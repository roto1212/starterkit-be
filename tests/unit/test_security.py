"""tests/unit/test_security.py — DB/인프라 없이 순수 함수만 검증한다."""

import time

import jwt as pyjwt
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    verify_password,
)


def test_hash_and_verify_roundtrip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_rejects_wrong_password() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_fresh_hash_does_not_need_rehash() -> None:
    hashed = hash_password("some password")
    assert needs_rehash(hashed) is False


def test_access_token_roundtrip() -> None:
    token = create_access_token(user_id=42, roles=frozenset({"user", "admin"}))
    payload = decode_access_token(token)
    assert payload.user_id == 42
    assert payload.roles == frozenset({"user", "admin"})


def test_tampered_access_token_rejected() -> None:
    token = create_access_token(user_id=1, roles=frozenset())
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_access_token(token + "tampered")


def test_expired_access_token_rejected() -> None:
    # exp를 과거로 강제 설정해 만료 검증 자체를 확인한다.
    from app.config import settings

    now = int(time.time())
    payload = {
        "sub": "1",
        "typ": "access",
        "iat": now - 3600,
        "exp": now - 1,
        "jti": "test",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "roles": [],
    }
    expired_token = pyjwt.encode(
        payload, settings.JWT_SECRET_KEY.get_secret_value(), algorithm="HS256"
    )
    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_access_token(expired_token)


def test_wrong_token_type_rejected() -> None:
    """typ 클레임이 access가 아니면 거부한다 — refresh 토큰을 access 자리에
    잘못 끼워 넣는 실수를 막는다."""
    from app.config import settings

    now = int(time.time())
    payload = {
        "sub": "1",
        "typ": "refresh",  # access가 아님
        "iat": now,
        "exp": now + 3600,
        "jti": "test",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "roles": [],
    }
    token = pyjwt.encode(payload, settings.JWT_SECRET_KEY.get_secret_value(), algorithm="HS256")
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_access_token(token)


def test_refresh_token_hash_is_deterministic_and_not_reversible() -> None:
    raw = generate_refresh_token()
    assert hash_refresh_token(raw) == hash_refresh_token(raw)
    assert hash_refresh_token(raw) != raw


def test_refresh_tokens_are_unique() -> None:
    tokens = {generate_refresh_token() for _ in range(20)}
    assert len(tokens) == 20
