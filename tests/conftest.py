"""tests/conftest.py

3계층 구조:
- tests/unit/         인프라 없음. 순수 함수만 (core/security.py, LIKE 이스케이프, config validator)
- tests/integration/  실제 MSSQL. 리포지토리/서비스를 HTTP 없이 직접 검증
- tests/api/          아래 db_session을 get_db에 꽂아 재사용 (tests/api/conftest.py)

.env가 없거나 MSSQL에 연결할 수 없으면 db_session에 의존하는 테스트는 자동으로
skip된다. unit만 빠르게 돌리려면:
    uv run pytest tests/unit

db_session/db_connection/_migrated fixture가 여기(최상위)에 있는 이유: tests/api가
tests/integration의 DB 격리 방식을 그대로 재사용해야 하는데, pytest는 형제
디렉터리 간 conftest.py 공유를 지원하지 않는다 — 공통 조상인 여기 두면 양쪽 다
쓸 수 있다.
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio


@pytest_asyncio.fixture(scope="session")
async def _migrated() -> AsyncIterator[None]:
    try:
        from app.config import settings  # noqa: F401
    except Exception as e:
        pytest.skip(f".env 설정이 없어 DB 관련 테스트를 건너뜁니다: {e}")

    from alembic.config import Config

    from alembic import command

    try:
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")  # 마이그레이션이 매 테스트런마다 검증된다
    except Exception as e:
        pytest.skip(f"MSSQL에 연결할 수 없어 DB 관련 테스트를 건너뜁니다: {e}")

    yield


@pytest_asyncio.fixture
async def db_connection(_migrated: None):
    """트랜잭션 하나를 열어둔 커넥션. db_session이 이 위에 SAVEPOINT로 올라탄다."""
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.config import settings

    engine = create_async_engine(settings.db_url_async)
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            yield conn
        finally:
            await trans.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_connection):
    """서비스/리포지토리/API 테스트용 세션. commit()을 호출해도 SAVEPOINT로
    흡수되어, 바깥 트랜잭션이 db_connection fixture 종료 시 통째로 롤백된다
    — 테스트가 dev DB에 흔적을 남기지 않고, 테스트 간 순서 의존도 생기지 않는다."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    maker = async_sessionmaker(
        bind=db_connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    session: AsyncSession = maker()
    try:
        yield session
    finally:
        await session.close()
