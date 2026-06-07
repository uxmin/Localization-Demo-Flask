import re
from io import BytesIO

import numpy as np
import pandas as pd
from openpyxl.styles import Alignment


def create_excel_report_in_memory(df: pd.DataFrame) -> BytesIO:
    """
    데이터를 기반으로 메모리 상에서 셀 병합 및 서식이 적용된 Excel 보고서를 생성합니다.
    - 동적 컬럼을 처리하며, 지정된 컬럼을 제외하고 셀을 병합합니다.

    Args:
        df: 엑셀로 변환할 데이터가 담긴, 이미 컬럼 순서가 정리된 DataFrame.

    Returns:
        Excel 파일 데이터가 담긴 BytesIO 버퍼.
    """
    # 1. 메모리 버퍼에 Excel 파일 쓰기
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="KPI_Report")

        # 2. openpyxl 워크북 및 워크시트 객체 가져오기비
        workbook = writer.book
        worksheet = writer.sheets["KPI_Report"]

        # 3. 병합에서 제외할 컬럼 목록 정의
        cols_to_exclude_from_merge = ["root_key", "index", "path", "original", "localized", "fixed"]

        # 병합할 대상 컬럼 목록 생성 (제외 목록에 없는 모든 컬럼)
        columns_to_merge = [col for col in df.columns if col not in cols_to_exclude_from_merge]

        # DataFrame 컬럼 이름을 Excel 컬럼 인덱스(1-based)로 매핑
        header = list(df.columns)
        col_indices_to_merge = []
        for col_name in columns_to_merge:
            try:
                # header 리스트에서 컬럼 이름의 위치를 찾아 1을 더함
                col_indices_to_merge.append(header.index(col_name) + 1)
            except ValueError:
                # DataFrame에 해당 컬럼이 없는 경우는 거의 없지만, 안전장치
                pass

        current_row_in_excel = 2  # 데이터 시작 행 (1은 헤더)

        # sort=False는 원본 데이터의 순서를 유지하기 위해 매우 중요합니다.
        for _, group in df.groupby(["file_path", "filename"], sort=False):
            group_size = len(group)

            # 그룹의 행이 2개 이상일 때만 병합을 수행합니다.
            if group_size > 1:
                start_row = current_row_in_excel
                end_row = current_row_in_excel + group_size - 1

                for col_idx in col_indices_to_merge:
                    # 해당 컬럼의 값이 그룹 내에서 모두 동일한지 한 번 더 확인 (선택적 안전장치)
                    # 대부분의 경우 이 값들은 동일할 것이므로, 이 check는 생략해도 무방합니다.
                    # if group.iloc[:, col_idx - 1].nunique() == 1:
                    worksheet.merge_cells(
                        start_row=start_row, start_column=col_idx, end_row=end_row, end_column=col_idx
                    )
                    # 병합된 첫 셀에 서식 적용
                    cell = worksheet.cell(row=start_row, column=col_idx)
                    cell.alignment = Alignment(vertical="top", horizontal="left", wrap_text=True)

            # 다음 그룹의 시작 행을 계산하기 위해 현재 그룹의 크기를 더해줍니다.
            current_row_in_excel += group_size

    # 5. 버퍼의 커서를 처음으로 되돌려 send_file이 읽을 수 있도록 준비
    excel_buffer.seek(0)
    return excel_buffer


def flatten_json_to_rows(json_data: dict, file_path: str, filename: str):
    """
    JSON 데이터를 분석하여 평탄화된 행 리스트를 반환합니다.
    - file_path와 filename을 직접 인자로 받아 메타데이터로 사용합니다.
    """
    # 1. info 블록을 동적으로 처리
    base_info = json_data.get("info", {})

    # 2. 파일 경로 관련 메타데이터를 인자로부터 직접 받음
    file_meta = {"file_path": file_path, "filename": filename}

    all_rows = []

    # traverse 함수는 내부 로직 변경 없음 (이전과 동일)
    def traverse(node, current_path, root_key):
        # ... (이전과 동일한 traverse 함수 내용) ...
        path_without_root = current_path.replace(root_key, "", 1).lstrip(".")
        first_segment = path_without_root.split(".")[0]
        index_match = re.match(r"\[(\d+)\]", first_segment)
        index_val = index_match.group(1) if index_match else (first_segment if first_segment else "N/A")

        row_template = {**file_meta, **base_info, "root_key": root_key, "index": index_val, "path": current_path}

        # 규칙 1: 'original'/'localized' 쌍은 최우선 추출 대상
        if isinstance(node, dict) and "original" in node and "localized" in node and len(node) == 2:
            row = row_template.copy()
            row["original"] = node["original"]
            row["localized"] = node["localized"]
            all_rows.append(row)
            return

        # 규칙 2: 단순 문자열 값을 가진 리프 노드 추출
        if isinstance(node, str):
            row = row_template.copy()
            row["original"] = node
            row["localized"] = np.nan  # pandas 호환성을 위해 np.nan 사용
            all_rows.append(row)
            # 문자열은 리프 노드이므로 더 탐색하지 않음

        # 재귀 탐색
        if isinstance(node, list):
            for i, item in enumerate(node):
                traverse(item, f"{current_path}[{i}]", root_key)
        elif isinstance(node, dict):
            for key, value in node.items():
                traverse(value, f"{current_path}.{key}", root_key)

    for root_key, content in json_data.items():
        if root_key == "info":
            continue
        traverse(content, root_key, root_key)

    return all_rows
