"""app/services/auth_service.py

★ 신원 저장소 슬라이스 — 자세한 설계 근거는 docs/AUTH.md 참조.

로그인 실패 사유(존재하지 않는 이메일/틀린 비밀번호/계정 잠김)는 전부 동일한
메시지로 응답한다. 사유별로 다른 메시지를 주면 공격자가 어느 이메일이
가입되어 있는지 순차 대입으로 알아낼 수 있다(계정 열거 공격).
"""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AuthError, ConflictError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    verify_password,
)
from app.db.models.base import utcnow_naive
from app.db.repositories.refresh_token import RefreshTokenRepository
from app.db.repositories.user import UserRepository
from app.db.schemas.user import UserRow

_LOGIN_FAILED_MSG = "이메일 또는 비밀번호가 올바르지 않습니다."
_SESSION_EXPIRED_MSG = "세션이 만료되었습니다. 다시 로그인해 주세요."


class AuthService:
    def __init__(
        self, user_repo: UserRepository, refresh_repo: RefreshTokenRepository, db: AsyncSession
    ) -> None:
        self.user_repo = user_repo
        self.refresh_repo = refresh_repo
        self.db = db

    async def register(self, email: str, password: str) -> UserRow:
        existing = await self.user_repo.get_by_email(email)
        if existing:
            raise ConflictError("이미 가입된 이메일입니다.")
        user = await self.user_repo.create(email, hash_password(password))
        await self.db.commit()
        return user

    async def login(self, email: str, password: str) -> tuple[str, str, int]:
        """Returns: (access_token, refresh_token_raw, expires_in_seconds)"""
        user = await self.user_repo.get_by_email(email)

        if user is None or not user.is_active:
            raise AuthError(_LOGIN_FAILED_MSG)

        if user.locked_until and user.locked_until > utcnow_naive():
            raise AuthError(_LOGIN_FAILED_MSG)

        if not verify_password(password, user.password_hash):
            new_count = await self.user_repo.increment_failed_login(user.user_id)
            if new_count >= settings.LOGIN_FAIL_MAX:
                until = utcnow_naive() + timedelta(seconds=settings.LOGIN_LOCK_SEC)
                await self.user_repo.set_locked_until(user.user_id, until)
            await self.db.commit()
            raise AuthError(_LOGIN_FAILED_MSG)

        # 해싱 파라미터를 나중에 올렸다면, 로그인 성공 순간 조용히 재해시한다 —
        # 이게 파라미터를 나중에 강화할 수 있는 유일한 지점이라 1일차부터 넣는다.
        if needs_rehash(user.password_hash):
            await self.user_repo.update_password_hash(user.user_id, hash_password(password))

        await self.user_repo.clear_login_failures(user.user_id)

        access_token = create_access_token(user.user_id, user.role_set)
        refresh_token_raw = await self._issue_refresh_token(user.user_id)
        await self.db.commit()
        return access_token, refresh_token_raw, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    async def refresh(self, refresh_token_raw: str) -> tuple[str, str, int]:
        """refresh 토큰을 회전한다: 기존 토큰은 폐기하고 새 쌍을 발급한다."""
        token_hash = hash_refresh_token(refresh_token_raw)
        row = await self.refresh_repo.get_by_hash(token_hash)

        if row is None or row.revoked_at is not None or row.expires_at < utcnow_naive():
            raise AuthError(_SESSION_EXPIRED_MSG)

        user = await self.user_repo.get_by_id(row.user_id)
        if user is None or not user.is_active:
            raise AuthError(_SESSION_EXPIRED_MSG)

        await self.refresh_repo.revoke(row.token_id)

        access_token = create_access_token(user.user_id, user.role_set)
        new_refresh_token_raw = await self._issue_refresh_token(user.user_id)
        await self.db.commit()
        return access_token, new_refresh_token_raw, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    async def logout(self, refresh_token_raw: str) -> None:
        """로그아웃은 멱등이어야 한다 — 이미 없거나 폐기된 토큰이어도 조용히 성공 처리."""
        token_hash = hash_refresh_token(refresh_token_raw)
        row = await self.refresh_repo.get_by_hash(token_hash)
        if row is not None and row.revoked_at is None:
            await self.refresh_repo.revoke(row.token_id)
        await self.db.commit()

    async def _issue_refresh_token(self, user_id: int) -> str:
        raw = generate_refresh_token()
        expires_at = utcnow_naive() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await self.refresh_repo.create(user_id, hash_refresh_token(raw), expires_at)
        return raw
