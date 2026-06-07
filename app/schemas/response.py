from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel

from app.schemas.error import Error, ErrorCode

T = TypeVar("T")


class Meta(BaseModel):
    __abstract__ = True

    meta: Dict[str, Any] = {}

    def metadata(self, **kwargs) -> "Meta":
        for k, v in kwargs.items():
            self.meta.setdefault(k, v)
        return self


class Response(Meta, Generic[T]):
    status_code: int = 200
    data: Optional[T] = None
    error: Optional[Error] = None

    class Config:
        arbitrary_types_allowed = True

    def successful_response(self, data: Optional[T] = None) -> "Response[T]":
        self.data = data
        self.error = Error(code="", message="")
        return self

    def error_response(self, error_code: ErrorCode) -> "Response[T]":
        self.status_code = 500 if error_code == ErrorCode.INTERNAL_SERVER_ERROR else 400
        self.data = None
        self.error = Error(code=error_code.code, message=error_code.message)
        return self
