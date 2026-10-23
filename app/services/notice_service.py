"""app/services/notice_service.py — ★ 예제 도메인.

소유권 판정(본인 또는 admin만 수정/삭제)이 여기 있다 — 보안 로직은 BE에
둔다는 프로젝트 원칙에 따라, endpoint는 이 서비스가 던지는 ForbiddenError를
그대로 전역 핸들러로 흘려보내기만 한다.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.repositories.notice import NoticeRepository
from app.db.schemas.notice import NoticeRow


class NoticeService:
    def __init__(self, repo: NoticeRepository, db: AsyncSession) -> None:
        self.repo = repo
        self.db = db

    async def list_notices(
        self, offset: int = 0, limit: int = 20, keyword: str | None = None
    ) -> tuple[list[NoticeRow], int]:
        items = await self.repo.list(offset=offset, limit=limit, keyword=keyword)
        total = await self.repo.count(keyword=keyword)
        return items, total

    async def get_notice(self, notice_id: int, *, count_view: bool = True) -> NoticeRow:
        notice = await self.repo.get_by_id(notice_id)
        if notice is None or notice.is_deleted:
            raise NotFoundError("공지사항을 찾을 수 없습니다.")
        if count_view:
            await self.repo.increment_view(notice_id)
            await self.db.commit()
            notice = notice.model_copy(update={"view_count": notice.view_count + 1})
        return notice

    async def create_notice(self, title: str, content: str, author_id: int) -> NoticeRow:
        notice = await self.repo.create(title=title, content=content, author_id=author_id)
        await self.db.commit()
        return notice

    async def update_notice(
        self,
        notice_id: int,
        *,
        user_id: int,
        is_admin: bool,
        title: str | None = None,
        content: str | None = None,
        is_pinned: bool | None = None,
    ) -> NoticeRow:
        notice = await self._get_or_404(notice_id)
        self._check_owner_or_admin(notice, user_id=user_id, is_admin=is_admin)

        if is_pinned is not None and not is_admin:
            raise ForbiddenError("상단 고정은 관리자만 변경할 수 있습니다.")

        updated = await self.repo.update(
            notice_id, title=title, content=content, is_pinned=is_pinned
        )
        await self.db.commit()
        if updated is None:
            # _get_or_404가 통과했으니 여기 오면 안 되지만, assert는 -O 플래그로
            # 스킵될 수 있어 프로덕션에서도 반드시 걸러지도록 명시적으로 예외를 던진다.
            raise RuntimeError(f"notice {notice_id} 업데이트 직후 조회 실패 — 동시성 문제 의심")
        return updated

    async def delete_notice(self, notice_id: int, *, user_id: int, is_admin: bool) -> None:
        notice = await self._get_or_404(notice_id)
        self._check_owner_or_admin(notice, user_id=user_id, is_admin=is_admin)
        await self.repo.soft_delete(notice_id)
        await self.db.commit()

    async def _get_or_404(self, notice_id: int) -> NoticeRow:
        notice = await self.repo.get_by_id(notice_id)
        if notice is None or notice.is_deleted:
            raise NotFoundError("공지사항을 찾을 수 없습니다.")
        return notice

    @staticmethod
    def _check_owner_or_admin(notice: NoticeRow, *, user_id: int, is_admin: bool) -> None:
        if notice.author_id != user_id and not is_admin:
            raise ForbiddenError("본인이 작성한 공지사항만 수정/삭제할 수 있습니다.")
