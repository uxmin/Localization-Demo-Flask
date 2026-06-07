import json
import os
from datetime import datetime
from io import BytesIO

from flask import Blueprint, current_app, jsonify, request, send_file
from werkzeug.datastructures import FileStorage

from app.schemas.error import ErrorCode
from app.schemas.response import Response
from app.services.aws import S3Helper
from app.services.github import GithubService
from app.services.kpi import KpiService
from app.utils.etc import (
    handle_exceptions,
    replace_words_with_O_case_insensitive,
    require_json_body,
    split_json_and_text,
)
from app.utils.openai import call_model, get_model, get_model_list, get_template

bp_external = Blueprint("external", __name__, url_prefix="/demo/external")
REVIEW_JSON_PATH = "result/.review.json"


def _get_github_service(data: dict) -> GithubService:
    """요청 데이터에서 repo_url을 가져와 GithubService 인스턴스를 생성하는 헬퍼 함수"""
    repo_url = data.get("repo_url")
    if not repo_url:
        raise ValueError("repo_url is required")
    return GithubService(current_app.config.get("GITHUB_TOKEN", ""), repo_url)


@bp_external.route("/openai", methods=["POST"])
@require_json_body
@handle_exceptions
def prompt(data: dict):
    words_to_replace = current_app.config.get("SECURITY_KEYWORDS", [])
    refined_data = replace_words_with_O_case_insensitive(json.dumps(data, ensure_ascii=False), words_to_replace)

    data = request.get_json()
    if not data:
        return jsonify(Response().error_response(ErrorCode.INVALID_INPUT).model_dump())

    prompt_template = get_template("translation")
    formatted_prompt = prompt_template.format_prompt(
        input_language="Korean", output_language="Korean", user_input=refined_data
    )

    model, _ = get_model(is_json=False)
    chain = prompt_template | model
    response = chain.invoke(formatted_prompt)

    try:
        json_str, text_str = split_json_and_text(response.content)
        parsed_json = json.loads(json_str)
    except json.JSONDecodeError as jde:
        current_app.logger.error(f"Failed to parse JSON from model response: {jde}")
        return jsonify(Response().error_response(ErrorCode.INVALID_JSON_FORMAT).model_dump())

    return jsonify(Response().successful_response({"analyze": text_str, "translation": parsed_json}).model_dump())


@bp_external.route("/models", methods=["GET"])
@handle_exceptions
def get_models():
    models = get_model_list()
    return jsonify(Response().successful_response({"models": models}).model_dump())


@bp_external.route("/call-llm", methods=["POST"])
@require_json_body
@handle_exceptions
def call_llm(data: dict):
    api_key = data.get("api_key", "")
    system_prompt = data.get("system_prompt", "")
    user_prompt = data.get("user_prompt", "")
    model_name = data.get("model_name", "gpt-4o-mini")
    try:
        response = call_model(api_key, model_name, system_prompt, user_prompt)
        return jsonify(Response().successful_response({"response": response}).model_dump())
    except ValueError as ve:
        err_str = str(ve).lower()
        if "empty" in err_str:
            return jsonify(Response().error_response(ErrorCode.EMPTY_RESPONSE).model_dump())
        elif "invalid api key" in err_str:
            return jsonify(Response().error_response(ErrorCode.INVALID_API_KEY).model_dump())
        raise


@bp_external.route("/lookup-repo", methods=["POST"])
@require_json_body
@handle_exceptions
def lookup_repo(data: dict):
    branch = data.get("branch", "develop")
    path = data.get("path", "/workspace")
    git_service = _get_github_service(data)

    # 1. 디렉토리 정보 조회
    dir_result = git_service.get_remote_file_content(branch, path)
    if not dir_result:
        return jsonify(Response().successful_response({"response": "Not Found Repo"}).model_dump())

    response = {}
    if dir_result.get("type") == "dir" and dir_result.get("items"):
        response["items"] = [item.get("name") for item in dir_result.get("items", [])]

    # Review 조회
    review_result: dict | None = git_service.get_remote_file_content(branch, REVIEW_JSON_PATH)
    if not review_result or "content" not in review_result:
        return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

    reviews = review_result.get("content", [])
    response.update(
        {
            "task_done": sum(1 for r in reviews if r.get("task_done")),
            "review_done": sum(1 for r in reviews if r.get("review_done")),
            "total_done": sum(1 for r in reviews if r.get("task_done") and r.get("review_done")),
            "total": len(reviews),
        }
    )

    # 커밋 이력 조회
    response["commits"] = git_service.get_branch_commits(branch)
    return jsonify(Response().successful_response({"response": response}).model_dump())


@bp_external.route("/lookup-commit", methods=["POST"])
@require_json_body
@handle_exceptions
def lookup_commit(data: dict):
    git_service = _get_github_service(data)
    branch = data.get("branch", "develop")

    response = {}
    # Review 조회
    review_result: dict | None = git_service.get_remote_file_content(branch, REVIEW_JSON_PATH)
    if not review_result or "content" not in review_result:
        return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

    reviews = review_result.get("content", [])
    response.update(
        {
            "task_done": sum(1 for r in reviews if r.get("task_done")),
            "review_done": sum(1 for r in reviews if r.get("review_done")),
            "total_done": sum(1 for r in reviews if r.get("task_done") and r.get("review_done")),
            "total": len(reviews),
        }
    )

    response["commits"] = git_service.get_branch_commits(branch)
    return jsonify(Response().successful_response({"response": response}).model_dump())


@bp_external.route("/download-xlsx", methods=["POST"])
@require_json_body
@handle_exceptions
def download_xlsx(data: dict):
    branch = data.get("branch", "develop")
    git_service = _get_github_service(data)

    review_file_path = os.path.join(REVIEW_JSON_PATH).replace("\\", "/")
    current_app.logger.info(f"Fetching '{review_file_path}' from branch '{branch}'...")
    review_file_data = git_service.get_remote_file_content(branch, review_file_path)

    if not review_file_data or review_file_data.get("type") != "file":
        error_msg = f"'{review_file_path}' not found in branch '{branch}'."
        current_app.logger.error(error_msg)
        return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

    excel_buffer = git_service.create_xlsx_from_review_data(review_file_data["content"])
    if not excel_buffer:
        # 데이터가 비어있어 Excel 파일을 생성할 수 없는 경우
        return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

    return send_file(
        excel_buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="workfile.xlsx",  # 다운로드될 파일명
    )


@bp_external.route("/download-workfile", methods=["POST"])
@require_json_body
@handle_exceptions
def download_workfile(data: dict):
    git_service = _get_github_service(data)
    branch = data.get("branch", "develop")
    path = data.get("path", "/workspace")
    dwn_type = data.get("data_type", "delivered-data")

    # 1. 커밋 범위(최초-최신) 조회
    head_sha = git_service.get_branch_head(branch)
    root_sha = git_service.get_root_commit(branch)
    if not head_sha or not root_sha:
        current_app.logger.warning("Could not retrieve commit range for branch.")
        return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

    # 2. 변경된 파일 목록 조회
    changed_files_set = git_service.get_changed_files(root_sha, head_sha)
    if not changed_files_set:
        current_app.logger.info("감지된 파일 변경사항이 없습니다. 프로세스를 종료합니다.")
        return jsonify(Response().successful_response({"message": "변경 이력이 없습니다."}).model_dump())

    # 3. .review.json 파일 조회
    review_file: dict | None = git_service.get_remote_file_content(branch, REVIEW_JSON_PATH)
    if not review_file or not review_file.get("content") or not review_file.get("sha"):
        return jsonify(Response().error_response(ErrorCode.EXTERNAL_SERVICE_ERROR).model_dump())

    # 4. 리뷰 완료된 데이터 필터링
    items_to_process = git_service.filter_review_data(review_file["content"], dwn_type)

    # 6. ZIP 파일 생성
    zip_buffer, archived_items = git_service.create_zip_from_remote(path, items_to_process, branch)
    if not archived_items:
        current_app.logger.warning("No files were successfully archived, skipping commit.")
        return jsonify(Response().successful_response({"message": "변경 이력이 없습니다."}).model_dump())

    if dwn_type != "delivered-data":
        # 7. .review.json 상태 업데이트 및 커밋
        git_service.update_and_commit_review_file(
            original_data=review_file["content"],
            updated_items=archived_items,
            file_path=REVIEW_JSON_PATH,
            sha=review_file["sha"],
            branch=branch,
        )

    # 8. ZIP 파일 전송
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"review_export_{timestamp}_{head_sha[:7]}.zip"
    if zip_buffer is None:
        current_app.logger.error("zip_buffer is None, cannot send file.")
        return jsonify(Response().error_response(ErrorCode.EXTERNAL_SERVICE_ERROR).model_dump())

    return send_file(zip_buffer, mimetype="application/zip", as_attachment=True, download_name=zip_filename)


@bp_external.route("/download-kpi", methods=["POST"])
@require_json_body
@handle_exceptions
def download_kpi(data: dict):
    git_service = _get_github_service(data)
    branch = data.get("branch", "develop")
    excel_buffer = KpiService(git_service).build_kpi_excel(branch)

    if not excel_buffer:
        # build_kpi_excel 내부에서 이미 로깅이 수행됨
        return jsonify(Response().error_response(ErrorCode.KPI_DATA_NOT_FOUND).model_dump())

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"KPI_Report_{timestamp}.xlsx"
    return send_file(
        excel_buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@bp_external.route("/upload-workfile", methods=["POST"])
@handle_exceptions
def upload_workfile():
    current_app.logger.info("Received request for /upload-workfile")

    workfile: FileStorage | None = request.files.get("workfile")
    if not workfile:
        return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

    repo_url = request.form.get("repo_url")
    branch = request.form.get("branch", "develop")
    root_path_in_repo = request.form.get("path", "").strip("/")
    if not all([repo_url, branch, root_path_in_repo]):
        return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

    data = {"repo_url": repo_url, "branch": branch, "path": root_path_in_repo}
    git_service = _get_github_service(data)

    current_app.logger.info(f"\tReceived file: {workfile.filename}")
    current_app.logger.info(f"\tForm data: repo_url={repo_url}, branch={branch}, path={root_path_in_repo}")
    current_app.logger.info(f"\tgit_service: {git_service}")

    zip_file_stream = BytesIO(workfile.read())
    commit_message = "upload workfile"
    success = git_service.upload_zip_and_create_review(
        branch=branch,
        root_path=root_path_in_repo,
        zip_file_stream=zip_file_stream,
        commit_message=commit_message,
    )

    if success:
        return jsonify(Response().successful_response().model_dump())
    else:
        return jsonify(Response().error_response(ErrorCode.INTERNAL_SERVER_ERROR).model_dump())


@bp_external.route("/s3-upload-from-commits", methods=["POST"])
@require_json_body
@handle_exceptions
def upload_kpi_and_jsons_to_s3(data: dict):
    """
    'upload workfile' 커밋을 기준으로 최초/최종 JSON 파일들과 KPI 보고서를 S3에 업로드합니다.
    """
    # 1. 요청 파라미터 추출
    repo_url = data.get("repo_url")
    branch = data.get("branch", "develop")
    work_folder_name = data.get("work_folder_name", "test")
    bucket_name = current_app.config.get(
        "AWS_S3_BUCKET_NAME", ""
    )  # S3 버킷 이름은 Flask config에 설정되어 있어야 합니다.

    if not all([repo_url, work_folder_name, bucket_name]):
        return jsonify(Response().error_response(ErrorCode.INVALID_INPUT).model_dump())

    # 2. 서비스 초기화
    git_service = _get_github_service(data)
    s3_helper = S3Helper()

    today_str = datetime.now().strftime("%y%m%d")
    aws_work_folder_name = f"{today_str}_{work_folder_name}"

    # 폴더 초기화
    try:
        current_app.logger.info(f"S3의 기존 폴더 '{aws_work_folder_name}' 내용 삭제를 시작합니다.")
        s3_helper.delete_folder(bucket_name=bucket_name, folder_prefix=aws_work_folder_name)
        current_app.logger.info(f"기존 폴더 '{aws_work_folder_name}' 내용 삭제 완료.")
    except Exception as e:
        # 삭제 실패 시 프로세스를 중단하고 에러를 반환합니다.
        current_app.logger.error(f"S3 폴더 삭제 실패: {e}")
        return jsonify(Response().error_response(ErrorCode.EXTERNAL_SERVICE_ERROR).model_dump())

    # 3. 'upload workfile' 메시지를 가진 첫 커밋과 브랜치의 마지막 커밋 조회
    upload_commits = git_service.find_all_commits_by_message(branch, "upload workfile")
    if not upload_commits:
        # "'upload workfile' 메시지를 가진 커밋을 찾을 수 없습니다."
        return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

    first_commit_sha = upload_commits[0]["sha"]
    last_commit_sha = git_service.get_branch_head(branch)
    if not last_commit_sha:
        # "브랜치의 마지막 커밋을 조회할 수 없습니다."
        return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

    current_app.logger.info(f"기준 커밋: 최초='{first_commit_sha[:7]}', 최종='{last_commit_sha[:7]}'")

    # 4. 각 커밋 시점의 JSON 파일 목록 및 내용 조회
    base_path_in_repo = f"workspace/{work_folder_name}"
    initial_json_files = git_service.get_all_json_files_in_path(first_commit_sha, base_path_in_repo)
    final_json_files = git_service.get_all_json_files_in_path(last_commit_sha, base_path_in_repo)

    # 5. KPI 보고서 생성
    kpi_excel_buffer = KpiService(git_service).build_kpi_excel(branch)

    # 6. S3 업로드
    upload_results = {}

    # 6-1. KPI 보고서 업로드
    if kpi_excel_buffer:
        s3_url = s3_helper.upload_file(
            bucket_name=bucket_name,
            file_content=kpi_excel_buffer.getvalue(),
            upload_path=[aws_work_folder_name],
            file_name="kpi",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        upload_results["kpi_report_url"] = s3_url
        current_app.logger.info(f"KPI 보고서 업로드 완료: {s3_url}")

    # 6-2. 최초 커밋의 JSON 파일('원본폴더') 업로드
    initial_urls = []
    for file_info in initial_json_files:
        path_parts = file_info["path"].split("/")
        file_name = path_parts.pop()
        s3_path = [aws_work_folder_name, "source"] + path_parts
        s3_url = s3_helper.upload_file(
            bucket_name=bucket_name,
            file_content=file_info["content"],
            upload_path=s3_path,
            file_name=file_name,
            content_type="application/json",
        )
        initial_urls.append(s3_url)
    upload_results["initial_files_urls"] = initial_urls
    current_app.logger.info(f"원본 파일 {len(initial_urls)}개 업로드 완료.")

    # 6-3. 최종 커밋의 JSON 파일('작업폴더') 업로드
    final_urls = []
    for file_info in final_json_files:
        path_parts = file_info["path"].split("/")
        file_name = path_parts.pop()
        s3_path = [aws_work_folder_name, "work"] + path_parts
        s3_url = s3_helper.upload_file(
            bucket_name=bucket_name,
            file_content=file_info["content"],
            upload_path=s3_path,
            file_name=file_name,
            content_type="application/json",
        )
        final_urls.append(s3_url)
    upload_results["final_files_urls"] = final_urls
    current_app.logger.info(f"작업 파일 {len(final_urls)}개 업로드 완료.")

    # 7. 결과 반환
    return jsonify(Response().successful_response(upload_results).model_dump())
