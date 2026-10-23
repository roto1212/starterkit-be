"""app/core/security.py

★ 신원 저장소 슬라이스 — 비밀번호 해싱과 JWT 발급/검증의 순수 함수만 담는다.
  DB나 FastAPI를 import하지 않는다: 그래야 tests/unit/ 에서 인프라 없이
  전량 테스트된다.

해싱: argon2-cffi 직접 사용 (passlib 아님 — passlib은 2020년 이후 유지보수가
정체되어 있고 Python 3.13에서 깨진다. pwdlib은 아직 0.x라 이 정도 로직에
의존성을 더 얹을 이유가 없다). Argon2id는 PHC(Password Hashing Competition)
우승 알고리즘이고 메모리 하드라 GPU/ASIC 공격 비용이 bcrypt 대비 훨씬 높다.

토큰: access는 JWT(무상태, 30분), refresh는 불투명 랜덤 문자열(DB에 SHA-256
해시로만 저장, 회전) — 자세한 설계 근거는 docs/AUTH.md 참조.
"""

import hashlib
import secrets
import time
from dataclasses import dataclass

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import settings

# OWASP 권장 하한값. 서버 스펙에 여유가 있으면 memory_cost를 올린다.
_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def needs_rehash(hashed: str) -> bool:
    """해싱 파라미터를 나중에 올렸을 때, 로그인 성공 순간 조용히 재해시하기 위한 판정.
    호출부(auth_service)가 로그인 성공 직후 True면 hash_password() 로 재해시해 저장한다."""
    return _hasher.check_needs_rehash(hashed)


@dataclass(frozen=True)
class AccessTokenPayload:
    user_id: int
    roles: frozenset[str]
    jti: str


def create_access_token(user_id: int, roles: frozenset[str]) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "typ": "access",
        "iat": now,
        "exp": now + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "jti": secrets.token_hex(8),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "roles": sorted(roles),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY.get_secret_value(), algorithm="HS256")


def decode_access_token(token: str) -> AccessTokenPayload:
    """검증 실패 시 jwt.InvalidTokenError 계열 예외를 그대로 전파한다.
    호출부(api/deps.py)가 이를 잡아 401로 변환한다."""
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithms=["HS256"],  # 화이트리스트 고정 — alg 혼동 공격(alg:none 등) 차단
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
    )
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("access 토큰이 아닙니다.")
    return AccessTokenPayload(
        user_id=int(payload["sub"]),
        roles=frozenset(payload.get("roles", [])),
        jti=payload["jti"],
    )


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_token: str) -> str:
    """DB에는 이 해시만 저장한다 — DB가 유출돼도 저장값만으로는 토큰을 재사용할 수 없다."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
