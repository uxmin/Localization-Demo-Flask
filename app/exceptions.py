"""애플리케이션 예외 계층.

서비스 계층에서 발생하는 도메인성 오류를 `AppError`로 표현하고,
컨트롤러(데코레이터)에서 일관된 `ErrorCode` 응답으로 변환한다.
예상 가능한 실패는 AppError로, 예상치 못한 오류는 그대로 전파되어
INTERNAL_SERVER_ERROR로 처리된다.
"""

from app.schemas.error import ErrorCode


class AppError(Exception):
    """ErrorCode를 동반하는 애플리케이션 기본 예외."""

    def __init__(self, error_code: ErrorCode, detail: str | None = None) -> None:
        self.error_code = error_code
        self.detail = detail
        super().__init__(detail or error_code.message)


class PromptNotFoundError(AppError):
    def __init__(self, detail: str | None = None) -> None:
        super().__init__(ErrorCode.PROMPT_NOT_FOUND, detail)


class DataNotFoundError(AppError):
    def __init__(self, detail: str | None = None) -> None:
        super().__init__(ErrorCode.DATA_NOT_FOUND, detail)


class InvalidInputError(AppError):
    def __init__(self, detail: str | None = None) -> None:
        super().__init__(ErrorCode.INVALID_INPUT, detail)


class ExternalServiceError(AppError):
    def __init__(self, detail: str | None = None) -> None:
        super().__init__(ErrorCode.EXTERNAL_SERVICE_ERROR, detail)
