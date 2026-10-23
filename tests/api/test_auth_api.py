"""tests/api/test_auth_api.py — ★ 신원 저장소 슬라이스."""

import uuid

from httpx import AsyncClient


def _unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:12]}@example.com"


async def test_register_returns_created_user(client: AsyncClient) -> None:
    email = _unique_email()
    r = await client.post(
        "/v1/auth/register", json={"email": email, "password": "a valid password 123"}
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == email
    assert body["roles"] == ["user"]


async def test_duplicate_register_rejected(client: AsyncClient) -> None:
    email = _unique_email()
    payload = {"email": email, "password": "a valid password 123"}
    await client.post("/v1/auth/register", json=payload)
    r = await client.post("/v1/auth/register", json=payload)
    assert r.status_code == 409
    assert r.json()["code"] == "CONFLICT"


async def test_login_wrong_password_rejected(client: AsyncClient) -> None:
    email = _unique_email()
    await client.post(
        "/v1/auth/register", json={"email": email, "password": "correct password 123"}
    )
    r = await client.post("/v1/auth/login", json={"email": email, "password": "wrong password"})
    assert r.status_code == 401


async def test_login_nonexistent_user_same_error_as_wrong_password(client: AsyncClient) -> None:
    """계정 열거 방지 — 존재하지 않는 이메일도 비번 틀림과 동일한 메시지/코드를 받는다."""
    r1 = await client.post(
        "/v1/auth/login", json={"email": _unique_email(), "password": "whatever123"}
    )

    email = _unique_email()
    await client.post(
        "/v1/auth/register", json={"email": email, "password": "correct password 123"}
    )
    r2 = await client.post("/v1/auth/login", json={"email": email, "password": "wrong password"})

    assert r1.status_code == r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]


async def test_login_success_returns_token_and_sets_cookie(client: AsyncClient) -> None:
    email = _unique_email()
    await client.post(
        "/v1/auth/register", json={"email": email, "password": "correct password 123"}
    )
    r = await client.post(
        "/v1/auth/login", json={"email": email, "password": "correct password 123"}
    )
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]
    assert "refresh_token" in r.cookies


async def test_me_requires_valid_token(client: AsyncClient) -> None:
    r = await client.get("/v1/auth/me")
    assert r.status_code == 401

    email = _unique_email()
    await client.post(
        "/v1/auth/register", json={"email": email, "password": "correct password 123"}
    )
    login = await client.post(
        "/v1/auth/login", json={"email": email, "password": "correct password 123"}
    )
    token = login.json()["access_token"]

    r = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == email


async def test_refresh_rotates_token_and_old_one_becomes_invalid(client: AsyncClient) -> None:
    email = _unique_email()
    await client.post(
        "/v1/auth/register", json={"email": email, "password": "correct password 123"}
    )
    await client.post("/v1/auth/login", json={"email": email, "password": "correct password 123"})

    r1 = await client.post("/v1/auth/refresh")
    assert r1.status_code == 200
    token_after_first_refresh = r1.json()["access_token"]

    r2 = await client.post("/v1/auth/refresh")
    assert r2.status_code == 200
    assert r2.json()["access_token"] != token_after_first_refresh


async def test_logout_then_refresh_rejected(client: AsyncClient) -> None:
    email = _unique_email()
    await client.post(
        "/v1/auth/register", json={"email": email, "password": "correct password 123"}
    )
    await client.post("/v1/auth/login", json={"email": email, "password": "correct password 123"})

    r = await client.post("/v1/auth/logout")
    assert r.status_code == 204

    r = await client.post("/v1/auth/refresh")
    assert r.status_code == 401


async def test_account_locks_after_repeated_failures(client: AsyncClient) -> None:
    from app.config import settings

    email = _unique_email()
    await client.post(
        "/v1/auth/register", json={"email": email, "password": "correct password 123"}
    )

    for _ in range(settings.LOGIN_FAIL_MAX):
        r = await client.post("/v1/auth/login", json={"email": email, "password": "wrong password"})
        assert r.status_code == 401

    # 실패 횟수를 다 채운 뒤에는, 이번엔 "맞는" 비밀번호를 넣어도 잠금 때문에 거부되어야 한다
    r = await client.post(
        "/v1/auth/login", json={"email": email, "password": "correct password 123"}
    )
    assert r.status_code == 401
