"""app/api/v1/router.py

새 도메인을 추가하면 여기에 라우터를 등록한다.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, notice

router = APIRouter(prefix="/v1")
router.include_router(auth.router)
router.include_router(notice.router)
