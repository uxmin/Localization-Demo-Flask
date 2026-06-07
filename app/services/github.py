import base64
import json
import logging
import os
import re
import zipfile
from datetime import datetime
from io import BytesIO
from typing import Any

import openpyxl
import requests
from flask import current_app


class GithubService:
    def __init__(self, token: str, repo_url_or_name: str) -> None:
        """
        GithubService를 초기화합니다.

        Args:
            token: GitHub Personal Access Token.
            repo_url_or_name: 'https://github.com/owner/repo' 형식의 URL 또는 'owner/repo' 형식의 이름.
        """
        self.headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        self.repo = self._extract_repo_name(repo_url_or_name)
        self.api_url = f"https://api.github.com/repos/{self.repo}"
        self.raw_content_url = f"https://raw.githubusercontent.com/{self.repo}"

    def _extract_repo_name(self, repo_url_or_name: str) -> str:
        """URL에서 'owner/repo' 부분을 추출합니다."""
        match = re.search(r"github\.com/([^/]+/[^/.]+)", repo_url_or_name)
        return match.group(1) if match else repo_url_or_name

    def _is_excluded_commit(self, author: str, message: str = "") -> bool:
        """집계에서 제외할 시스템/봇 커밋인지 판별한다(초기 업로드, 머지, 자동화 봇)."""
        return (
            message == "init"
            or message == "upload workfile"
            or message.startswith("Merge")
            or author.startswith("github-actions")
        )

    def _send_request(self, method: str, endpoint: str, **kwargs) -> Any | None:
        """GitHub API에 요청을 보내고 응답을 처리하는 중앙 헬퍼 메서드."""
        url = f"{self.api_url}/{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            # 내용이 없는 응답(e.g., 204 No Content)은 .json() 호출 시 에러가 발생하므로 확인
            if response.content:
                return response.json()
            return None  # 내용 없는 성공 응답
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                current_app.logger.error(f"리소스를 찾을 수 없습니다 (404): {url}")
            else:
                current_app.logger.error(f"HTTP 오류 발생: {e.response.status_code} {e.response.reason} for {url}")
                current_app.logger.error(f"응답 내용: {e.response.text}")
            return None
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"GitHub API 요청 실패: {e}")
            return None
        except json.JSONDecodeError:
            current_app.logger.error(f"JSON 파싱 실패: {url}")
            return None

    def _generate_review_json_content(self, zip_file_stream: BytesIO) -> str:
        """
        메모리 상의 ZIP 파일 스트림을 읽어 .review.json 파일의 내용을 생성합니다.
        제공된 셸 스크립트 로직을 Python으로 구현합니다.
        """
        current_app.logger.info("Generating .review.json content from ZIP stream...")
        review_items = []

        zip_file_stream.seek(0)  # 스트림 포인터를 처음으로 되돌림
        with zipfile.ZipFile(zip_file_stream, "r") as zipf:
            for item_info in zipf.infolist():
                # 디렉토리거나, 파일명이 .review.json이거나, .json으로 끝나지 않으면 건너뜀
                if (
                    item_info.is_dir()
                    or os.path.basename(item_info.filename) == ".review.json"
                    or not item_info.filename.lower().endswith(".json")
                ):
                    continue

                filename = os.path.basename(item_info.filename)
                # zip 파일 내의 상대 경로를 그대로 사용
                dirpath = os.path.dirname(item_info.filename)

                # 셸 스크립트의 relative_path 형식 맞추기
                relative_path = f"./{dirpath}" if dirpath else "./"
                # 경로 정규화 (e.g. ././ -> ./)
                relative_path = os.path.normpath(relative_path)

                review_item = {
                    "path": relative_path,
                    "filename": filename,
                    "task_done": False,
                    "tasked_by": "",
                    "tasked_at": "",
                    "review_done": False,
                    "reviewed_by": "",
                    "reviewed_at": "",
                    "comment": "",
                    "reporting": "",
                    "daily": "",
                }
                review_items.append(review_item)

        # path와 filename 기준으로 정렬 (셸 스크립트의 jq 역할)
        review_items.sort(key=lambda x: (x["path"], x["filename"]))

        current_app.logger.info(f"Generated {len(review_items)} items for .review.json")
        return json.dumps(review_items, indent=2, ensure_ascii=False)

    def _create_tree(self, branch: str, files_to_commit: list[dict]) -> str | None:
        """
        GitHub의 Git Trees API를 사용하여 여러 파일로부터 새로운 tree 객체를 생성합니다.

        Args:
            branch: 기준이 될 브랜치
            files_to_commit: [{'path': 'path/to/file', 'content': b'bytes content'}, ...] 형식의 리스트

        Returns:
            생성된 tree의 SHA, 실패 시 None
        """
        latest_commit_sha = self.get_branch_head(branch)
        if not latest_commit_sha:
            current_app.logger.error("Failed to get latest commit SHA for the base tree.")
            return None

        # 최신 커밋에서 base_tree의 SHA를 가져옴
        commit_data = self._send_request("GET", f"git/commits/{latest_commit_sha}")
        if not commit_data or "tree" not in commit_data:
            current_app.logger.error("Failed to get base tree SHA from the latest commit.")
            return None
        base_tree_sha = commit_data["tree"]["sha"]

        tree = []
        for file_info in files_to_commit:
            try:
                tree.append(
                    {
                        "path": file_info["path"],
                        "mode": "100644",  # 일반 파일
                        "type": "blob",
                        "content": file_info["content"].decode("utf-8"),  # content는 문자열이어야 함
                    }
                )
            except UnicodeDecodeError:
                current_app.logger.error(
                    f"파일 디코딩 실패: '{file_info['path']}'. "
                    f"이 파일은 바이너리 파일이거나 UTF-8 인코딩이 아닌 것 같습니다. "
                    f"tree 생성을 중단합니다."
                )
                return None

        payload = {"base_tree": base_tree_sha, "tree": tree}
        tree_data = self._send_request("POST", "git/trees", json=payload)

        if tree_data and "sha" in tree_data:
            current_app.logger.info(f"Successfully created a new tree with SHA: {tree_data['sha']}")
            return tree_data["sha"]
        else:
            current_app.logger.error("Failed to create a new git tree.")
            return None

    def get_branch_head(self, branch: str) -> str | None:
        """지정된 브랜치의 마지막 커밋 SHA를 가져옵니다."""
        data = self._send_request("GET", f"branches/{branch}")
        if data and "commit" in data and "sha" in data["commit"]:
            return data["commit"]["sha"]
        current_app.logger.warning(f"'{branch}' 브랜치의 HEAD 커밋 SHA를 찾지 못했습니다.")
        return None

    def get_root_commit(self, branch: str):
        """지정된 브랜치의 최초 커밋 SHA를 가져옵니다."""
        current_app.logger.info(f"'{branch}' 브랜치의 최초 커밋을 찾는 중...")
        endpoint = "commits"
        params = {"sha": branch, "per_page": 1}

        try:
            response = requests.head(f"{self.api_url}/{endpoint}", headers=self.headers, params=params)
            response.raise_for_status()
            last_page = 1
            if "link" in response.headers:
                links = response.headers["link"].split(",")
                for link in links:
                    if 'rel="last"' in link:
                        match = re.search(r"page=(\d+)", link)
                        if match:
                            last_page = int(match.group(1))
                        break

            current_app.logger.info(f"계산된 마지막 페이지: {last_page}")
        except requests.exceptions.RequestException as e:
            current_app.logger.error(f"최초 커밋 조회 중 마지막 페이지 확인 실패: {e}")
            return None

        for page in range(last_page, 0, -1):
            current_app.logger.info(f"-> 페이지 {page} 확인 중...")
            page_params = {"sha": branch, "per_page": 100, "page": page}
            commits_on_page = self._send_request("GET", endpoint, params=page_params)

            if commits_on_page:
                root_commit_sha = commits_on_page[-1]["sha"]
                current_app.logger.info(f"최초 커밋 발견 (페이지 {page}에서): {root_commit_sha[:7]}")
                return root_commit_sha

            current_app.logger.info(f"   페이지 {page}가 비어있어 이전 페이지를 확인합니다.")

        current_app.logger.error(f"'{branch}' 브랜치에서 유효한 커밋을 찾지 못했습니다.")
        return None

    def get_remote_file_content(self, branch: str, path: str) -> dict[str, Any] | None:
        """원격 GitHub 저장소에서 폴더 또는 파일의 내용과 SHA를 가져옵니다."""
        path = path.lstrip("/")
        data = self._send_request("GET", f"contents/{path}", params={"ref": branch})
        if data is None:
            return None

        if isinstance(data, dict) and "content" in data:
            # 📄 파일인 경우
            try:
                content_str = base64.b64decode(data["content"]).decode("utf-8")
                content: Any = content_str
                if path.lower().endswith(".json"):
                    try:
                        content = json.loads(content_str)
                    except json.JSONDecodeError:
                        current_app.logger.warning(f"'{path}'는 JSON 파일이지만 파싱에 실패. 문자열로 반환합니다.")
                return {"type": "file", "content": content, "sha": data["sha"], "path": path}
            except (UnicodeDecodeError, TypeError) as e:
                current_app.logger.error(f"파일 콘텐츠 디코딩 실패: {path}, 오류: {e}")

        elif isinstance(data, list):
            # 📂 디렉토리인 경우
            items = [{"name": item["name"], "path": item["path"], "type": item["type"]} for item in data]
            return {"type": "dir", "items": items, "path": path}
        else:
            current_app.logger.warning(f"'{path}'에서 예상치 못한 응답 형식을 받았습니다.")
            return None

    def get_branch_commits(self, branch: str, per_page: int = 30) -> list[dict[str, Any]]:
        """지정된 브랜치의 최근 커밋 목록을 가져옵니다."""

        commits_data = self._send_request("GET", "commits", params={"sha": branch, "per_page": per_page})
        if not commits_data:
            return []

        return [
            {
                "message": c["commit"]["message"],
                "author": c["commit"]["author"]["name"],
                "committed_at": datetime.strptime(c["commit"]["author"]["date"], "%Y-%m-%dT%H:%M:%SZ"),
                "sha": c["sha"][:7],
            }
            for c in commits_data
            if c.get("commit", {}).get("author")
            and not self._is_excluded_commit(c["commit"]["author"]["name"], c["commit"]["message"])
        ]

    def get_changed_files(self, base_sha: str, head_sha: str) -> set[str]:
        """두 커밋 사이의 모든 변경된 파일 목록을 Set 형태로 반환합니다."""
        current_app.logger.info(f"커밋 간 변경된 파일 목록 조회: {base_sha[:7]}...{head_sha[:7]}")
        changed_files = set()
        page = 1
        while True:
            # API는 페이지당 최대 250개의 파일 변경사항을 반환합니다.
            params = {"per_page": 250, "page": page}
            data = self._send_request("GET", f"compare/{base_sha}...{head_sha}", params=params)

            if data is None:  # API 요청 실패
                return set()

            files_on_page = [file["filename"] for file in data.get("files", [])]
            if not files_on_page:
                break

            changed_files.update(files_on_page)
            if len(files_on_page) < 250:
                break
            page += 1

        current_app.logger.info(f"총 {len(changed_files)}개의 파일 변경사항을 감지했습니다.")
        return changed_files

    def filter_review_data(self, review_data: list[dict[str, Any]], dwn_type: str) -> list[dict[str, Any]]:
        """
        메모리에 있는 리뷰 데이터(dict 리스트)를 조건에 맞게 필터링합니다.

        Args:
            review_data: 파싱된 .review.json 파일의 내용 (dict의 리스트).
        """

        if dwn_type != "delivered-data":
            filtered_list = [
                item
                for item in review_data
                if item.get("task_done") is True
                and item.get("tasked_by")
                and item.get("tasked_at")
                and item.get("review_done") is True
                and item.get("reviewed_by")
                and item.get("reviewed_at")
                and not item.get("daily", False)
            ]
        else:
            filtered_list = [item for item in review_data if item.get("daily", False) is True]

        current_app.logger.info(
            f"필터링 완료: 총 {len(review_data)}개 중 {len(filtered_list)}개 항목이 조건에 맞습니다."
        )
        return filtered_list

    def update_and_commit_review_file(
        self,
        original_data: list[dict],
        updated_items: list[dict],
        file_path: str,
        sha: str,
        branch: str,
    ) -> bool:
        """
        .review.json의 내용을 업데이트하고 원격 저장소에 커밋합니다.
        """
        if not updated_items:
            current_app.logger.info("업데이트할 항목이 없어 커밋을 건너뜁니다.")
            return True  # 업데이트 할 것이 없는 것도 성공으로 간주

        current_app.logger.info("'.review.json' 파일 업데이트 및 커밋 시작...")

        # 순서 보존을 위해 원본 데이터(리스트)를 직접 수정
        # 어떤 항목을 업데이트해야 하는지 빠르게 찾기 위해 set 사용
        update_keys = {(item["path"], item["filename"]) for item in updated_items}

        update_count = 0
        for item in original_data:
            if (item["path"], item["filename"]) in update_keys:
                item["daily"] = True
                update_count += 1

        if update_count == 0:
            current_app.logger.warning("업데이트 대상 항목이 원본 데이터에 존재하지 않습니다.")
            return False

        updated_content_str = json.dumps(original_data, indent=2, ensure_ascii=False)
        encoded_content = base64.b64encode(updated_content_str.encode("utf-8")).decode("utf-8")

        # 커밋 메시지 생성
        commit_message = f"chore: Update review status for {update_count} daily exported items"
        # API 페이로드 구성
        payload = {
            "message": commit_message,
            "content": encoded_content,
            "sha": sha,  # 파일 수정을 위해서는 이전 파일의 SHA가 필수
            "branch": branch,
        }

        result = self._send_request("PUT", f"contents/{file_path}", json=payload)
        if result and "commit" in result:
            current_app.logger.info(f"성공: '{file_path}' 파일이 업데이트되었습니다.")
            current_app.logger.info(f"  - 커밋 메시지: {commit_message}")
            current_app.logger.info(f"  - 새 커밋 SHA: {result['commit']['sha']}")
            return True
        else:
            current_app.logger.error(f"'{file_path}' 파일 업데이트 및 커밋에 실패했습니다.")
            return False

    def create_zip_from_remote(
        self,
        root_path: str,
        items_to_zip: list[dict],
        branch: str,
    ) -> tuple[BytesIO | None, list[dict]]:
        """
        원격 파일들을 다운로드하여 메모리상에서 ZIP 아카이브를 생성하고,
        (BytesIO, 성공적으로 압축된 항목들 리스트)를 반환합니다.
        """
        if not items_to_zip:
            current_app.logger.info("압축할 파일이 없습니다. ZIP 파일 생성을 건너뜁니다.")
            return None, []

        successfully_archived_items = []
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for item in items_to_zip:
                # `lstrip`으로 경로 시작의 './' 또는 '/' 제거
                file_path_in_repo = f"{root_path.lstrip('/')}/{item["path"].lstrip("./")}/{item['filename']}"
                url = f"{self.raw_content_url}/{branch}/{file_path_in_repo}"

                try:
                    # Raw 파일 다운로드는 API가 아닌 raw content URL을 직접 사용
                    response = requests.get(url, headers={"Authorization": self.headers["Authorization"]})
                    response.raise_for_status()

                    arcname = os.path.join(item["path"].lstrip("./"), item["filename"])
                    zipf.writestr(arcname, response.content)
                    current_app.logger.info(f"  - 추가됨: {arcname}")
                    successfully_archived_items.append(item)
                except requests.exceptions.RequestException as e:
                    current_app.logger.warning(f"  - [경고] 파일 다운로드 실패: {file_path_in_repo}, 오류: {e}")

        zip_buffer.seek(0)
        return zip_buffer, successfully_archived_items

    def find_commit_by_message(self, file_path: str, target_message: str, branch: str) -> str | None:
        """
        특정 파일의 히스토리에서, 지정된 메시지를 포함하는 가장 최신 커밋의 SHA를 찾습니다.

        GitHub API는 최신 커밋부터 반환하므로, 처음 발견되는 커밋이 가장 최신입니다.

        Args:
            file_path: 커밋 히스토리를 조회할 파일의 경로.
            target_message: 찾고자 하는 커밋 메시지의 일부 또는 전체.
            branch: 검색을 수행할 브랜치 이름.

        Returns:
            조건에 맞는 가장 최신 커밋의 전체 SHA 문자열. 찾지 못하면 None을 반환합니다.
        """
        current_app.logger.info(
            f"'{file_path}' 파일 히스토리에서 '{target_message}' 메시지가 포함된 커밋 검색 시작 (브랜치: {branch})"
        )
        page = 1
        while True:
            params = {"path": file_path, "sha": branch, "page": page, "per_page": 100}
            # 중앙 요청 헬퍼를 사용하여 API 호출 및 기본 오류 처리
            commits = self._send_request("GET", "commits", params=params)

            # 응답이 없거나 (페이지 끝), API 요청이 실패한 경우 루프 종료
            if not commits:
                break

            for commit in commits:
                commit_details = commit.get("commit", {})
                commit_message = commit_details.get("message", "")

                # 디버그 레벨에서 각 커밋 정보 로깅 (평소에는 출력되지 않음)
                if current_app.logger.isEnabledFor(logging.DEBUG):
                    sha = commit.get("sha", "N/A")
                    author = commit_details.get("author", {}).get("name", "N/A")
                    date_str = commit_details.get("author", {}).get("date", "")
                    try:
                        date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        formatted_date = date_obj.strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        formatted_date = "N/A"

                    current_app.logger.debug(
                        f"  - 검사 중: SHA={sha[:7]}, Date={formatted_date}, Author={author}, Msg='{commit_message.splitlines()[0]}'"
                    )

                if target_message in commit_message:
                    found_sha = commit["sha"]
                    current_app.logger.info(
                        f"  -> 기준 커밋 발견: {found_sha[:7]} - '{commit_message.splitlines()[0]}'"
                    )
                    return found_sha

            page += 1

        current_app.logger.warning(f"'{file_path}' 파일에서 '{target_message}' 메시지를 가진 커밋을 찾지 못했습니다.")
        return None

    def upload_zip_and_create_review(
        self,
        branch: str,
        root_path: str,
        zip_file_stream: BytesIO,
        commit_message: str,
    ) -> bool:
        """
        메모리 상의 ZIP 파일을 처리하여 여러 파일을 단일 커밋으로 GitHub에 업로드합니다.
        """
        # 1. .review.json 내용 생성
        review_json_content_str = self._generate_review_json_content(zip_file_stream)
        review_file_path_in_repo = os.path.join("result", ".review.json").replace("\\", "/")

        files_to_commit = [{"path": review_file_path_in_repo, "content": review_json_content_str.encode("utf-8")}]

        # 2. ZIP 파일의 압축을 풀며 커밋할 파일 목록 생성
        current_app.logger.info("Preparing files from ZIP for commit...")
        zip_file_stream.seek(0)
        with zipfile.ZipFile(zip_file_stream, "r") as zipf:
            for item_info in zipf.infolist():
                if item_info.is_dir():
                    continue

                content_bytes = zipf.read(item_info.filename)
                file_path_in_repo = os.path.join(root_path, item_info.filename).replace("\\", "/")

                files_to_commit.append({"path": file_path_in_repo, "content": content_bytes})

        current_app.logger.info(f"A total of {len(files_to_commit)} files will be committed.")

        # 4. 새 커밋 생성
        parent_sha = self.get_branch_head(branch)
        if not parent_sha:
            base_branch = "main"
            base_sha = self.get_branch_head(base_branch)
            if not base_sha:
                current_app.logger.error(f"Base branch '{base_branch}' not found.")
                return False

            create_branch_payload = {
                "ref": f"refs/heads/{branch}",
                "sha": base_sha,
            }
            create_resp = self._send_request("POST", "git/refs", json=create_branch_payload)
            if not create_resp or "ref" not in create_resp:
                current_app.logger.error(f"Failed to create {branch} branch from main.")
                return False

            current_app.logger.info(f"Created new '{branch}' branch from 'main'")
            # 다시 head SHA 가져오기
            parent_sha = self.get_branch_head(branch)

        # 3. Git Tree 생성
        new_tree_sha = self._create_tree(branch, files_to_commit)
        if not new_tree_sha:
            return False

        commit_payload = {"message": commit_message, "tree": new_tree_sha, "parents": [parent_sha]}
        commit_data = self._send_request("POST", "git/commits", json=commit_payload)
        if not commit_data or "sha" not in commit_data:
            current_app.logger.error("Failed to create a new commit object.")
            return False
        new_commit_sha = commit_data["sha"]
        current_app.logger.info(f"Successfully created a new commit with SHA: {new_commit_sha}")

        # 5. 브랜치 참조(ref) 업데이트
        ref_update_payload = {"sha": new_commit_sha}
        update_result = self._send_request("PATCH", f"git/refs/heads/{branch}", json=ref_update_payload)

        if update_result and "object" in update_result and update_result["object"]["sha"] == new_commit_sha:
            current_app.logger.info(f"Successfully updated branch '{branch}' to point to the new commit.")
            return True
        else:
            current_app.logger.error(f"Failed to update the branch '{branch}' reference.")
            return False

    def create_xlsx_from_review_data(self, review_data: list[dict]) -> BytesIO | None:
        """
        .review.json 데이터 (dict 리스트)를 기반으로 메모리 상에서 .xlsx 파일을 생성합니다.

        Args:
            review_data: .review.json 파일의 내용 (dict의 리스트).

        Returns:
            .xlsx 파일 데이터가 담긴 BytesIO 스트림, 데이터가 없으면 None.
        """
        if not review_data:
            current_app.logger.warning("No data provided to create an Excel file.")
            return None

        current_app.logger.info(f"Creating Excel file from {len(review_data)} review items.")

        # 1. 메모리 버퍼와 새 워크북 생성
        output_buffer = BytesIO()
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        if sheet is not None:
            sheet.title = "WorkList"
        else:
            current_app.logger.error("Failed to get active sheet from workbook.")
            return None

        # 2. 헤더 행 추가
        headers = ["filePath", "fileName", "Worker"]
        sheet.append(headers)

        # 3. 데이터 행 추가
        # .review.json의 키를 기반으로 데이터를 매핑합니다.
        for item in review_data:
            row = [
                item.get("path", ""),  # filePath
                item.get("filename", ""),  # fileName
                "",  # Worker
            ]
            sheet.append(row)

        # 4. 워크북을 메모리 버퍼에 저장
        workbook.save(output_buffer)
        output_buffer.seek(0)  # 스트림의 포인터를 처음으로 되돌려 나중에 읽을 수 있도록 함

        current_app.logger.info("Excel file created successfully in memory.")
        return output_buffer

    def find_all_commits_by_message(self, branch: str, target_message: str) -> list[dict]:
        """
        지정된 브랜치의 전체 히스토리에서 특정 메시지를 포함하는 모든 커밋을 찾아
        날짜가 오래된 순으로 정렬하여 반환합니다.
        """
        current_app.logger.info(f"'{branch}' 브랜치에서 '{target_message}' 메시지가 포함된 커밋을 검색합니다...")
        matching_commits = []
        page = 1
        while True:
            params = {"sha": branch, "page": page, "per_page": 100}
            commits = self._send_request("GET", "commits", params=params)
            if not commits:
                break

            for commit in commits:
                if target_message in commit.get("commit", {}).get("message", ""):
                    matching_commits.append(
                        {
                            "sha": commit["sha"],
                            "date": commit.get("commit", {}).get("author", {}).get("date"),
                        }
                    )

            if len(commits) < 100:
                break
            page += 1

        # 날짜(오래된 순) 기준으로 정렬하여 반환
        matching_commits.sort(key=lambda x: x["date"])
        current_app.logger.info(f"총 {len(matching_commits)}개의 일치하는 커밋을 찾았습니다.")
        return matching_commits

    def get_all_json_files_in_path(self, sha: str, path: str) -> list[dict]:
        """
        특정 커밋(sha)의 지정된 경로(path) 하위에 있는 모든 JSON 파일의 내용과 상대 경로를
        Git Trees API를 사용하여 재귀적으로 가져옵니다.

        Args:
            sha: 커밋 SHA
            path: 탐색을 시작할 리포지토리 내 경로 (e.g., "workspace/작업폴더1")

        Returns:
            [{'path': '상대경로/a.json', 'content': b'...'}] 형태의 리스트
        """
        path = path.strip("/")
        all_files = []
        current_app.logger.info(f"'{path}' 경로에서 JSON 파일을 탐색합니다 (커밋: {sha[:7]})...")

        commit_data = self._send_request("GET", f"git/commits/{sha}")
        if not commit_data or "tree" not in commit_data:
            current_app.logger.error(f"커밋 {sha}의 tree SHA를 가져올 수 없습니다.")
            return []
        tree_sha = commit_data["tree"]["sha"]

        tree_data = self._send_request("GET", f"git/trees/{tree_sha}?recursive=1")
        if not tree_data or "tree" not in tree_data:
            current_app.logger.error(f"tree SHA {tree_sha}의 재귀적 tree 정보를 가져올 수 없습니다.")
            return []

        for item in tree_data["tree"]:
            item_path = item["path"]
            if item["type"] == "blob" and item_path.startswith(path + "/") and item_path.lower().endswith(".json"):
                blob_data = self._send_request("GET", f"git/blobs/{item['sha']}")
                if blob_data and "content" in blob_data:
                    content_bytes = base64.b64decode(blob_data["content"])
                    relative_path = os.path.relpath(item_path, start=path).replace("\\", "/")
                    all_files.append({"path": relative_path, "content": content_bytes})

        current_app.logger.info(f"경로 '{path}'에서 총 {len(all_files)}개의 JSON 파일을 찾았습니다.")
        return all_files
