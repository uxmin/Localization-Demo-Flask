from enum import Enum

from pydantic import BaseModel


class ErrorCode(Enum):
    DATA_NOT_FOUND = ("DATA_NOT_FOUND", "요청하신 데이터를 찾을 수 없습니다. 다시 시도해주세요.")
    INVALID_FILE = ("INVALID_FILE", "파일 형식이 잘못되었습니다. 올바른 형식의 파일을 업로드해주세요.")

    PROMPT_NOT_FOUND = ("PROMPT_NOT_FOUND", "프롬프트 파일을 찾을 수 없습니다. 관리자에게 문의하세요.")
    CONFIGURATION_ERROR = ("CONFIGURATION_ERROR", "설정에 오류가 발생했습니다. 관리자에게 문의하세요.")
    INVALID_JSON_FORMAT = ("INVALID_JSON_FORMAT", "잘못된 JSON 형식입니다. 입력 데이터를 확인해주세요.")
    INVALID_INPUT = ("INVALID_INPUT", "입력 값이 잘못되었습니다. 입력 데이터를 확인해주세요.")

    INTERNAL_SERVER_ERROR = ("INTERNAL_SERVER_ERROR", "내부 서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
    EXTERNAL_SERVICE_ERROR = ("EXTERNAL_SERVICE_ERROR", "외부 서비스 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
    DUPLICATE_ENTRY = ("DUPLICATE_ENTRY", "중복된 항목이 있습니다. 다시 확인해주세요.")

    INVALID_API_KEY = ("INVALID_API_KEY", "API 키가 유효하지 않거나 인증에 실패했습니다. API 키를 확인해주세요.")
    EMPTY_RESPONSE = ("EMPTY_RESPONSE", "모델로부터 응답을 받지 못했습니다. 입력 값을 확인하거나 다시 시도해주세요.")

    KPI_DATA_NOT_FOUND = ("KPI_ERROR", "추출할 KPI 데이터가 없습니다. 납품 데이터를 먼저 다운로드 해주세요.")

    @property
    def code(self):
        return self.value[0]

    @property
    def message(self):
        return self.value[1]


class Error(BaseModel):
    code: str
    message: str
