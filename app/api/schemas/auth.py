"""app/api/schemas/auth.py — ★ 신원 저장소 슬라이스. 공개 계약 (openapi.json 노출)."""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 — OAuth2 토큰 타입 문자열이지 시크릿이 아니다
    expires_in: int  # 초


class MeResponse(BaseModel):
    user_id: int
    email: str
    roles: list[str]
