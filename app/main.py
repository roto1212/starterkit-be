"""app/main.py

앱 조립만 담당한다 — 로직은 여기 두지 않는다. 라우팅/비즈니스 로직이
필요하면 app/api 와 app/services 로 간다.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import router as api_v1_router
from app.config import settings
from app.core.exception_handlers import add_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import FileSizeMiddleware, RequestLoggingMiddleware
from app.db.session import get_db, sessionmanager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging(level=settings.LOG_LEVEL)
    sessionmanager.init(settings.db_url_async)
    yield
    await sessionmanager.close()


app = FastAPI(title="starterkit-be", lifespan=lifespan)

# 미들웨어는 나중에 추가한 것이 요청 처리 순서상 바깥쪽(먼저 실행)이 된다.
# 의도한 실행 순서: CORS → 업로드 크기 검증 → 요청 로깅 → 라우터
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(FileSizeMiddleware, max_size=20 * 1024 * 1024)  # 프로젝트에 맞게 조정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,  # refresh_token 쿠키를 쓰므로 필요
    allow_methods=["*"],
    allow_headers=["*"],
)

add_exception_handlers(app)

app.include_router(api_v1_router)


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    """무의존 헬스체크 — DB 등 외부 의존성을 절대 조회하지 않는다.
    헬스체크가 도메인 서비스를 호출하면, 그 서비스의 버그가 헬스체크를 깨뜨린다."""
    return {"status": "ok"}


@app.get("/health/db", include_in_schema=False)
async def health_db(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """DB 연결까지 확인하는 헬스체크. 배포 파이프라인이 DB 마이그레이션
    완료를 기다려야 할 때만 이걸 쓴다 — 일반 liveness 체크는 /health로 충분."""
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
