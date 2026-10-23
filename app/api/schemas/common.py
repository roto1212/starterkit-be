"""app/api/schemas/common.py

여러 도메인이 공유하는 응답 형태. 여기 있는 것만 openapi.json 에 나가므로
DB 컬럼을 그대로 노출하는 스키마를 만들지 않는다 — 그건 db/schemas 의 역할이다.
"""

from pydantic import BaseModel


class PageResponse[T](BaseModel):
    items: list[T]
    total: int
    offset: int
    limit: int


class ErrorResponse(BaseModel):
    """app/core/exception_handlers.py 가 실제로 내려주는 에러 응답 형태와 맞춘다."""

    success: bool = False
    code: str
    detail: str
    request_id: str
