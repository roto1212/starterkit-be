"""app/db/models/refresh_token.py

★ 신원 저장소 슬라이스 — user.py 와 함께 통째로 삭제 가능. docs/BOOTSTRAP.md 참조.

refresh 토큰은 값을 직접 저장하지 않고 SHA-256 해시만 저장한다.
DB가 유출되어도 저장된 값만으로는 토큰을 재사용할 수 없다.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import DATETIME2_3, Base, Unicode
from app.db.models.user import AppUser


class RefreshToken(Base):
    __tablename__ = "auth_refresh_token"

    token_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dbo.app_user.user_id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Unicode(64), unique=True, nullable=False)  # SHA-256 hex
    expires_at: Mapped[datetime] = mapped_column(DATETIME2_3, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DATETIME2_3, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME2_3, nullable=False, server_default=func.sysdatetime()
    )

    user: Mapped["AppUser"] = relationship(
        "AppUser", back_populates="refresh_tokens", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<RefreshToken(token_id={self.token_id}, user_id={self.user_id})>"
