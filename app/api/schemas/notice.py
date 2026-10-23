"""app/api/schemas/notice.py — ★ 예제 도메인. 공개 계약 (openapi.json 노출)."""

from datetime import datetime

from pydantic import BaseModel, Field


class NoticeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)


class NoticeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1)
    is_pinned: bool | None = None


class NoticeResponse(BaseModel):
    notice_id: int
    title: str
    content: str
    author_id: int
    is_pinned: bool
    view_count: int
    created_at: datetime
    updated_at: datetime | None
