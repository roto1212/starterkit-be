---
name: new-domain
description: 새 도메인(테이블 + CRUD API)을 notice 예제를 원본으로 13개 파일 전체 스캐폴딩하고 마이그레이션·린트·타입·테스트·openapi까지 검증한다. "새 도메인 추가", "notice처럼 ○○ 만들어줘", "○○ CRUD 만들어줘", "/new-domain" 요청에 사용.
argument-hint: <domain_snake_name>
---

# new-domain

`notice`(예제 도메인)를 복사 원본으로 새 도메인을 만든다. 레이어 규칙은
`.claude/CLAUDE.md`가 기준이며, 이 스킬은 그 절차를 빠짐없이 수행하게 하는 체크리스트다.

## 1. 입력 확정

인자(`$ARGUMENTS`)와 요청에서 아래를 확정한다. 모호한 항목은 AskUserQuestion으로 **한 번에** 묻는다.

- 도메인명: snake_case(`faq`), PascalCase(`Faq`), URL prefix 복수형(`/faqs`), 테이블명
- 컬럼 목록 (타입/길이/NULL 여부)
- 인가 수준: 공개 읽기 / 인증 쓰기 / 소유권 검사 / admin 전용 필드
- soft delete, 조회수, 키워드 검색, 상단 고정 등 notice 기능 중 필요한 것

## 2. 원본 읽기

코드 스니펫을 이 스킬에 박지 않는다 — 원본이 바뀌어도 낡지 않도록 **먼저 Read하고 그대로 따른다**.

- `app/db/models/notice.py`, `app/db/models/__init__.py`, `app/db/models/base.py`
- `app/db/schemas/notice.py`, `app/db/repositories/notice.py`
- `app/services/notice_service.py`
- `app/api/schemas/notice.py`, `app/api/v1/endpoints/notice.py`
- `app/api/deps.py`, `app/api/v1/router.py`
- `tests/integration/test_notice_repository.py`, `tests/api/test_notice_api.py`

## 3. 생성 체크리스트

필요 없는 기능은 notice에서 빼고, 아래 13개를 모두 처리한다.

| # | 파일 | 주의 |
|---|---|---|
| 1 | `app/db/models/<d>.py` | `base.py` 별칭만(`Unicode`/`UnicodeText`/`DATETIME2_3`). `__table_args__`에 schema 재선언 금지. 인덱스명 `ix_<table>_*`, FK는 `dbo.` 접두 |
| 2 | `app/db/models/__init__.py` | `import`와 `__all__` **둘 다** 추가 (빠지면 autogenerate가 테이블을 못 본다) |
| 3 | `app/db/schemas/<d>.py` | 내부 DTO, `from_attributes=True` |
| 4 | `app/db/repositories/<d>.py` | 순수 쿼리만, 정책 판단 금지. list/count가 `_apply_search`를 공유. LIKE는 `escape_like`. BIT 비교는 `== False  # noqa: E712`(`.is_(False)`는 MSSQL 에러). 카운터는 단일 UPDATE |
| 5 | `app/services/<d>_service.py` | 소유권/권한 판정과 `commit()`은 여기서만. `NotFoundError`/`ForbiddenError` 사용, HTTP 관심사 금지 |
| 6 | `app/api/schemas/<d>.py` | 공개 계약. `is_deleted` 같은 내부 컬럼 노출 금지 |
| 7 | `app/api/v1/endpoints/<d>.py` | 쿼리·권한 판정 금지. 목록은 `PageResponse`, 인증은 `get_current_user`/`require_roles` 재사용 |
| 8 | `app/api/v1/router.py` | 라우터 등록 |
| 9 | `app/api/deps.py` | `get_<d>_service` 추가. 기존 `TYPE_CHECKING` import + 함수 내부 지연 import 패턴 유지 |
| 10 | `alembic/versions/` | 4단계 참조 |
| 11 | `tests/integration/test_<d>_repository.py` | 페이징/검색/soft delete 등 SQL 정확성 |
| 12 | `tests/api/test_<d>_api.py` | 401, 공개 조회, 소유권 403, 404 |
| 13 | `openapi.json` | 5단계에서 재생성 |

## 4. 마이그레이션

1. `uv run alembic revision --autogenerate -m "create <d> table"`
2. 생성된 리비전 검토: `nvarchar`/`DATETIME2(3)`/`server_default`/인덱스가 모델과 맞는지, **다른 테이블 변경이 섞이지 않았는지**
3. `uv run alembic upgrade head` → `uv run alembic check`

MSSQL에 연결할 수 없으면 리비전을 손으로 쓰지 말고, 이유를 보고한 뒤 중단한다.

## 5. 검증 (순서대로)

```bash
uv run ruff format .
uv run ruff check .
uv run mypy app/
uv run pytest tests/unit
uv run pytest tests/integration tests/api -k <d>
uv run python scripts/export_openapi.py
uv run python scripts/export_openapi.py --check
```

실패하면 원인을 고치고 해당 단계부터 다시 돈다. integration/api가 skip되면 **"skip됨"이라고 그대로** 보고한다(통과로 말하지 않는다).

## 6. 보고

- 생성/수정한 파일 목록, 마이그레이션 리비전 ID
- 단계별 검증 결과(통과/실패/skip)
- 사용자 확인이 필요한 결정(인가 정책 등)

커밋은 하지 않는다. 요청하면 `conventional-commit` 스킬을 쓴다.

## 하지 말 것

- notice 원본 파일 수정
- `String`/`Text`/`DateTime` 직접 사용, `datetime.utcnow()`, `datetime.now(UTC)`
- endpoint에서 repository 직접 호출 또는 쿼리 작성
- `.env` 수정, 시크릿 기본값 추가
