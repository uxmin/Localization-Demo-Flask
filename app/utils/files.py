import copy
import json
import os
import re
import traceback
from itertools import zip_longest
from typing import Any, Dict, List, Set, Union

import pandas as pd
from flask import current_app

UTTERANCE_NAME = "utterance"
EXPECTED_NAME = "expected_nlg"
REQUEST_NAME = "agent_dialogues[*].request"
RESPONSE_NAME = "agent_dialogues[*].response"


EDITED_TEXT_KEY_NAME = "modified"
ORIGINAL_TEXT_KEY_NAME = "origin"
TRANSLATION_KEY_NAME = "localized"

EXCLUDED_KEYS = ["locale"]  # 작업량 산출 및 작업 사항 적용을 하지 않을 KEY 리스트

DIFF_PATH = "diff_path"
ERROR_NAME = "[catch-error]"

REPORT_HEADER = ["summary", "unchanged_files", "modified_files", "error_files"]


def list_all_files(directory: str) -> List[str]:
    """
    지정된 디렉토리 및 그 하위 디렉토리에 있는 모든 파일의 경로를 리스트로 반환합니다.

    Parameters:
        directory (str): 파일 경로를 탐색할 시작 디렉토리입니다.

    Returns:
        List[str]: 발견된 모든 파일의 전체 경로를 포함하는 리스트입니다.
    """
    all_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if "__MACOSX" in root or file == ".DS_Store":
                continue
            full_path = os.path.join(root, file)
            all_files.append(full_path)

    return all_files


def load_json_file(filename: str) -> Dict[str, Any] | None:
    """
    지정된 파일 이름으로 JSON 파일을 로드합니다.

    Parameters:
        filename (str): 로드할 JSON 파일의 경로입니다.

    Returns:
        JSON 데이터를 포함하는 객체 또는 JSON 파일을 읽을 수 없는 경우 None.

    Raises:
        FileNotFoundError: 파일이 지정된 경로에 존재하지 않을 때 발생합니다.
        json.JSONDecodeError: 파일 내용이 유효한 JSON 형식이 아닐 경우 발생하지만, 이 함수에서는 None을 반환하여 예외를 처리합니다.
    """
    try:
        with open(filename, "r", encoding="utf-8-sig") as file:
            return json.load(file)
    except json.JSONDecodeError:
        return None
    except FileNotFoundError:
        current_app.logger.error(f"File Not Found: {filename}")
        return None


def compare_lists(list1: List[Any], list2: List[Any], path: str) -> List[Dict[str, Union[Any, str]]]:
    """
    두 리스트를 비교하여 차이점을 리스트로 반환합니다. 차이점은 각 요소의 경로와 값의 차이를 포함합니다.

    Parameters:
        list1 (List[Any]): 비교할 첫 번째 리스트입니다.
        list2 (List[Any]): 비교할 두 번째 리스트입니다.
        path (str): 현재 요소의 경로를 나타내는 문자열입니다.

    Returns:
        List[Dict[str, Union[Any, str]]]: 각 차이점을 나타내는 사전 객체의 리스트입니다. 사전에는 요소의 경로('sub_path'), 원본 값('origin'), 수정된 값('modify')이 포함됩니다.

    Description:
        - 리스트의 각 요소를 인덱스 별로 비교합니다.
        - 요소가 사전형인 경우, `compare_json` 함수를 재귀적으로 호출하여 내부 차이점을 탐색합니다.
        - 두 리스트의 길이가 다를 경우, 누락된 요소를 "Missing in first/second list"로 표시합니다.
    """
    differences = []

    if len(list1) == len(list2):
        for i, (item1, item2) in enumerate(zip(list1, list2)):
            sub_path = f"{path}:{i}"
            if isinstance(item1, dict) and isinstance(item2, dict):
                # 두 요소가 모두 Dict인 경우, 내부 차이점을 추출합니다.
                differences.extend(compare_json(item1, item2, sub_path))
            elif item1 != item2:
                # 두 요소가 다른 경우, 차이점을 추가합니다.
                differences.append({DIFF_PATH: sub_path, ORIGINAL_TEXT_KEY_NAME: item1, EDITED_TEXT_KEY_NAME: item2})
    else:
        for i, (item1, item2) in enumerate(zip_longest(list1, list2, fillvalue=None)):
            sub_path = f"{path}:{i}"
            if isinstance(item1, dict) and isinstance(item2, dict):
                # 두 요소가 모두 Dict인 경우, 내부 차이점을 추출합니다.
                differences.extend(compare_json(item1, item2, sub_path))
            elif item1 != item2:
                # 두 요소가 다른 경우, 차이점을 추가합니다.
                differences.append({DIFF_PATH: sub_path, ORIGINAL_TEXT_KEY_NAME: item1, EDITED_TEXT_KEY_NAME: item2})

    return differences


def compare_json(
    data1: Dict[str, Any], data2: Dict[str, Any], path: str = "", sep: str = "/"
) -> List[Dict[str, Union[str, Any]]]:
    """
    두 JSON 객체를 비교하여 차이점을 리스트로 반환합니다. 차이점은 각 요소의 경로와 값의 차이를 포함합니다.

    Parameters:
        data1 (Dict[str, Any]): 비교할 첫 번째 JSON 객체입니다.
        data2 (Dict[str, Any]): 비교할 두 번째 JSON 객체입니다.
        path (str): 현재 요소의 경로를 나타내는 문자열입니다. 기본값은 빈 문자열입니다.
        sep (str): 경로 구분자로 사용할 문자열입니다. 기본값은 "/"입니다.

    Returns:
        List[Dict[str, Union[str, Any]]]: 각 차이점을 나타내는 사전 객체의 리스트입니다. 사전에는 요소의 경로('sub_path'), 원본 값('origin'), 수정된 값('modify')이 포함됩니다.

    Description:
        - 두 JSON 객체의 모든 키를 순회하며 비교합니다.
        - 키가 Dict인 경우, `compare_json` 함수를 재귀적으로 호출하여 내부 차이점을 탐색합니다.
        - 키가 List인 경우, `compare_lists` 함수를 호출하여 리스트 내 차이점을 탐색합니다.
        - 두 객체에서 각각만 존재하는 키가 있을 경우, 이를 차이점으로 기록합니다.
    """

    differences = []

    # 모든 키를 비교합니다.
    for key in data1.keys():
        if key not in data2:
            sub_path = f"{path}/{key}" if path else key
            differences.append(
                {
                    DIFF_PATH: sub_path,
                    ORIGINAL_TEXT_KEY_NAME: data1[key],
                    EDITED_TEXT_KEY_NAME: f"{ERROR_NAME} Key missing in second",
                }
            )
        else:
            sub_path = f"{path}{sep}{key}" if path else key
            if isinstance(data1[key], dict) and isinstance(data2[key], dict):
                differences.extend(compare_json(data1[key], data2[key], sub_path))
            elif isinstance(data1[key], list) and isinstance(data2[key], list):
                differences.extend(compare_lists(data1[key], data2[key], sub_path))
            elif data1[key] != data2[key]:
                differences.append(
                    {DIFF_PATH: sub_path, ORIGINAL_TEXT_KEY_NAME: data1[key], EDITED_TEXT_KEY_NAME: data2[key]}
                )

    # 두 번째 JSON에만 존재하는 키를 확인합니다.
    for key in data2.keys():
        if key not in data1:
            sub_path = f"{path}{sep}{key}" if path else key
            differences.append(
                {
                    DIFF_PATH: sub_path,
                    ORIGINAL_TEXT_KEY_NAME: f"{ERROR_NAME} Key missing in first",
                    EDITED_TEXT_KEY_NAME: data2[key],
                }
            )

    return differences


def apply_changes_not_parent(data: Dict[str, Any], diff: Dict[str, Any], sep: str = "/") -> None:
    """
    JSON 데이터 구조 내에서 지정된 경로에 따라 특정 값을 수정합니다.

    Parameters:
        data (Dict[str, Any]): 수정할 원본 JSON 데이터입니다.
        diff (Dict[str, Any]): 변경사항을 포함하는 딕셔너리. 'sub_path'는 변경을 적용할 경로를, 'modify'는 새로운 값 또는 수정된 값을 나타냅니다.
        sep (str): 경로 구분자로 사용할 문자열입니다. 기본값은 "/"입니다.

    Description:
        - 함수는 'sub_path'에 따라 중첩된 딕셔너리를 순회합니다.
        - 경로의 마지막 요소에 도달했을 때, 변경사항을 적용합니다.
        - 'utterance' 또는 'expected_nlg' 항목을 수정하는 경우, 해당 항목의 이름을 'modified_utterance' 또는 'modified_nlg'로 변경하여 수정된 값을 저장합니다.
        - 'utterance' 또는 'expected_nlg' 이외의 항목을 수정하는 경우 (origin or localized), 또는 배열 인덱스를 포함하는 경로는 'modified' 키에 변경된 값을 배열로 저장합니다.
        - 예외 발생 시 traceback을 출력하여 오류를 추적합니다.
    """
    path, modified_value = diff.get(DIFF_PATH, ""), diff.get(EDITED_TEXT_KEY_NAME, "")

    keys = path.split(sep)
    current = data
    parent = None

    symbol = ":"
    for i in range(len(keys)):

        # 부모 주입
        if i > 0:
            parent = current

        key: str = keys[i]

        if symbol in key:
            key_name, key_index = key.split(symbol)
            key_index = int(key_index)
            if key_name in current and isinstance(current[key_name], list) and 0 <= key_index < len(current[key_name]):
                current = current[key_name][key_index]
            else:
                current = None
        else:
            current = current[key]

        try:
            if i == len(keys) - 1:
                if key in EXCLUDED_KEYS:
                    continue

                # 발화 또는 응답 수정이 발생한 경우

                # Case 1: 다국어 번역 작업 X (e.g., "turns[N].utterance": "안녕")
                if key == UTTERANCE_NAME or key == EXPECTED_NAME:
                    if key == UTTERANCE_NAME:
                        _key = key.replace(UTTERANCE_NAME, f"{EDITED_TEXT_KEY_NAME}_{UTTERANCE_NAME}")
                    elif key == EXPECTED_NAME:
                        _key = key.replace(EXPECTED_NAME, f"{EDITED_TEXT_KEY_NAME}_nlg")

                    parent[_key] = modified_value

                # Case 2: 다국어 번역 작업 O (e.g., "turns[N].utterance": {"original": "hello", "localized": "안녕"})
                else:
                    if key.startswith(ORIGINAL_TEXT_KEY_NAME) or key.startswith(TRANSLATION_KEY_NAME):
                        # e.g., origin, origin:1, ..., origin:N, localized, localized:1, ..., localized:N
                        _key = EDITED_TEXT_KEY_NAME

                        if symbol in key:
                            # e.g., origin:1, ..., origin:N, localized:1, ..., localized:N
                            if len(parent.get(_key, [])) == 0:
                                parent[_key] = copy.deepcopy(parent[TRANSLATION_KEY_NAME])
                            _, _key_index = key.split(symbol)
                            _key_index = int(_key_index)

                            try:
                                parent[_key][_key_index] = modified_value
                            except IndexError:
                                while len(parent[_key]) <= _key_index:
                                    parent[_key].append(None)
                                parent[_key][_key_index] = modified_value
                        else:
                            parent[_key] = modified_value
                    else:
                        # e.g., suggest? 없을 것으로 추정됨.
                        _key = f"{key}_{EDITED_TEXT_KEY_NAME}"
                        parent[_key] = modified_value

        except Exception:
            traceback.print_exc()


def clean_json(json_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    JSON 데이터에서 value가 리스트인 경우, 리스트 내 None 요소를 제거하는 함수

    Parameters:
        json_data (Dict[str, Any]): None 제거가 필요한 JSON 데이터.

    Returns:
        Dict[str, Any]: None이 제거된 JSON 데이터.
    """
    if isinstance(json_data, dict):
        for key, value in json_data.items():
            if isinstance(value, list):
                # 리스트에서 None 요소 제거
                json_data[key] = [item for item in value if item is not None]
            else:
                # 재귀 호출로 내부 데이터도 검사
                clean_json(value)
    elif isinstance(json_data, list):
        for item in json_data:
            clean_json(item)
    return json_data


def matches_pattern(path, pattern):
    """특정 패턴과 일치하는 지 확인하는 함수"""
    # 패턴을 정규식으로 변환: [*] → \[\d+\], 나머지는 escape
    regex_pattern = re.escape(pattern).replace(r"\[\*\]", r"\[\d+\]")
    return bool(re.search(regex_pattern, path))


def chg_pattern(path: str) -> str:
    return re.sub(r"\d+", "*", path.replace("/", "."))


def apply_changes(
    modify_file_path: str,
    origin_extracted: str,
    work_extracted: str,
    output_dir: str,
    selected_keys: list[str],
) -> Dict[str, Any]:
    """
    수정된 JSON 파일과 원본을 비교하여 변경사항을 새로운 출력 파일에 적용합니다.

    Parameters:
        modify_file_path (str): 수정된 JSON 파일의 경로입니다.
        origin_extracted (str): 원본 JSON 파일이 저장된 루트 디렉토리 경로입니다.
        work_extracted (str): 수정된 JSON 파일이 저장된 루트 디렉토리 경로입니다.
        output_dir (str): 출력 JSON 파일이 저장될 루트 디렉토리 경로입니다.

    Returns:
        Dict[str, any]: 발화(utterances), 응답(expected NLGs), 기타 슬롯(slot) 등 변경 횟수를 각각 포함하는 딕셔너리입니다.

    Raises:
        FileNotFoundError: 지정된 경로에 원본 또는 수정 파일이 없는 경우 발생할 수 있습니다.
    """
    counts = {k: 0 for k in selected_keys}
    counts["etc"] = 0

    # 작업 경로를 원본 및 출력 위치로 업데이트
    original_file_path = modify_file_path.replace(work_extracted, origin_extracted)
    output_file_path = modify_file_path.replace(work_extracted, output_dir)

    # 원본 및 수정된 파일에서 JSON 내용 로드
    original_file = load_json_file(original_file_path)
    modify_file = load_json_file(modify_file_path)

    # 파일을 로드할 수 없는 경우 0을 반환
    if original_file is None or modify_file is None:
        return {**counts, "is_err": False}

    # JSON 파일 비교 및 차이 계산
    diffs = compare_json(original_file, modify_file)
    is_err: bool = any(
        (isinstance(diff[ORIGINAL_TEXT_KEY_NAME], str) and ERROR_NAME in diff[ORIGINAL_TEXT_KEY_NAME])
        or (isinstance(diff[EDITED_TEXT_KEY_NAME], str) and ERROR_NAME in diff[EDITED_TEXT_KEY_NAME])
        for diff in diffs
    )

    if is_err:
        for diff in diffs:
            if ERROR_NAME in diff[ORIGINAL_TEXT_KEY_NAME] or ERROR_NAME in diff[EDITED_TEXT_KEY_NAME]:
                current_app.logger.info(json.dumps(diff, indent=2, ensure_ascii=False))
        return {**counts, "is_err": True}

    # 원본 파일의 깊은 복사본을 생성하여 변경 적용 시작
    output_file = copy.deepcopy(original_file)

    # JSON 구조 내 각 차이점 처리
    for diff in diffs:
        # current_app.logger.info(diff)
        # print(json.dumps(diff, indent=2, ensure_ascii=False) + ",")
        _diff_path = chg_pattern(diff[DIFF_PATH])

        _chk_pattern = False
        for selected_key in selected_keys:
            if selected_key in _diff_path:
                counts[selected_key] += 1
                _chk_pattern = True
                break

        if not _chk_pattern and not any(key in diff[DIFF_PATH] for key in EXCLUDED_KEYS):
            counts["etc"] += 1
        apply_changes_not_parent(output_file, diff)

    output_file = clean_json(output_file)

    # 쓰기 전에 출력 디렉토리 존재 확인
    directory = os.path.dirname(output_file_path)
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    # 변경된 내용을 새 파일에 쓰기
    with open(output_file_path, "w") as file:
        json.dump(output_file, file, ensure_ascii=False, indent=2)

    return {**counts, "is_err": False}


def read_json_files(folder_path):
    """지정한 폴더 내의 모든 .json 파일을 재귀적으로 검색하여, 파일의 내용을 리스트로 반환한다."""
    json_list = []

    # os.walk를 사용하여 지정된 폴더 내의 모든 하위 디렉토리를 재귀적으로 순회합니다.
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            # 파일 확장자가 .json (대소문자 무관) 인 경우 처리
            if file.lower().endswith(".json"):
                file_path = os.path.join(root, file)
                try:
                    # JSON 파일 읽기 (UTF-8 인코딩)
                    with open(file_path, "r", encoding="utf-8") as json_file:
                        data = json.load(json_file)
                        json_list.append(data)
                except Exception as e:
                    # 파일 읽기 또는 파싱 중 문제가 생기면 에러 메시지를 출력합니다.
                    print(f"파일을 읽는 중 오류 발생 ({file_path}): {e}")
    return json_list


def extract_parent_paths(json_objs: List[dict]) -> List[str]:
    """
    여러 JSON(dict)을 돌며 경로를 추출 → 정렬 후 반환
    """

    TARGET_KEYS = {"original", "localized"}

    def _collect_paths(node: Any, path: List[str], out: Set[tuple]) -> None:
        """
        재귀 탐색: original/localized 포함 딕셔너리의 '부모 경로 토큰 리스트'를 out에 저장
        """
        if isinstance(node, dict):
            # ① original / localized 가 있는 딕셔너리인가?
            if TARGET_KEYS & node.keys():
                out.add(tuple(path))  # 토큰 리스트를 튜플로 저장 (hashable)
            # ② 하위로 내려가기
            for k, v in node.items():
                _collect_paths(v, path + [k], out)

        elif isinstance(node, list):
            for idx, item in enumerate(node):
                _collect_paths(item, path + [str(idx)], out)
        # str/int/None 등은 패스

    def _tokens_to_str(tokens: List[str]) -> str:
        """
        토큰 리스트 → 'turns[*].agent_dialogues[*].response' 형태 문자열
        (숫자 토큰은 앞 토큰 뒤에 [*] 로 붙여준다)
        """
        idx_pattern = re.compile(r"^\d+$")  # '0', '1', ...
        out: List[str] = []
        for t in tokens:
            if idx_pattern.fullmatch(t):  # 리스트 인덱스
                if not out:
                    continue  # 루트가 바로 숫자인 경우는 거의 없음
                out[-1] += "[*]"
            else:
                out.append(t)
        return ".".join(out)

    raw_paths: Set[tuple] = set()
    for obj in json_objs:
        _collect_paths(obj, [], raw_paths)

    # 토큰 리스트(tuple) → 문자열로 변환
    return sorted(_tokens_to_str(list(p)) for p in raw_paths)


def create_excel_frames(
    all_list: list[str],
    unModify_list: list[str],
    modify_list: list[dict[str, Any]],
    err_list: list[str],
    selected_keys: List[str],
) -> Dict[str, Any]:
    # 1. 수정된 파일 전체
    modified_files = [item["filename"] for item in modify_list]

    # 3. 시트1: 집계 결과
    df_overall = pd.DataFrame(
        [
            {
                "Total Files": len(all_list),
                "Unchanged Files": len(unModify_list),
                "Modified Files": len(modified_files),
                "Error Files": len(err_list),
            }
        ]
    )

    # 3. 시트1: key별 요약
    key_summary = []
    for key in selected_keys + ["etc"]:
        total = sum(item.get(key, 0) for item in modify_list)
        files_count = sum(1 for item in modify_list if item.get(key, 0) > 0)
        key_summary.append({"KEY": key, "Modified Count": total, "Modified File Count": files_count})
    key_summary.append(
        {
            "KEY": "total",
            "Modified Count": sum(row["Modified Count"] for row in key_summary),
            "Modified File Count": len(modify_list),
        }
    )

    df_key_summary = pd.DataFrame(key_summary)

    # 4. 시트2: 수정되지 않은 파일
    df_unchanged = pd.DataFrame({"filename": unModify_list}) if unModify_list else None

    # 5. 시트3: 수정된 파일 상세 (파일별 key별 count)
    df_modified_detail = pd.DataFrame(modify_list)

    # 6. 시트4: 에러 파일
    df_err = pd.DataFrame({"filename": sorted(err_list)}) if err_list else None

    return {
        REPORT_HEADER[0]: (df_overall, df_key_summary),
        REPORT_HEADER[1]: df_unchanged,
        REPORT_HEADER[2]: df_modified_detail,
        REPORT_HEADER[3]: df_err,
    }


def save_excel_report(frames: dict, output_dir: str, filename="report.xlsx") -> str:
    excel_path = os.path.join(output_dir, filename)
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        # 집계 결과: 두 테이블 (상단 + 하단)
        overall, key_summary = frames[REPORT_HEADER[0]]
        overall.to_excel(writer, sheet_name=REPORT_HEADER[0], index=False, startrow=0)
        key_summary.to_excel(writer, sheet_name=REPORT_HEADER[0], index=False, startrow=3)

        # 다른 시트
        if frames.get(REPORT_HEADER[1]) is not None:
            frames[REPORT_HEADER[1]].to_excel(writer, sheet_name=REPORT_HEADER[1], index=False)

        if frames.get(REPORT_HEADER[2]) is not None:
            frames[REPORT_HEADER[2]].to_excel(writer, sheet_name=REPORT_HEADER[2], index=False)

        if frames.get(REPORT_HEADER[3]) is not None:
            frames[REPORT_HEADER[3]].to_excel(writer, sheet_name=REPORT_HEADER[3], index=False)

    return excel_path
