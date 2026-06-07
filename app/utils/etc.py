import re
from functools import wraps
from typing import List

from flask import current_app, jsonify, request

from app.exceptions import AppError
from app.schemas.error import ErrorCode
from app.schemas.response import Response


def replace_words_with_O_case_insensitive(text: str, words_to_replace: List[str]) -> str:
    pattern = r"(" + "|".join(re.escape(word) for word in words_to_replace) + r")"
    return re.sub(pattern, "OOO", text, flags=re.IGNORECASE)


def clean_response(response: str) -> str:
    """백틱이나 언어 태그 제거 + JSON 문자열만 추출"""
    response = response.strip()
    if response.startswith("```json"):
        response = response.lstrip("```json").rstrip("```").strip()
    elif response.startswith("```"):
        response = response.lstrip("```").rstrip("```").strip()
    return response


def split_json_and_text(response_text: str) -> tuple[str, str]:
    """
    마크다운 코드 블록(```json)으로 감싸인 JSON 문자열과 그 외 텍스트를 분리합니다.
    """
    json_part = ""
    text_part = ""
    in_json = False

    lines = response_text.split("\n")
    for line in lines:
        if line.strip().startswith("```json"):
            in_json = True
            continue
        elif line.strip().startswith("```") and in_json:
            in_json = False
            continue

        if in_json:
            json_part += line + "\n"
        else:
            text_part += line + "\n"

    return json_part.strip(), text_part.strip()


def handle_exceptions(f):
    """
    API 라우트에서 발생하는 예외를 일관되게 처리하는 데코레이터.
    예외 발생 시 에러를 로깅하고 표준 에러 응답을 반환합니다.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except AppError as e:
            # 예상 가능한 도메인 오류: 해당 ErrorCode로 변환한다.
            current_app.logger.warning(f"AppError in {f.__name__}: {e.error_code.code} - {e}")
            return jsonify(Response().error_response(e.error_code).model_dump())
        except Exception as e:
            current_app.logger.error(f"An unexpected error occurred in {f.__name__}: {e}", exc_info=True)
            return jsonify(Response().error_response(ErrorCode.INTERNAL_SERVER_ERROR).model_dump())

    return decorated_function


def require_json_body(f):
    """
    POST/PUT 요청 시 JSON 본문이 있는지 확인하는 데코레이터.
    본문이 없으면 INVALID_INPUT 에러를 반환합니다.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return jsonify(Response().error_response(ErrorCode.INVALID_INPUT).model_dump())

        data = request.get_json()
        if not data:
            return jsonify(Response().error_response(ErrorCode.INVALID_INPUT).model_dump())

        # 데코레이터를 통과한 데이터를 뷰 함수로 전달
        return f(data, *args, **kwargs)

    return decorated_function
