"""app/db/repositories/refresh_token.py — ★ 신원 저장소 슬라이스. 순수 쿼리만."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.base import utcnow_naive
from app.db.models.refresh_token import RefreshToken
from app.db.schemas.refresh_token import RefreshTokenRow


class RefreshTokenRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, user_id: int, token_hash: str, expires_at: datetime) -> RefreshTokenRow:
        row = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return RefreshTokenRow.model_validate(row)

    async def get_by_hash(self, token_hash: str) -> RefreshTokenRow | None:
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        row = result.scalar_one_or_none()
        return RefreshTokenRow.model_validate(row) if row else None

    async def revoke(self, token_id: int) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_id == token_id)
            .values(revoked_at=utcnow_naive())
        )
        await self.db.flush()

    async def revoke_all_for_user(self, user_id: int) -> None:
        """로그아웃-전체/비밀번호 변경 시 그 사용자의 모든 refresh 토큰을 폐기한다."""
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow_naive())
        )
        await self.db.flush()
