"""app/db/repositories/notice.py — ★ 예제 도메인. 순수 쿼리만 담당한다."""

from typing import Any

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notice import Notice
from app.db.repositories._like import escape_like
from app.db.schemas.notice import NoticeRow


class NoticeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _apply_search(stmt: Select[Any], keyword: str | None) -> Select[Any]:
        """검색 조건을 붙인다 — list()와 count()가 같은 조건을 쓰게 하려고 분리했다.
        조건이 두 곳에 흩어지면 "5건 중 1-20" 같은 어긋난 페이징이 나온다."""
        # .is_(False)가 아니라 == False 를 쓴다: MSSQL은 BIT 컬럼에 대해 "IS 0" 구문을
        # 지원하지 않는다(ANSI IS 술어는 NULL 전용) — 실제로 "Incorrect syntax near '0'"
        # 런타임 에러로 확인됨. == False 는 "= 0"으로 렌더링되어 정상 동작한다.
        stmt = stmt.where(Notice.is_deleted == False)  # noqa: E712
        if keyword:
            pattern = f"%{escape_like(keyword)}%"
            stmt = stmt.where(
                Notice.title.ilike(pattern, escape="\\")
                | Notice.content.ilike(pattern, escape="\\")
            )
        return stmt

    async def list(
        self, offset: int = 0, limit: int = 20, keyword: str | None = None
    ) -> list[NoticeRow]:
        stmt = self._apply_search(select(Notice), keyword)
        stmt = (
            stmt.order_by(
                Notice.is_pinned.desc(), Notice.created_at.desc(), Notice.notice_id.desc()
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [NoticeRow.model_validate(n) for n in result.scalars().all()]

    async def count(self, keyword: str | None = None) -> int:
        stmt = self._apply_search(select(func.count()).select_from(Notice), keyword)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_by_id(self, notice_id: int) -> NoticeRow | None:
        result = await self.db.execute(select(Notice).where(Notice.notice_id == notice_id))
        row = result.scalar_one_or_none()
        return NoticeRow.model_validate(row) if row else None

    async def create(self, title: str, content: str, author_id: int) -> NoticeRow:
        notice = Notice(title=title, content=content, author_id=author_id)
        self.db.add(notice)
        await self.db.flush()
        await self.db.refresh(notice)
        return NoticeRow.model_validate(notice)

    async def update(
        self,
        notice_id: int,
        *,
        title: str | None = None,
        content: str | None = None,
        is_pinned: bool | None = None,
    ) -> NoticeRow | None:
        values = {
            k: v
            for k, v in {"title": title, "content": content, "is_pinned": is_pinned}.items()
            if v is not None
        }
        if not values:
            return await self.get_by_id(notice_id)

        await self.db.execute(update(Notice).where(Notice.notice_id == notice_id).values(**values))
        await self.db.flush()
        return await self.get_by_id(notice_id)

    async def soft_delete(self, notice_id: int) -> None:
        await self.db.execute(
            update(Notice).where(Notice.notice_id == notice_id).values(is_deleted=True)
        )
        await self.db.flush()

    async def increment_view(self, notice_id: int) -> None:
        """단일 UPDATE 문으로 원자적 증가. SELECT 후 +1 해서 UPDATE하면
        동시 조회 시 카운트가 유실된다."""
        await self.db.execute(
            update(Notice)
            .where(Notice.notice_id == notice_id)
            .values(view_count=Notice.view_count + 1)
        )
        await self.db.flush()
