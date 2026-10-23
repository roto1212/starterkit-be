"""tests/api/test_notice_api.py — ★ 예제 도메인.

새 도메인의 API 테스트를 추가할 때 이 파일을 복사 원본으로 쓴다:
공개 읽기 / 인증 쓰기 / 소유권 검사 / 역할 기반 필드 제한을 한 번에 보여준다.
"""

import uuid

from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> dict[str, str]:
    email = f"notice-test-{uuid.uuid4().hex[:12]}@example.com"
    await client.post(
        "/v1/auth/register", json={"email": email, "password": "a valid password 123"}
    )
    login = await client.post(
        "/v1/auth/login", json={"email": email, "password": "a valid password 123"}
    )
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_create_requires_auth(client: AsyncClient) -> None:
    r = await client.post("/v1/notices", json={"title": "제목", "content": "내용"})
    assert r.status_code == 401


async def test_create_and_list_is_public(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    r = await client.post(
        "/v1/notices", json={"title": "공지 제목", "content": "공지 내용"}, headers=headers
    )
    assert r.status_code == 201
    notice_id = r.json()["notice_id"]

    r = await client.get("/v1/notices")  # 인증 헤더 없이 공개 조회
    assert r.status_code == 200
    ids = [i["notice_id"] for i in r.json()["items"]]
    assert notice_id in ids


async def test_get_increments_view_count(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    created = (
        await client.post(
            "/v1/notices", json={"title": "조회수 테스트", "content": "c"}, headers=headers
        )
    ).json()

    await client.get(f"/v1/notices/{created['notice_id']}")
    r = await client.get(f"/v1/notices/{created['notice_id']}")
    assert r.json()["view_count"] == 2


async def test_get_nonexistent_returns_404(client: AsyncClient) -> None:
    r = await client.get("/v1/notices/999999999")
    assert r.status_code == 404


async def test_other_user_cannot_edit(client: AsyncClient) -> None:
    owner_headers = await _register_and_login(client)
    notice = (
        await client.post(
            "/v1/notices", json={"title": "원본", "content": "c"}, headers=owner_headers
        )
    ).json()

    other_headers = await _register_and_login(client)
    r = await client.patch(
        f"/v1/notices/{notice['notice_id']}", json={"title": "해킹 시도"}, headers=other_headers
    )
    assert r.status_code == 403


async def test_owner_can_edit(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    notice = (
        await client.post("/v1/notices", json={"title": "원본", "content": "c"}, headers=headers)
    ).json()

    r = await client.patch(
        f"/v1/notices/{notice['notice_id']}", json={"title": "수정됨"}, headers=headers
    )
    assert r.status_code == 200
    assert r.json()["title"] == "수정됨"


async def test_non_admin_cannot_pin(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    notice = (
        await client.post("/v1/notices", json={"title": "제목", "content": "c"}, headers=headers)
    ).json()

    r = await client.patch(
        f"/v1/notices/{notice['notice_id']}", json={"is_pinned": True}, headers=headers
    )
    assert r.status_code == 403


async def test_owner_can_delete_and_then_404(client: AsyncClient) -> None:
    headers = await _register_and_login(client)
    notice = (
        await client.post(
            "/v1/notices", json={"title": "삭제될 글", "content": "c"}, headers=headers
        )
    ).json()

    r = await client.delete(f"/v1/notices/{notice['notice_id']}", headers=headers)
    assert r.status_code == 204

    r = await client.get(f"/v1/notices/{notice['notice_id']}")
    assert r.status_code == 404


async def test_other_user_cannot_delete(client: AsyncClient) -> None:
    owner_headers = await _register_and_login(client)
    notice = (
        await client.post(
            "/v1/notices", json={"title": "원본", "content": "c"}, headers=owner_headers
        )
    ).json()

    other_headers = await _register_and_login(client)
    r = await client.delete(f"/v1/notices/{notice['notice_id']}", headers=other_headers)
    assert r.status_code == 403
