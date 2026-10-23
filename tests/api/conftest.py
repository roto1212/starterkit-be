"""tests/api/conftest.py

httpx.AsyncClient + ASGITransport로 앱을 직접 호출한다 — 실제 소켓을 열지
않으므로 "서버 기동"이 필요 없다.

Starlette TestClient가 아니라 이걸 쓰는 이유: TestClient는 내부적으로 별도
스레드의 독립된 이벤트 루프에서 앱을 실행하는데, db_session fixture는
pytest-asyncio가 관리하는 (다른) 이벤트 루프의 커넥션에 바인딩되어 있어서
"attached to a different loop" 런타임 에러가 난다(실제로 겪은 문제). 테스트
함수 자체를 비동기로 만들고 AsyncClient를 쓰면 요청 처리와 db_session이
같은 이벤트 루프를 공유해 이 문제가 사라진다.

db_session fixture는 최상위 tests/conftest.py에 있다 (tests/integration과 공유).
"""

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    from app.db.session import get_db
    from app.main import app

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
