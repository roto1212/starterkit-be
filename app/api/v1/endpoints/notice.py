"""app/api/v1/endpoints/notice.py — ★ 예제 도메인.

목록/상세 조회는 공개, 작성/수정/삭제는 인증 필요 — 두 인가 수준이 한
도메인에 섞인 흔한 실전 패턴을 보여준다.
"""

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, get_current_user, get_notice_service
from app.api.schemas.common import PageResponse
from app.api.schemas.notice import NoticeCreate, NoticeResponse, NoticeUpdate
from app.services.notice_service import NoticeService

router = APIRouter(prefix="/notices", tags=["notices"])


def _to_response(row: object) -> NoticeResponse:
    return NoticeResponse.model_validate(row, from_attributes=True)


@router.get("", response_model=PageResponse[NoticeResponse])
async def list_notices(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None, max_length=200),
    notice_service: NoticeService = Depends(get_notice_service),
) -> PageResponse[NoticeResponse]:
    items, total = await notice_service.list_notices(offset=offset, limit=limit, keyword=keyword)
    return PageResponse(
        items=[_to_response(i) for i in items], total=total, offset=offset, limit=limit
    )


@router.get("/{notice_id}", response_model=NoticeResponse)
async def get_notice(
    notice_id: int,
    notice_service: NoticeService = Depends(get_notice_service),
) -> NoticeResponse:
    notice = await notice_service.get_notice(notice_id)
    return _to_response(notice)


@router.post("", response_model=NoticeResponse, status_code=status.HTTP_201_CREATED)
async def create_notice(
    body: NoticeCreate,
    user: CurrentUser = Depends(get_current_user),
    notice_service: NoticeService = Depends(get_notice_service),
) -> NoticeResponse:
    notice = await notice_service.create_notice(
        title=body.title, content=body.content, author_id=user.user_id
    )
    return _to_response(notice)


@router.patch("/{notice_id}", response_model=NoticeResponse)
async def update_notice(
    notice_id: int,
    body: NoticeUpdate,
    user: CurrentUser = Depends(get_current_user),
    notice_service: NoticeService = Depends(get_notice_service),
) -> NoticeResponse:
    notice = await notice_service.update_notice(
        notice_id,
        user_id=user.user_id,
        is_admin=user.has_role("admin"),
        title=body.title,
        content=body.content,
        is_pinned=body.is_pinned,
    )
    return _to_response(notice)


@router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notice(
    notice_id: int,
    user: CurrentUser = Depends(get_current_user),
    notice_service: NoticeService = Depends(get_notice_service),
) -> None:
    await notice_service.delete_notice(
        notice_id, user_id=user.user_id, is_admin=user.has_role("admin")
    )
