"""app/db/repositories/user.py

★ 신원 저장소 슬라이스. 순수 쿼리만 담당 — 브루트포스 정책 판단(몇 번 실패하면
잠글지)은 여기서 하지 않고 services/auth_service.py 가 결정한다.
"""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import AppUser
from app.db.schemas.user import UserRow


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: int) -> UserRow | None:
        result = await self.db.execute(select(AppUser).where(AppUser.user_id == user_id))
        user = result.scalar_one_or_none()
        return UserRow.model_validate(user) if user else None

    async def get_by_email(self, email: str) -> UserRow | None:
        result = await self.db.execute(select(AppUser).where(AppUser.email == email))
        user = result.scalar_one_or_none()
        return UserRow.model_validate(user) if user else None

    async def create(self, email: str, password_hash: str, roles: str = "user") -> UserRow:
        user = AppUser(email=email, password_hash=password_hash, roles=roles)
        self.db.add(user)
        await self.db.flush()  # DB 반영 (commit은 서비스 레이어 책임)
        await self.db.refresh(user)  # server_default 값(created_at 등) 로드
        return UserRow.model_validate(user)

    async def update_password_hash(self, user_id: int, new_hash: str) -> None:
        await self.db.execute(
            update(AppUser).where(AppUser.user_id == user_id).values(password_hash=new_hash)
        )
        await self.db.flush()

    async def increment_failed_login(self, user_id: int) -> int:
        """실패 카운트를 1 올리고 갱신된 값을 반환한다. 잠글지 여부는 호출부가 판단."""
        await self.db.execute(
            update(AppUser)
            .where(AppUser.user_id == user_id)
            .values(failed_login_count=AppUser.failed_login_count + 1)
        )
        await self.db.flush()
        result = await self.db.execute(
            select(AppUser.failed_login_count).where(AppUser.user_id == user_id)
        )
        return result.scalar_one()

    async def set_locked_until(self, user_id: int, until: datetime) -> None:
        await self.db.execute(
            update(AppUser).where(AppUser.user_id == user_id).values(locked_until=until)
        )
        await self.db.flush()

    async def clear_login_failures(self, user_id: int) -> None:
        """로그인 성공 시 실패 카운트/잠금을 초기화한다."""
        await self.db.execute(
            update(AppUser)
            .where(AppUser.user_id == user_id)
            .values(failed_login_count=0, locked_until=None)
        )
        await self.db.flush()
