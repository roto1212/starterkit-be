# starterkit-be

FastAPI + async SQLAlchemy(aioodbc) + MSSQL 2019 스타터킷. 자세한 배경은
[`../README.md`](../README.md), 인증 설계는 [`../docs/AUTH.md`](../docs/AUTH.md),
새 프로젝트 시작 절차는 [`../docs/BOOTSTRAP.md`](../docs/BOOTSTRAP.md) 참조.

## Architecture — 요청 흐름

```
HTTP 요청
  → Endpoint (app/api/v1/endpoints/*.py)      쿼리 직접 작성 금지
  → Service   (app/services/*.py)             비즈니스 로직 + commit() 책임
  → Repository (app/db/repositories/*.py)     순수 쿼리만. 정책 판단 없음
  → Model     (app/db/models/*.py)            SQLAlchemy ORM
```

| 레이어 | 책임 | 하지 않는 것 |
|---|---|---|
| Endpoint | HTTP 파싱, 상태 코드, 쿠키 set/delete | DB 쿼리, 권한 판정 로직 |
| Service | 소유권/권한 판정, 트랜잭션 경계(`commit()`) | HTTP 관심사(쿠키/헤더) |
| Repository | SQL 실행, 검색/페이징 | 소유권 판정, 락 정책 결정 |
| Model | 테이블 매핑 | — |

`api/schemas/`(공개 계약, openapi.json에 나감) vs `db/schemas/`(repository→service
내부 DTO, 비공개)는 의도적으로 분리되어 있다. 합치면 DB 컬럼이 FE로 그대로
새어 나간다.

## Commands

```bash
uv run uvicorn app.main:app --reload        # 로컬 서버
uv run ruff check .                         # 린트
uv run ruff format .                        # 포맷
uv run mypy app/                            # 타입 체크
uv run pytest                               # 전체 테스트 (unit+integration+api)
uv run pytest tests/unit                    # unit만 (인프라 불필요, 빠름)
uv run alembic revision --autogenerate -m "설명"
uv run alembic upgrade head
uv run alembic check                        # 모델-DB 드리프트 확인
uv run python scripts/export_openapi.py     # openapi.json 갱신 (FE 킷용)
uv run python scripts/rename_project.py --name my-service --apply
```

## 모델 타입 규약 (필수)

`app/db/models/base.py`의 별칭만 쓴다:
- 문자열: `Unicode`/`UnicodeText` (❌ `String`/`Text`)
- 타임스탬프: `DATETIME2_3` (❌ `DateTime` 직접 사용)
- 현재시각: `utcnow_naive()` (❌ `datetime.utcnow()` — deprecated. ❌ `datetime.now(UTC)` 그대로 —
  MSSQL DATETIME2는 naive라 DB에서 읽은 값과 비교 시 `TypeError` 남)
- 스키마: `Base.metadata`에서 전역 지정됨(`dbo`) — 테이블마다 `__table_args__`로
  다시 선언하지 않는다

이 규약을 지켜야 `alembic/env.py`의 `compare_type=True`가 진짜 드리프트만 잡는다
(어기면 `String` vs `nvarchar` 같은 가짜 드리프트가 다시 생긴다).

## 새 도메인 추가하기

`notice`(공지사항, `app/**/notice.py` 및 `tests/**/*notice*.py`)를 복사 원본으로
쓴다. 이름만 바꿔서 아래 파일 전부를 만든다:

```
app/db/models/<domain>.py                          모델
app/db/models/__init__.py                           import 추가 (autogenerate 진입점)
app/db/schemas/<domain>.py                           내부 DTO
app/db/repositories/<domain>.py                      쿼리
app/services/<domain>_service.py                     비즈니스 로직 + commit()
app/api/schemas/<domain>.py                           공개 계약 (Create/Update/Response)
app/api/v1/endpoints/<domain>.py                      HTTP 라우트
app/api/v1/router.py                                  라우터 등록
app/api/deps.py                                       get_<domain>_service 팩토리
alembic/versions/                                     `alembic revision --autogenerate` 로 생성
tests/integration/test_<domain>_repository.py         리포지토리 직접 테스트
tests/api/test_<domain>_api.py                        HTTP 계층 테스트
openapi.json                                          `scripts/export_openapi.py` 로 재생성
```

## 인증은 제거 가능한 슬라이스다

파일 상단에 `★ 신원 저장소 슬라이스`라고 적힌 파일들(`core/security.py`,
`db/models/{user,refresh_token}.py`, `services/auth_service.py`,
`api/v1/endpoints/auth.py` 등)은 자체 로그인이 필요 없는 프로젝트(예: 신원을
이미 다른 시스템이 갖고 있는 기능 부착 프로젝트)에서 통째로 지워도 된다.
`api/deps.py`의 `get_current_user`/`require_roles`(★ 표시 없음)는 항상 남는다
— 신원 소스만 바꿔 끼우면 된다. 절차는 [`docs/BOOTSTRAP.md`](../docs/BOOTSTRAP.md)
6단계 참조.

## 시크릿

`app/config.py`는 fail-fast다 — 필수 필드 미설정, 플레이스홀더 시크릿,
`ENV=prod`에서의 안전하지 않은 CORS/쿠키 설정은 전부 부팅 자체를 막는다.
새 시크릿 필드를 추가할 때도 기본값을 두지 않는다(`.env.example`엔 placeholder만).

## 테스트 3계층

`tests/unit`(인프라 없음) / `tests/integration`(실제 MSSQL, 리포지토리·서비스
직접 검증) / `tests/api`(httpx `AsyncClient` + `ASGITransport`, `db_session`을
`get_db`에 override). `tests/api`가 Starlette `TestClient`가 아니라
`httpx.AsyncClient`를 쓰는 이유: `TestClient`는 별도 스레드의 독립된 이벤트
루프에서 앱을 돌려서, pytest-asyncio가 관리하는 `db_session`과 이벤트 루프가
어긋나 `RuntimeError: ... attached to a different loop`가 난다(실제로 겪은 문제).

integration/api 테스트는 `.env`가 없거나 MSSQL에 연결할 수 없으면 자동으로
skip된다(`tests/conftest.py`의 `_migrated` fixture).
