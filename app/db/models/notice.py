"""app/db/models/notice.py

★ 예제 도메인 — 새 도메인을 추가할 때 이 파일들을 복사해 이름만 바꾼다.
  전체 목록은 .claude/CLAUDE.md의 "새 도메인 추가하기" 절 참조.
"""

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import DATETIME2_3, Base, Unicode, UnicodeText


class Notice(Base):
    __tablename__ = "notice"
    __table_args__ = (
        # 목록 조회(삭제 안 됨 + 상단고정 우선 + 최신순)를 커버하는 인덱스
        Index("ix_notice_list", "is_deleted", "is_pinned", "created_at"),
        Index("ix_notice_author", "author_id"),
    )

    notice_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Unicode(200), nullable=False)
    content: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    author_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dbo.app_user.user_id"), nullable=False
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        DATETIME2_3, nullable=False, server_default=func.sysdatetime()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DATETIME2_3, nullable=True, onupdate=func.sysdatetime()
    )

    def __repr__(self) -> str:
        return f"<Notice(notice_id={self.notice_id}, title={self.title!r})>"
