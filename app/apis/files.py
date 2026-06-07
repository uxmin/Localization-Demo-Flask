import json
import traceback
from io import BytesIO

import pandas as pd
from flask import (
    Blueprint,
    current_app,
    jsonify,
    request,
    send_file,
)

from app.schemas.error import ErrorCode
from app.schemas.response import Response
from app.services.files import (
    apply_changes_and_download_service,
    check_validate_json_service,
    convert_excel_to_json,
    convert_json_to_xlsx,
    create_excel_from_dataframe,
    extract_and_download_service,
    extract_excel_columns,
    get_keys_service,
    read_json_file_list,
    remove_keys_service,
)
from app.tasks.files import process_items_task

bp_file = Blueprint("file", __name__, url_prefix="/demo/file")
DEFAULT_COLUMNS = ["file_path", "filename", "root_key", "index", "path", "original", "localized"]


@bp_file.route("/extract-columns", methods=["POST"])
def extract_columns():
    try:
        excel_file = request.files.get("excel_file")
        if not excel_file:
            return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

        columns = extract_excel_columns(excel_file)
        return jsonify(Response().successful_response({"columns": columns}).model_dump())
    except Exception as e:
        current_app.logger.error(f"Error processing Excel file: {str(e)}")
        return jsonify(Response().error_response(ErrorCode.INTERNAL_SERVER_ERROR).model_dump())


@bp_file.route("/extract-and-download", methods=["POST"])
def extract_and_download():
    try:
        header = request.form.get("header")
        excel_file = request.files.get("excel_file")
        archive_file = request.files.get("archive_file")
        if not archive_file or not header:
            return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

        zip_path = extract_and_download_service(header, excel_file, archive_file)
        return send_file(zip_path, as_attachment=True)
    except Exception as e:
        current_app.logger.error(f"Error: {str(e)}")
        return jsonify(Response().error_response(ErrorCode.INTERNAL_SERVER_ERROR).model_dump())


@bp_file.route("/get-keys-zip-file", methods=["POST"])
def get_keys_zip_file():
    try:
        origin_file = request.files.get("origin_file")
        if not origin_file:
            return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

        keys = read_json_file_list(origin_file)
        if not keys:
            return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())
        return jsonify(Response().successful_response({"keys": keys}).model_dump())
    except Exception as e:
        current_app.logger.error(f"Failed to validate JSON: {str(e)}")
        return jsonify(Response().error_response(ErrorCode.INTERNAL_SERVER_ERROR).model_dump())


@bp_file.route("/apply-changes-and-download", methods=["POST"])
def apply_changes_and_download():
    try:
        origin_file = request.files.get("origin_file")
        work_file = request.files.get("work_file")
        selected_keys = json.loads(request.form.get("selected_keys", "[]"))

        if not origin_file or not work_file or not selected_keys:
            return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

        result = apply_changes_and_download_service(origin_file, work_file, selected_keys)
        response = send_file(result["zip_path"], as_attachment=True)

        result.pop("zip_path", None)
        response.headers["X-Metadata"] = json.dumps(result)
        return response
    except Exception as e:
        traceback.print_exc()
        current_app.logger.error(f"Error: {str(e)}")
        return jsonify(Response().error_response(ErrorCode.INTERNAL_SERVER_ERROR).model_dump())


@bp_file.route("/check-validate-json", methods=["POST"])
def check_validate_json():  # 압축파일 저장
    try:
        zip_file = request.files.get("zip_file")
        if not zip_file:
            return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

        info, err_list = check_validate_json_service(zip_file)
        return jsonify(Response().metadata(**info).successful_response(err_list).model_dump())
    except Exception as e:
        current_app.logger.error(f"Failed to validate JSON: {str(e)}")
        return jsonify(Response().error_response(ErrorCode.INTERNAL_SERVER_ERROR).model_dump())


@bp_file.route("/get-keys", methods=["POST"])
def get_keys():
    try:
        zip_file = request.files.get("zip_file")
        if not zip_file:
            return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

        keys = get_keys_service(zip_file)
        return jsonify(Response().metadata().successful_response(keys).model_dump())
    except Exception as e:
        current_app.logger.error(f"Failed to validate JSON: {str(e)}")
        return jsonify(Response().error_response(ErrorCode.INTERNAL_SERVER_ERROR).model_dump())


@bp_file.route("/remove-keys", methods=["POST"])
def remove_keys():
    try:
        zip_file = request.files.get("zip_file")
        remove_key = request.form.get("remove_key")
        if not zip_file or not remove_key:
            return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

        output_buffer = remove_keys_service(zip_file, remove_key)
        output_buffer.seek(0)
        return send_file(
            output_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name="processed_files.zip",
        )
    except Exception as e:
        current_app.logger.error(f"Failed to validate JSON: {str(e)}")
        return jsonify(Response().error_response(ErrorCode.INTERNAL_SERVER_ERROR).model_dump())


@bp_file.route("/translate-bulk", methods=["POST"])
def translate_bulk():
    try:
        print("Flask: Received request to start task.")
        task = process_items_task.delay(5)
        print(f"Flask: Task {task.id} sent to queue.")
        return jsonify(Response().successful_response({"task_id": task.id}).model_dump())
    except Exception as e:
        current_app.logger.error(f"Failed to validate JSON: {str(e)}")
        return jsonify(Response().error_response(ErrorCode.INTERNAL_SERVER_ERROR).model_dump())


@bp_file.route("/translate-bulk/<task_id>", methods=["GET"])
def translate_bulk_status(task_id):
    try:
        from celery.result import AsyncResult

        task = AsyncResult(task_id, app=process_items_task.app)
        if task.state == "PENDING":
            response = {"state": task.state, "progress": 0}
        elif task.state == "PROGRESS":
            response = {
                "state": task.state,
                "progress": task.info.get("progress", 0),
                "current": task.info.get("current", 0),
                "total": task.info.get("total", 100),
            }
        elif task.state == "SUCCESS":
            response = {"state": task.state, "progress": 100, "result": task.result}
        else:
            # 실패(Failure) 혹은 기타 상태 처리
            response = {"state": task.state, "error": str(task.info)}
        return jsonify(response)
    except Exception as e:
        current_app.logger.error(f"Failed to validate JSON: {str(e)}")
        return jsonify(Response().error_response(ErrorCode.INTERNAL_SERVER_ERROR).model_dump())


@bp_file.route("/json-to-xlsx", methods=["POST"])
def json_to_xlsx():
    try:
        zip_file = request.files.get("target_file")
        if not zip_file:
            return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

        all_rows, info_keys_set, other_data_keys_set = convert_json_to_xlsx(zip_file)
        if not all_rows:
            return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

        df = pd.DataFrame(all_rows)

        file_cols = ["file_path", "filename"]
        path_cols = ["root_key", "index", "path"]
        base_data_cols = ["original", "localized"]

        # 전달받은 키 목록을 정렬하여 사용
        info_cols = sorted(list(info_keys_set))
        other_data_cols = sorted(list(other_data_keys_set))

        # 최종 컬럼 순서 조합
        final_col_order = file_cols + info_cols + path_cols + base_data_cols + other_data_cols

        # DataFrame에 존재하는 컬럼만으로 최종 순서 필터링
        final_col_order_existing = [col for col in final_col_order if col in df.columns]
        df = df[final_col_order_existing]

        excel_buffer = create_excel_from_dataframe(df)
        return send_file(
            excel_buffer,
            as_attachment=True,
            download_name="json_data.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        current_app.logger.error(f"Error processing JSON file: {str(e)}")
        return jsonify(Response().error_response(ErrorCode.INTERNAL_SERVER_ERROR).model_dump())


@bp_file.route("/xlsx-to-json", methods=["POST"])
def xlsx_to_json():
    try:
        excel_file = request.files.get("target_file")
        if not excel_file:
            return jsonify(Response().error_response(ErrorCode.DATA_NOT_FOUND).model_dump())

        zip_buffer = convert_excel_to_json(excel_file, DEFAULT_COLUMNS)

        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name="json_files.zip",
            mimetype="application/zip",
        )
    except Exception as e:
        current_app.logger.error(f"엑셀 to JSON 변환 중 오류: {str(e)}")
        return jsonify(Response().error_response(ErrorCode.INTERNAL_SERVER_ERROR).model_dump())
