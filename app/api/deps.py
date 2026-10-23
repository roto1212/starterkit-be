"""app/api/deps.py

★ 껍데기(항상 포함) — get_current_user / require_roles / CurrentUser.
  신원이 이 서비스가 아니라 외부(SSO·게이트웨이)에서 온다면, 아래
  get_current_user의 "JWT 디코드 + DB 조회" 부분만 그 외부 검증 로직으로
  바꿔치면 된다. CurrentUser를 반환하는 함수라는 계약만 지키면 나머지
  (require_roles, 각 엔드포인트)는 손댈 필요가 없다.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import jwt as pyjwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import user_id_var
from app.core.exceptions import AuthError, ForbiddenError
from app.core.security import decode_access_token
from app.db.repositories.notice import NoticeRepository
from app.db.repositories.refresh_token import RefreshTokenRepository
from app.db.repositories.user import UserRepository
from app.db.session import get_db

if TYPE_CHECKING:
    from app.services.auth_service import AuthService
    from app.services.notice_service import NoticeService

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    user_id: int
    email: str
    roles: frozenset[str]

    def has_role(self, role: str) -> bool:
        return role in self.roles


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if credentials is None:
        raise AuthError("인증이 필요합니다.")

    try:
        payload = decode_access_token(credentials.credentials)
    except pyjwt.InvalidTokenError as e:
        raise AuthError("유효하지 않은 토큰입니다.") from e

    # 무상태 JWT만 믿으면 계정을 비활성화해도 최대 토큰 수명(기본 30분)만큼
    # 살아있는 상태가 된다. 운영 시스템 특성상(퇴사자 즉시 차단) 요청당
    # 인덱스 조회 1회는 값싼 보험이다.
    user = await UserRepository(db).get_by_id(payload.user_id)
    if user is None or not user.is_active:
        raise AuthError("유효하지 않은 사용자입니다.")

    user_id_var.set(str(user.user_id))
    return CurrentUser(user_id=user.user_id, email=user.email, roles=user.role_set)


def require_roles(*roles: str) -> object:
    """특정 역할을 요구하는 Depends 팩토리.

    사용 예:
        @router.delete("/notices/{notice_id}")
        async def delete_notice(
            user: CurrentUser = Depends(require_roles("admin")),
        ): ...
    """

    async def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any(user.has_role(r) for r in roles):
            raise ForbiddenError(f"{'/'.join(roles)} 권한이 필요합니다.")
        return user

    return _dep


async def get_notice_service(db: AsyncSession = Depends(get_db)) -> "NoticeService":
    from app.services.notice_service import NoticeService

    return NoticeService(NoticeRepository(db), db)


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> "AuthService":
    """★ 신원 저장소 슬라이스 — 이 함수는 auth_service.py 와 함께 삭제 가능."""
    from app.services.auth_service import AuthService

    return AuthService(UserRepository(db), RefreshTokenRepository(db), db)
