import ast
import io
import json
import os
import re
import shutil
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import magic
import pandas as pd
from flask import current_app, jsonify
from openpyxl.styles import Alignment
from werkzeug.datastructures.file_storage import FileStorage
from werkzeug.utils import secure_filename

from app.schemas.error import ErrorCode
from app.schemas.response import Response
from app.utils.files import (
    apply_changes,
    create_excel_frames,
    extract_parent_paths,
    list_all_files,
    read_json_files,
    save_excel_report,
)
from app.utils.report import flatten_json_to_rows

LOCALIZATION_KEYS = ["original", "localized"]


def save_temp_file(file: FileStorage) -> str:
    """
    Save the uploaded file to a temporary location and return the path.
    """
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, secure_filename(file.filename or "uploaded_file"))
    file.save(file_path)
    return file_path


def extract_zip_to_temp(zip_path: str) -> str:
    extract_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)
    return extract_dir


def create_zip_from_folder(folder_path: str) -> str:
    zip_path = folder_path + ".zip"
    shutil.make_archive(folder_path, "zip", folder_path)
    return zip_path


def safe_load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def walk_json_files(folder_path: str):
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".json"):
                yield os.path.join(root, file)


def extract_excel_columns(excel_file: FileStorage) -> list[str]:
    try:
        filename = secure_filename(excel_file.filename or "uploaded.xlsx")
        ext = os.path.splitext(filename)[1].lower()
        if ext not in [".xls", ".xlsx"]:
            return jsonify(Response().error_response(ErrorCode.NOT_INVALID_FILE).model_dump())  # type: ignore

        data = io.BytesIO(excel_file.read())
        df = pd.read_excel(data, engine="openpyxl")
        columns = df.columns.tolist()
        return columns
    except Exception as e:
        current_app.logger.error(f"Failed to extract columns: {str(e)}")
        raise e


def extract_and_download_service(
    header: str,
    excel_file: FileStorage,
    archive_file: FileStorage,
) -> str:
    # Excel에서 추출할 파일 리스트 확보
    data = io.BytesIO(excel_file.read())
    df = pd.read_excel(data, engine="openpyxl", usecols=[header]).dropna()
    filenames = [os.path.basename(f).lower().strip() for f in df[header].astype(str)]

    archive_path = save_temp_file(archive_file)
    temp_dir = extract_zip_to_temp(archive_path)
    extracted_dir = os.path.join(temp_dir, "extracted")
    os.makedirs(extracted_dir, exist_ok=True)

    with zipfile.ZipFile(archive_path, "r") as z:
        all_files = {os.path.basename(p).lower(): p for p in z.namelist()}
        for name in filenames:
            name = name.lower().strip()
            if name in all_files:
                z.extract(all_files[name], extracted_dir)

    return create_zip_from_folder(extracted_dir)


def is_all_int_values_zero(d: dict) -> bool:
    return all(isinstance(v, int) and v == 0 for k, v in d.items() if not isinstance(v, bool))  # bool 제외


def summarize_modify_list(modify_list: list[dict], selected_keys: list[str]) -> dict[str, int]:
    summary = defaultdict(int)

    for item in modify_list:
        for key in selected_keys + ["etc"]:
            summary[key] += item.get(key, 0)

    return dict(summary)


def apply_changes_and_download_service(
    origin_file: FileStorage,
    work_file: FileStorage,
    selected_keys: list[str],
) -> dict[str, Any]:
    counts = {key: 0 for key in selected_keys}
    counts["etc"] = 0

    all_list = []
    err_list = []
    modify_list = []
    unModify_list = []

    origin_path = save_temp_file(origin_file)
    work_path = save_temp_file(work_file)

    origin_dir = extract_zip_to_temp(origin_path)
    work_dir = extract_zip_to_temp(work_path)
    output_dir = tempfile.mkdtemp()

    for modify_file_path in list_all_files(work_dir):
        if not modify_file_path.endswith(".json"):
            continue

        _origin_path = modify_file_path.replace(work_dir, "")
        all_list.append(_origin_path)

        result = apply_changes(modify_file_path, origin_dir, work_dir, output_dir, selected_keys)
        if is_all_int_values_zero(result):
            # 변경 건이 없는 경우
            unModify_list.append(_origin_path)

        if result.get("is_err"):
            err_list.append(modify_file_path.replace(work_dir, "."))
        else:
            del result["is_err"]
            modify_list.append({"filename": _origin_path, **result})

    if not os.listdir(output_dir):
        raise FileNotFoundError("No modified files found.")

    # 엑셀 파일 다운로드
    summary_counts = summarize_modify_list(modify_list, selected_keys)
    frames = create_excel_frames(all_list, unModify_list, modify_list, err_list, selected_keys)
    save_excel_report(frames, output_dir=output_dir)

    zip_path = create_zip_from_folder(output_dir)
    return {"zip_path": zip_path, "total_cnt": len(all_list), "err_list": err_list, **summary_counts}


def check_validate_json_service(zip_file: FileStorage) -> tuple[dict[str, int], list[str]]:
    info = {"totalCnt": 0, "jsonCnt": 0, "successCnt": 0, "failCnt": 0}
    errors = []

    zip_path = save_temp_file(zip_file)
    extract_dir = extract_zip_to_temp(zip_path)

    for file_path in walk_json_files(extract_dir):
        info["totalCnt"] += 1
        mime = magic.Magic(mime=True).from_file(file_path)
        if mime == "application/json" or (mime == "text/plain" and file_path.endswith(".json")):
            info["jsonCnt"] += 1
            try:
                safe_load_json(file_path)
                info["successCnt"] += 1
            except (json.JSONDecodeError, UnicodeDecodeError):
                errors.append(os.path.relpath(file_path, extract_dir))
                info["failCnt"] += 1

    return info, errors


def extract_keys_from_json(json_data: dict[str, Any], keys=None) -> set[str]:
    if keys is None:
        keys = set()
        keys = set()

    if isinstance(json_data, dict):
        keys.update(json_data.keys())
        for value in json_data.values():
            extract_keys_from_json(value, keys)
    elif isinstance(json_data, list):
        for item in json_data:
            extract_keys_from_json(item, keys)

    return keys


def get_keys_service(zip_file: FileStorage):
    all_keys = set()
    zip_path = save_temp_file(zip_file)
    extract_dir = extract_zip_to_temp(zip_path)

    for file_path in walk_json_files(extract_dir):
        try:
            json_data = safe_load_json(file_path)
            all_keys.update(extract_keys_from_json(json_data))
        except json.JSONDecodeError:
            continue


def remove_key_from_json(data: dict[str, Any], key_to_remove: str):
    if isinstance(data, dict):
        if key_to_remove in data:
            del data[key_to_remove]
        for key in data:
            remove_key_from_json(data[key], key_to_remove)
    elif isinstance(data, list):
        for item in data:
            remove_key_from_json(item, key_to_remove)
            remove_key_from_json(item, key_to_remove)


def remove_keys_service(zip_file: FileStorage, remove_key: str) -> io.BytesIO:
    zip_path = save_temp_file(zip_file)
    extract_dir = extract_zip_to_temp(zip_path)

    output_buffer = io.BytesIO()
    with zipfile.ZipFile(output_buffer, "w", zipfile.ZIP_DEFLATED) as out_zip:
        for file_path in walk_json_files(extract_dir):
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    remove_key_from_json(data, remove_key)
                    out_zip.writestr(
                        os.path.relpath(file_path, extract_dir),
                        json.dumps(data, ensure_ascii=False, indent=4).encode("utf-8"),
                    )
                except json.JSONDecodeError:
                    raise ValueError(f"Invalid JSON: {file_path}")

    output_buffer.seek(0)
    return output_buffer


def read_json_file_list(dwn_file: FileStorage):
    def _replace_digits_and_deduplicate(strings):
        result = set()
        for s in strings:
            # 숫자를 *로 치환
            replaced = re.sub(r"\d+", "*", s)
            result.add(replaced)
        return sorted(result)

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "uploaded.zip")
        dwn_file.save(zip_path)

        # ZIP 압축 해제
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)

        # JSON 파일 읽기
        json_data_list = read_json_files(tmpdir)

    paths = extract_parent_paths(json_data_list)
    unique_replaced = _replace_digits_and_deduplicate(paths)
    return unique_replaced


def join_path(path_elements):
    """
    리스트 형태의 경로 요소들을 문자열로 결합합니다.
    리스트 인덱스는 앞에 dot(.) 없이 붙입니다.
    예) ['agent_dialogues', '[0]', 'request'] --> "agent_dialogues[0].request"
    """
    if not path_elements:
        return ""
    result = path_elements[0]
    for elem in path_elements[1:]:
        if elem.startswith("["):
            result += elem
        else:
            result += "." + elem
    return result


def encode_special_chars(text):
    if isinstance(text, str):
        return text.replace("\r\n", "\\r\\n").replace("\r", "\\r").replace("\n", "\\n")
    return text


def decode_special_chars(text):
    if isinstance(text, str):
        return text.replace("\\r\\n", "\r\n").replace("\\r", "\r").replace("\\n", "\n")
    return text


def extract_pairs(obj, cur_path, target_keys):
    """
    JSON 객체를 재귀적으로 순회하여, 'original'과 'localized'
    키가 동시에 존재하는 노드를 찾고, 현재 경로와 함께 반환합니다.
    """
    results = []
    if isinstance(obj, dict):
        has_target_key = any(key in obj for key in target_keys)
        if has_target_key:
            path_str = join_path(cur_path)
            node_data = {key: encode_special_chars(obj[key]) for key in obj.keys()}
            results.append({"path": path_str, **node_data})
        else:
            for k, v in obj.items():
                results.extend(extract_pairs(v, cur_path + [k], target_keys))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            results.extend(extract_pairs(item, cur_path + [f"[{i}]"], target_keys))
    return results


def convert_json_to_xlsx(zip_file: FileStorage) -> tuple[list[dict], set[str], set[str]]:
    """
    ZIP 파일 내 모든 JSON을 파싱하여, 평탄화된 데이터 행과 함께
    전체 파일에서 발견된 모든 info 키와 추가 데이터 키의 목록을 반환합니다.
    """
    all_rows = []
    # 전체 파일에서 발견된 모든 키를 추적하기 위한 세트(set)
    all_info_keys = set()
    all_other_data_keys = set()

    zip_path = save_temp_file(zip_file)
    extract_dir = extract_zip_to_temp(zip_path)

    # 압축 해제된 디렉토리 내 모든 json 파일 순회
    for file_path in walk_json_files(extract_dir):
        try:
            data = safe_load_json(file_path)
            if not data:
                continue

            if "info" in data and isinstance(data["info"], dict):
                all_info_keys.update(data["info"].keys())

            # 파일 경로와 파일명을 추출
            # extract_dir을 기준으로 상대 경로를 계산하여 'file_path'로 사용
            relative_path = os.path.relpath(os.path.dirname(file_path), extract_dir)
            # 순수 파일명
            filename = os.path.basename(file_path)

            # 경로가 현재 디렉토리일 경우 '.'으로 표시될 수 있으므로, 이를 처리
            if relative_path == ".":
                relative_path = ""

            # 핵심: 우리가 만든 유연한 파싱 함수 호출
            # 첫 번째 인자: JSON 데이터
            # 두 번째 인자: 엑셀에 기록될 상대 경로
            # 세 번째 인자: 엑셀에 기록될 파일명
            rows_from_file = flatten_json_to_rows(
                json_data=data, file_path=relative_path.replace("\\", "/"), filename=filename  # Windows 경로 호환성
            )

            base_cols = {"file_path", "filename", "root_key", "index", "path", "original", "localized"}
            for r in rows_from_file:
                if "original" in r:  # 데이터 행 확인
                    # 행의 키들 중에서, 기본 컬럼과 info 컬럼이 아닌 것을 추가 데이터 키로 간주
                    row_keys = set(r.keys())
                    other_keys = row_keys - base_cols - all_info_keys
                    all_other_data_keys.update(other_keys)

            # 현재 파일에서 추출된 행들을 전체 리스트에 추가
            all_rows.extend(rows_from_file)

        except Exception as e:
            current_app.logger.error(f"Error processing {file_path}: {str(e)}")
            # 특정 파일 오류 시에도 계속 진행하려면 아래 raise를 주석 처리
            # raise e

    # 임시 파일 및 디렉토리 정리 (필요시)
    # cleanup_temp_files(zip_path, extract_dir)

    return all_rows, all_info_keys, all_other_data_keys


def create_row(info, path, root_key, index, pair):
    file_path, filename = os.path.split(path)

    row = {"file_path": file_path, "filename": filename, "root_key": root_key, "index": index, **pair}  # 디렉토리 경로
    row.update(info)
    return row


def parse_value(value):
    """
    셀 값을 JSON-직렬화하기 전에 정규화한다.
      * NaN  → ""
      * None → None  (→ JSON null)
      * "[a, b]" 같은 문자열 리스트 → 실제 리스트
      * \r\n, \r → \n 으로 표준화
    """
    # 1) None 은 그대로 둔다
    if value is None:
        return "None"

    # 2) NaN, pd.NA → ""
    if pd.isna(value):
        return ""

    # 3) 문자열 후처리
    if isinstance(value, str):
        if value == "":
            return ""
        if value.startswith("[") and value.endswith("]"):
            try:
                return ast.literal_eval(value)
            except (ValueError, SyntaxError):
                pass  # 형식이 틀리면 그냥 문자열로

    return decode_special_chars(value)


def convert_excel_to_json(xlsx_file: FileStorage, default_columns: list[str]) -> io.BytesIO:
    try:
        df = pd.read_excel(xlsx_file, dtype_backend="pyarrow", na_values=[""], keep_default_na=False)

        filled_fp = df["file_path"].ffill()  # Series, DataFrame에는 영향 없음
        filled_fn = df["filename"].ffill()

        grouped = df.groupby([filled_fp, filled_fn])
        output_buffer = io.BytesIO()
        with tempfile.TemporaryDirectory() as temp_dir:
            for (file_path, filename), group in grouped:
                try:
                    original_col_index = group.columns.get_loc(LOCALIZATION_KEYS[0])
                    localization_columns = group.columns[original_col_index:]
                except KeyError:
                    # original 컬럼이 없으면 기본값 사용
                    localization_columns = LOCALIZATION_KEYS

                first_row = group.iloc[0]
                info_keys = [col for col in df.columns if col not in default_columns]
                info_dict = {
                    key: first_row[key].item() if hasattr(first_row[key], "item") else first_row[key]
                    for key in info_keys
                    if pd.notnull(first_row[key])
                }
                output_data = {"info": info_dict}

                for _, row in group.iterrows():
                    root_key = row["root_key"]
                    item_index = "" if pd.isna(row["index"]) else str(row["index"])
                    path = row["path"]

                    localization_dict = {}
                    for key in localization_columns:
                        # 엑셀의 현재 행(row)에 해당 컬럼이 있고, 값이 비어있지 않다면
                        if key in LOCALIZATION_KEYS:
                            if key in row:
                                localization_dict[key] = parse_value(row[key])
                        else:
                            if key in row and pd.notna(row[key]) and row[key] != "":  # 빈 문자열이 아닌 경우
                                localization_dict[key] = parse_value(row[key])

                    if not localization_dict:
                        continue

                    # root_key가 없으면 생성
                    if root_key not in output_data:
                        output_data[root_key] = {}

                    indexed_key = f"{root_key}_{item_index}" if item_index else root_key
                    if indexed_key not in output_data[root_key]:
                        output_data[root_key][indexed_key] = {}

                    output_data[root_key][indexed_key][path] = localization_dict

                # temp 디렉토리에 파일 저장
                full_output_path = Path(temp_dir) / file_path / filename
                full_output_path.parent.mkdir(parents=True, exist_ok=True)

                with open(full_output_path, "w", encoding="utf-8") as f:
                    json.dump(output_data, f, ensure_ascii=False, indent=2)

            # temp_dir 내부 파일을 ZIP으로 압축
            with zipfile.ZipFile(output_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        abs_path = os.path.join(root, file)
                        rel_path = os.path.relpath(abs_path, temp_dir)
                        zipf.write(abs_path, arcname=rel_path)

        output_buffer.seek(0)
        return output_buffer
    except Exception as e:
        current_app.logger.error(f"Error processing: {str(e)}")
        raise e


def create_excel_from_dataframe(df: pd.DataFrame) -> io.BytesIO:
    """
    DataFrame 데이터를 기반으로 메모리 상에서 셀 병합 및 서식이 적용된 Excel 보고서를 생성합니다.
    - 병합은 file_path와 filename을 기준으로 그룹화하여 파일 단위로만 수행됩니다.
    - 병합 대상 컬럼은 동적으로 결정됩니다.

    Args:
        df: 엑셀로 변환할 데이터가 담긴, 이미 컬럼 순서가 정리된 DataFrame.

    Returns:
        Excel 파일 데이터가 담긴 BytesIO 버퍼.
    """
    # 1. 메모리 버퍼에 Excel 파일 쓰기
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="JSON_Data")  # 시트 이름은 여기서 지정

        # 2. openpyxl 워크북 및 워크시트 객체 가져오기
        worksheet = writer.sheets["JSON_Data"]

        # 3. 병합에서 제외할 컬럼 목록 정의
        # 이 목록에 없는 컬럼은 모두 병합 대상이 됩니다.
        cols_to_exclude_from_merge = ["root_key", "index", "path", "original", "localized"]

        # 'original', 'localized' 외 다른 데이터 컬럼이 있을 수 있으므로,
        # 제외 목록에 없는 모든 컬럼을 병합 대상으로 동적으로 찾습니다.
        columns_to_merge = [col for col in df.columns if col not in cols_to_exclude_from_merge]

        # DataFrame 컬럼 이름을 Excel 컬럼 인덱스(1-based)로 매핑
        header = list(df.columns)
        merge_cols_indices = []
        for col_name in columns_to_merge:
            try:
                merge_cols_indices.append(header.index(col_name) + 1)
            except ValueError:
                pass  # DataFrame에 해당 컬럼이 없으면 무시

        # 4. file_path와 filename을 기준으로 그룹화하여 파일 단위로 셀 병합
        current_row_in_excel = 2  # 데이터 시작 행 (1은 헤더)

        # sort=False는 원본 데이터의 순서를 유지하기 위해 중요
        for _, group in df.groupby(["file_path", "filename"], sort=False):
            group_size = len(group)

            if group_size > 1:
                start_row = current_row_in_excel
                end_row = current_row_in_excel + group_size - 1

                for col_idx in merge_cols_indices:
                    worksheet.merge_cells(
                        start_row=start_row, start_column=col_idx, end_row=end_row, end_column=col_idx
                    )
                    # 병합된 첫 셀에 서식 적용
                    cell = worksheet.cell(row=start_row, column=col_idx)
                    cell.alignment = Alignment(vertical="top", horizontal="left", wrap_text=True)

            # 다음 그룹의 시작 행으로 이동
            current_row_in_excel += group_size

    # 5. 버퍼의 커서를 처음으로 되돌림
    excel_buffer.seek(0)
    return excel_buffer
