"""app/db/session.py

대상: MSSQL (Microsoft SQL Server)
드라이버: aioodbc (mssql+aioodbc)
용도: FastAPI Depends 기반 비동기 DB 세션

⚠️ 사전 요구사항 (코드로 보장 불가, 환경에서 반드시 확인):
  1) OS에 ODBC Driver 설치 (예: "ODBC Driver 18 for SQL Server" / msodbcsql18)
  2) settings.db_url_async 가 올바른 형태인지 (app/config.py 참조)
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator

from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class DatabaseSessionManager:
    """
    AsyncEngine + AsyncSession 라이프사이클 관리.
    FastAPI lifespan에서 init() / close()를 호출한다.

    MSSQL에는 유휴 트랜잭션 서버측 자동 종료 기능이 없으므로,
    트랜잭션 누수 차단은 get_db()의 finally 강제 정리로 달성한다.
    """

    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker[AsyncSession] | None = None

    def init(
        self,
        db_url: str,
        *,
        echo: bool = False,
        pool_size: int = 20,
        max_overflow: int = 10,
        pool_recycle: int = 1800,
    ) -> None:
        """엔진 초기화 — FastAPI lifespan에서 호출. 실패 시 예외를 그대로 전파한다."""
        if self._engine is not None:
            logger.warning("DatabaseSessionManager is already initialized")
            return

        masked_url = self._mask_url(db_url)
        logger.info(f"Initializing async MSSQL engine: {masked_url}")

        # ⚠️ AUTOCOMMIT 미사용: 트랜잭션 원자성(rollback) 보존이 최우선.
        # 초기화 실패는 삼키지 않고 전파시켜 부팅을 중단한다(빠른 실패).
        self._engine = create_async_engine(
            db_url,
            echo=echo,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,  # 30분마다 풀 재생성
            pool_pre_ping=True,  # 죽은 커넥션 감지
            pool_reset_on_return="rollback",  # 풀 반환 시 미완 트랜잭션 정리
        )

        self._sessionmaker = async_sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
        )
        logger.info("MSSQL engine and sessionmaker initialized successfully")

    async def close(self) -> None:
        """엔진 종료 — FastAPI lifespan에서 호출"""
        if self._engine is None:
            logger.warning("DatabaseSessionManager is not initialized, skipping close")
            return

        await asyncio.shield(self._engine.dispose())
        self._engine = None
        self._sessionmaker = None
        logger.info("MSSQL engine disposed")

    @property
    def is_initialized(self) -> bool:
        return self._engine is not None

    @contextlib.asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """
        세션 컨텍스트.
        - 정상 종료: 호출부 책임으로 commit (commit 누락 시 finally에서 rollback → 누수 없음)
        - 예외 발생: rollback 후 재전파
        - 어떤 경우든 finally에서 rollback + close로 트랜잭션/커넥션을 확실히 회수
        """
        if self._sessionmaker is None:
            raise RuntimeError("DatabaseSessionManager is not initialized")

        session = self._sessionmaker()
        try:
            yield session
        except Exception:
            logger.exception("Exception in session context. Rolling back.")
            await asyncio.shield(session.rollback())
            raise
        finally:
            try:
                if session.in_transaction():
                    # 미저장 변경이 실제로 있는지 확인 (조회는 여기 안 걸림)
                    has_pending_changes = bool(session.new or session.dirty or session.deleted)
                    if has_pending_changes:
                        logger.warning(
                            "Uncommitted changes detected on session exit "
                            "(commit 누락 가능성). Rolling back — 변경사항이 저장되지 않습니다. "
                            f"new={len(session.new)}, dirty={len(session.dirty)}, "
                            f"deleted={len(session.deleted)}"
                        )
                    else:
                        # 조회만 한 정상 케이스: 열린 (빈) 트랜잭션을 조용히 정리
                        logger.debug("Closing read-only transaction (no pending changes).")
                    await asyncio.shield(session.rollback())
            except Exception as cleanup_err:
                logger.warning(f"Rollback during cleanup failed: {cleanup_err}")
            finally:
                await asyncio.shield(session.close())

    @staticmethod
    def _mask_url(url: str) -> str:
        """DB URL에서 비밀번호를 마스킹"""
        try:
            from sqlalchemy import make_url

            parsed = make_url(url)
            return str(parsed.set(password="****")) if parsed.password else url  # noqa: S106
        except Exception:
            return "****"


# 전역 싱글턴 (초기화는 lifespan에서)
sessionmanager = DatabaseSessionManager()


async def get_db() -> AsyncIterator[AsyncSession]:
    """
    FastAPI Depends용 DB 세션 제공자.

    사용 예:
        @router.post("/items")
        async def create_item(db: AsyncSession = Depends(get_db)):
            db.add(item)
            await db.commit()   # ← commit은 호출부(서비스 계층) 책임. 누락 시 자동 rollback됨.
    """
    async with sessionmanager.session() as session:
        yield session
