"""app/api/v1/endpoints/auth.py

★ 신원 저장소 슬라이스. 쿠키 set/delete는 HTTP 관심사이므로 여기서만 한다
(서비스 계층은 토큰 문자열만 다루고 쿠키를 모른다).
"""

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import CurrentUser, get_auth_service, get_current_user
from app.api.schemas.auth import LoginRequest, MeResponse, RegisterRequest, TokenResponse
from app.config import settings
from app.core.exceptions import AuthError
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "refresh_token"
# 실제 마운트 경로(/v1/auth)와 반드시 일치해야 한다 — 이 앱엔 /api 프리픽스가 없다.
# 어긋나면 브라우저/httpx 쿠키잭이 RFC 6265 path 규칙에 따라 쿠키를 아예 안 보낸다
# (조용히 실패한다 — 만들 때 실제로 겪은 버그).
_REFRESH_COOKIE_PATH = "/v1/auth"


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=raw_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path=_REFRESH_COOKIE_PATH,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


@router.post("/register", response_model=MeResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> MeResponse:
    user = await auth_service.register(body.email, body.password)
    return MeResponse(user_id=user.user_id, email=user.email, roles=sorted(user.role_set))


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    access_token, refresh_token_raw, expires_in = await auth_service.login(
        body.email, body.password
    )
    _set_refresh_cookie(response, refresh_token_raw)
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    raw_token = request.cookies.get(_REFRESH_COOKIE)
    if not raw_token:
        raise AuthError("세션이 만료되었습니다. 다시 로그인해 주세요.")

    access_token, new_refresh_token_raw, expires_in = await auth_service.refresh(raw_token)
    _set_refresh_cookie(response, new_refresh_token_raw)
    return TokenResponse(access_token=access_token, expires_in=expires_in)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    raw_token = request.cookies.get(_REFRESH_COOKIE)
    if raw_token:
        await auth_service.logout(raw_token)
    response.delete_cookie(_REFRESH_COOKIE, path=_REFRESH_COOKIE_PATH)


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser = Depends(get_current_user)) -> MeResponse:
    return MeResponse(user_id=user.user_id, email=user.email, roles=sorted(user.roles))
