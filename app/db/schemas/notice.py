"""app/db/schemas/notice.py — repository → service 경계 내부 DTO."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NoticeRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notice_id: int
    title: str
    content: str
    author_id: int
    is_pinned: bool
    view_count: int
    is_deleted: bool
    created_at: datetime
    updated_at: datetime | None
