"""KPI 집계 서비스.

GitHub 저장소의 `.review.json`과 작업 전/후 JSON 파일을 비교하여
번역/현지화 작업 결과를 행 단위로 펼치고 Excel 보고서로 만든다.

기존에는 이 로직이 컨트롤러(external.py)에 직접 들어가 있었으나,
도메인 책임 분리를 위해 서비스 계층으로 이동했다.
"""

import os
import re
from datetime import datetime
from io import BytesIO

import pandas as pd
from flask import current_app

from app.services.github import GithubService
from app.utils.report import create_excel_report_in_memory

REVIEW_JSON_PATH = "result/.review.json"
INITIAL_COMMIT_MESSAGE = "upload workfile"


class KpiService:
    def __init__(self, github_service: GithubService) -> None:
        self.github = github_service

    @staticmethod
    def _extract_pairs_recursive(value, current_path):
        """재귀적으로 {'original', 'localized'} 쌍을 찾아 경로와 함께 yield한다."""
        if isinstance(value, dict):
            if "original" in value and "localized" in value:
                yield {
                    "path": ".".join(current_path),
                    "original": value["original"],
                    "localized": value["localized"],
                }
            else:
                for key, sub_value in value.items():
                    yield from KpiService._extract_pairs_recursive(sub_value, current_path + [key])

    @classmethod
    def _parse_json_dynamically(cls, data) -> list[dict]:
        """JSON 데이터를 동적으로 순회하여 번역 쌍 목록을 추출한다."""
        parsed_items: list[dict] = []
        if not data:
            return parsed_items

        for root_key, root_val in data.items():
            if root_key == "info":  # 메타데이터는 제외
                continue
            if not isinstance(root_val, dict):
                continue

            for child_key, child_val in root_val.items():
                index = ""
                path_prefix = [child_key]

                # 'turns_0', 'turns_1' 같은 패턴은 index로 분리하고 경로에서 제외
                match = re.match(f"^{re.escape(root_key)}_(\\d+)$", child_key)
                if match:
                    index = match.group(1)
                    path_prefix = []

                for pair_info in cls._extract_pairs_recursive(child_val, path_prefix):
                    parsed_items.append(
                        {
                            "root_key": root_key,
                            "index": index,
                            "path": pair_info["path"],
                            "original": pair_info["original"],
                            "localized": pair_info["localized"],
                        }
                    )
        return parsed_items

    @staticmethod
    def _format_iso_date(date_str: str) -> str:
        """ISO 8601 문자열을 'YYYY-MM-DD HH:MM:SS'로 변환한다."""
        if not date_str:
            return ""
        try:
            dt_obj = datetime.fromisoformat(date_str.replace("Z", ""))
            return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return date_str

    def build_kpi_excel(self, branch: str) -> BytesIO | None:
        """브랜치의 리뷰 데이터를 기반으로 KPI 보고서(.xlsx)를 메모리 버퍼로 생성한다."""
        current_app.logger.info(f"Generating KPI report for branch '{branch}'...")
        head_sha = self.github.get_branch_head(branch)
        if not head_sha:
            current_app.logger.error(f"Could not retrieve HEAD for branch '{branch}'.")
            return None

        review_info = self.github.get_remote_file_content(head_sha, REVIEW_JSON_PATH)
        if not review_info or not review_info.get("content"):
            current_app.logger.error(f"Could not find or parse '{REVIEW_JSON_PATH}'.")
            return None

        all_rows = [row for item in review_info.get("content", []) for row in self._rows_for_review_item(item, head_sha, branch)]

        if not all_rows:
            current_app.logger.info("KPI 보고서를 생성할 데이터가 없습니다.")
            return None

        try:
            df = pd.DataFrame(all_rows)
            excel_buffer = create_excel_report_in_memory(df)
            current_app.logger.info("KPI report Excel file created successfully in memory.")
            return excel_buffer
        except Exception as e:
            current_app.logger.error(f"KPI Excel 보고서 생성 중 오류 발생: {e}")
            return None

    def _rows_for_review_item(self, review_item: dict, head_sha: str, branch: str) -> list[dict]:
        """단일 리뷰 항목에 대해 최초/현재 파일을 비교하여 KPI 행 목록을 만든다."""
        if not review_item.get("daily", False):
            return []

        file_path_from_review = review_item.get("path", "").replace("./", "")
        filename = review_item.get("filename", "")
        if not file_path_from_review or not filename:
            return []

        full_path = os.path.join("workspace", file_path_from_review, filename).replace("\\", "/")
        initial_commit_sha = self.github.find_commit_by_message(full_path, INITIAL_COMMIT_MESSAGE, branch)
        if not initial_commit_sha:
            return []

        initial_file_data = self.github.get_remote_file_content(initial_commit_sha, full_path)
        current_file_data = self.github.get_remote_file_content(head_sha, full_path)
        if not initial_file_data:
            return []

        initial_strings = self._parse_json_dynamically(initial_file_data.get("content", {}))
        current_strings_map = (
            {item["path"]: item["localized"] for item in self._parse_json_dynamically(current_file_data.get("content", {}))}
            if current_file_data
            else {}
        )

        info = initial_file_data.get("content", {}).get("info", {})
        rows = []
        for item in initial_strings:
            current_localized = current_strings_map.get(item["path"])
            fixed_localized = ""
            if current_localized is not None and current_localized != item["localized"]:
                fixed_localized = current_localized

            rows.append(
                {
                    "locale": info.get("locale", ""),
                    "version": info.get("version", ""),
                    "reference": info.get("reference", ""),
                    "skip_train": info.get("skip_train", False),
                    "file_path": review_item.get("path", "").lstrip("./"),
                    "filename": filename,
                    "root_key": item["root_key"],
                    "index": item["index"],
                    "path": item["path"],
                    "original": item["original"],
                    "localized": item["localized"],
                    "fixed": fixed_localized,
                    "tasked_by": review_item.get("tasked_by", ""),
                    "tasked_at": self._format_iso_date(review_item.get("tasked_at", "")),
                    "reviewed_by": review_item.get("reviewed_by", ""),
                    "reviewed_at": self._format_iso_date(review_item.get("reviewed_at", "")),
                    "comment": review_item.get("comment", ""),
                    "reporting": review_item.get("reporting", ""),
                }
            )
        return rows
