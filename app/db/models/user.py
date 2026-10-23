"""app/db/models/user.py

★ 신원 저장소 슬라이스 — 이 서비스가 자체 로그인을 쓰지 않는다면
  (예: 외부 SSO/게이트웨이가 신원을 전달하는 경우) 이 파일과
  refresh_token.py, 관련 repository/service/endpoint를 통째로 삭제한다.
  자세한 목록은 docs/BOOTSTRAP.md 참조.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import DATETIME2_3, Base, Unicode

if TYPE_CHECKING:
    from app.db.models.refresh_token import RefreshToken


class AppUser(Base):
    __tablename__ = "app_user"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(Unicode(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Unicode(255), nullable=False)
    # 콤마 구분 문자열. 역할이 늘어나면 별도 role 테이블로 정규화한다.
    roles: Mapped[str] = mapped_column(Unicode(200), nullable=False, server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    # ── 로그인 브루트포스 방어 (DB 컬럼 기반 — docs/AUTH.md 참조) ──
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DATETIME2_3, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DATETIME2_3, nullable=False, server_default=func.sysdatetime()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DATETIME2_3, nullable=True, onupdate=func.sysdatetime()
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", lazy="noload"
    )

    @property
    def role_set(self) -> frozenset[str]:
        return frozenset(r.strip() for r in self.roles.split(",") if r.strip())

    def __repr__(self) -> str:
        return f"<AppUser(user_id={self.user_id}, email={self.email!r})>"
