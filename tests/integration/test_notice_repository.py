"""tests/integration/test_notice_repository.py — ★ 예제 도메인.

새 도메인을 추가할 때 이 파일을 리포지토리 테스트의 복사 원본으로 쓴다.
HTTP 계층을 거치지 않고 리포지토리를 직접 검증한다 — 페이징/검색처럼
API 응답 형태만 봐서는 못 잡는 SQL 자체의 정확성이 여기서 드러난다.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.notice import NoticeRepository
from app.db.repositories.user import UserRepository


async def _make_user(db_session: AsyncSession, email: str) -> int:
    user = await UserRepository(db_session).create(email, password_hash="x")
    await db_session.flush()
    return user.user_id


async def test_create_and_get_by_id(db_session: AsyncSession) -> None:
    repo = NoticeRepository(db_session)
    author_id = await _make_user(db_session, "notice-author-1@example.com")

    created = await repo.create(title="제목", content="내용", author_id=author_id)
    fetched = await repo.get_by_id(created.notice_id)

    assert fetched is not None
    assert fetched.title == "제목"
    assert fetched.author_id == author_id


async def test_list_excludes_soft_deleted(db_session: AsyncSession) -> None:
    repo = NoticeRepository(db_session)
    author_id = await _make_user(db_session, "notice-author-2@example.com")

    kept = await repo.create(title="유지됨", content="c", author_id=author_id)
    deleted = await repo.create(title="삭제됨", content="c", author_id=author_id)
    await repo.soft_delete(deleted.notice_id)

    items = await repo.list(limit=100)
    ids = {i.notice_id for i in items}
    assert kept.notice_id in ids
    assert deleted.notice_id not in ids


async def test_list_pinned_first_then_newest(db_session: AsyncSession) -> None:
    repo = NoticeRepository(db_session)
    author_id = await _make_user(db_session, "notice-author-3@example.com")

    first = await repo.create(title="먼저 작성", content="c", author_id=author_id)
    second = await repo.create(title="나중 작성 + 고정", content="c", author_id=author_id)
    await repo.update(second.notice_id, is_pinned=True)

    items = await repo.list(limit=100)
    ids_in_order = [i.notice_id for i in items]
    # 고정된 글(나중에 썼지만)이 먼저 작성한 일반 글보다 앞에 와야 한다
    assert ids_in_order.index(second.notice_id) < ids_in_order.index(first.notice_id)


async def test_search_matches_title_and_content(db_session: AsyncSession) -> None:
    repo = NoticeRepository(db_session)
    author_id = await _make_user(db_session, "notice-author-4@example.com")

    await repo.create(title="점검 안내", content="이번 주 금요일 점검합니다", author_id=author_id)
    await repo.create(title="휴가 안내", content="상관없는 내용", author_id=author_id)

    by_title = await repo.list(limit=100, keyword="점검")
    assert len(by_title) == 1
    assert by_title[0].title == "점검 안내"


async def test_search_escapes_like_wildcards(db_session: AsyncSession) -> None:
    """검색어에 %가 들어가면 "모든 행"이 아니라 "%가 실제로 들어간 행"만 나와야 한다."""
    repo = NoticeRepository(db_session)
    author_id = await _make_user(db_session, "notice-author-5@example.com")

    await repo.create(title="할인 50%", content="c", author_id=author_id)
    await repo.create(title="관련없는 글", content="c", author_id=author_id)

    results = await repo.list(limit=100, keyword="50%")
    assert len(results) == 1
    assert results[0].title == "할인 50%"


async def test_count_matches_search_filter(db_session: AsyncSession) -> None:
    """list()와 count()가 같은 조건을 쓰는지 확인한다 — 어긋나면 페이징 total이 틀어진다."""
    repo = NoticeRepository(db_session)
    author_id = await _make_user(db_session, "notice-author-6@example.com")

    for i in range(3):
        await repo.create(title=f"검색어포함-{i}", content="c", author_id=author_id)
    await repo.create(title="무관한 글", content="c", author_id=author_id)

    count = await repo.count(keyword="검색어포함")
    items = await repo.list(limit=100, keyword="검색어포함")
    assert count == 3
    assert len(items) == 3


async def test_increment_view_is_atomic_update(db_session: AsyncSession) -> None:
    repo = NoticeRepository(db_session)
    author_id = await _make_user(db_session, "notice-author-7@example.com")
    notice = await repo.create(title="조회수 테스트", content="c", author_id=author_id)

    await repo.increment_view(notice.notice_id)
    await repo.increment_view(notice.notice_id)

    fetched = await repo.get_by_id(notice.notice_id)
    assert fetched is not None
    assert fetched.view_count == 2
