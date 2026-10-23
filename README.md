# starterkit-be

FastAPI + async SQLAlchemy(aioodbc) + MSSQL 2019 스타터킷. 새 백엔드
서비스를 시작할 때마다 반복하던 결정(디렉터리 구조, DB 세션 관리, 마이그레이션,
Docker, 배포 설정)을 코드로 고정해둔 템플릿이다.

## 용도

새 백엔드 서비스를 시작할 때 구조·DB·인증·배포 설정을 처음부터 다시 정하지 않고
바로 가져다 쓰는 FastAPI 백엔드 템플릿. 프로토타이핑과 프로덕션 시작점 모두를
목표로 한다.

## 주요 기능

- **레이어드 구조**: `Endpoint → Service → Repository → Model`. 공개 API 스키마와
  내부 DTO를 분리해 DB 컬럼이 응답으로 새지 않게 한다.
- **비동기 DB 세션 관리**: async SQLAlchemy 2.0 + aioodbc, 트랜잭션 경계(`commit()`)는
  Service에서 일원화한다.
- **JWT 인증**: Access/Refresh 토큰, Argon2 비밀번호 해시, 로그인 실패 횟수 기반
  계정 잠금, 역할 기반 접근 제어(`require_roles`). 필요 없으면 통째로 제거할 수 있다.
- **CRUD 예제 도메인(공지사항)**: 검색·페이징, 작성자 또는 admin만 수정/삭제하는
  소유권 판정. 새 도메인은 이 코드를 복사해 시작한다.
- **운영 안전장치**: 시크릿 fail-fast 설정, 요청 로그 민감정보 마스킹, 전역 예외
  처리, 헬스체크(`/health`, `/health/db`).
- **개발 도구**: Alembic 마이그레이션, OpenAPI 내보내기, 프로젝트 이름 일괄 변경
  스크립트, 단위/통합/API 3계층 테스트, ruff + mypy.

## 기술 스택

FastAPI · SQLAlchemy 2.0(async) · MSSQL 2019 · Alembic · Pydantic v2 · uv ·
Python 3.12 · Docker Compose(로컬) / Swarm(운영 템플릿) · pytest

## 이 킷으로 뭘 시작하려면

새 프로젝트를 시작할 때는 [`docs/BOOTSTRAP.md`](docs/BOOTSTRAP.md)를 따라간다.
5분 안에 로컬에서 뜨는 것만 이 README에 남기고, 나머지는 그쪽으로 뺐다.

## 빠른 시작 (이 킷 자체를 테스트해볼 때)

```bash
# 1) Python 3.12 확보 + 의존성 설치
uv python install 3.12
uv sync

# 2) 환경변수 설정
cp .env.example .env
uv run python scripts/generate_secret.py   # JWT_SECRET_KEY에 붙여넣기
# DB_HOST/DB_USER/DB_PASSWORD 등을 채운다

# 3) MSSQL 기동 (로컬 전용 compose — 운영은 Swarm)
docker compose up -d

# 4) 마이그레이션
uv run alembic upgrade head

# 5) 서버 실행
uv run uvicorn app.main:app --reload
```

`/docs`에서 Swagger UI 확인, `/health`가 무의존 헬스체크, `/health/db`가 DB 연결까지
확인하는 헬스체크다.

## 구조

```
app/
├── main.py              # 앱 조립만 (배선). 로직 금지
├── config.py             # 시크릿 fail-fast (미설정 시 부팅 자체가 실패한다)
├── api/
│   ├── deps.py           # get_current_user, require_roles — 항상 포함되는 인증 껍데기
│   ├── schemas/           # 공개 계약 (openapi.json에 그대로 나감)
│   └── v1/endpoints/      # HTTP 경계
├── core/                  # 로깅, 보안(해시/JWT), 예외, 미들웨어
├── db/
│   ├── session.py         # DatabaseSessionManager — 트랜잭션 누수 차단의 핵심
│   ├── models/            # SQLAlchemy ORM (타입 규약: app/db/models/base.py 참조)
│   ├── repositories/       # 순수 쿼리만. 정책 판단 없음
│   └── schemas/            # 내부 DTO (repository → service 경계, 비공개)
└── services/               # 비즈니스 로직 + 소유권/권한 판정 + commit() 책임
```

**계층 규칙**: `Endpoint → Service → Repository → Model`. Endpoint는 쿼리를 직접
쓰지 않는다. `commit()`은 항상 Service의 책임이다.

## 인증은 제거 가능한 슬라이스다

`app/api/deps.py`의 `get_current_user`/`require_roles`(★ 표시 없음)는 신원을
이 서비스가 자체 관리하든 외부 SSO가 넘겨주든 항상 그대로 쓴다.

반면 `core/security.py`, `db/models/{user,refresh_token}.py`,
`services/auth_service.py`, `api/v1/endpoints/auth.py` 등(파일 상단에 ★ 표시)은
**자체 로그인이 필요 없는 프로젝트라면 통째로 지워도 된다** — 예를 들어 기존
사이트에 붙는 부가 기능처럼, 신원을 이미 다른 시스템이 갖고 있는 경우.
자세한 목록은 [`docs/BOOTSTRAP.md`](docs/BOOTSTRAP.md), 설계 근거는
[`docs/AUTH.md`](docs/AUTH.md) 참조.

## 예제 도메인 (notice, 공지사항)

`notice_id`/`title`/`content`/`author_id`/`is_pinned`/`view_count`/`is_deleted`
전 계층을 관통하는 예제. 공개 읽기 + 인증 쓰기 + 소유권 검사 + 관리자 전용 필드
(상단 고정)까지, 실전에서 반복되는 패턴을 한 번에 보여준다. **새 도메인을
추가할 때 이 파일들을 복사 원본으로 쓴다** — 목록은
[`.claude/CLAUDE.md`](.claude/CLAUDE.md)의 "새 도메인 추가하기" 절 참조.

## FE 킷과의 접점

이 저장소는 커밋된 `openapi.json`으로 FE 킷과 연결된다. BE 스키마가 바뀌면:

```bash
uv run python scripts/export_openapi.py
git add openapi.json
```

FE 킷은 이 파일을 `openapi-typescript`로 소비한다 — FE 개발자가 BE를 띄우지
않고도 최신 타입을 받을 수 있다.

## 명령 모음

| 목적 | 명령 |
|---|---|
| 서버 실행 | `uv run uvicorn app.main:app --reload` |
| 린트 | `uv run ruff check .` |
| 포맷 | `uv run ruff format .` |
| 타입 체크 | `uv run mypy app/` |
| 전체 테스트 | `uv run pytest` |
| unit만 (빠름, 인프라 불필요) | `uv run pytest tests/unit` |
| 마이그레이션 생성 | `uv run alembic revision --autogenerate -m "설명"` |
| 마이그레이션 적용 | `uv run alembic upgrade head` |
| 드리프트 확인 | `uv run alembic check` |
| OpenAPI 내보내기 | `uv run python scripts/export_openapi.py` |

## 배포

로컬 개발은 `docker-compose.yml`(MSSQL만 — 앱은 `uv run uvicorn`으로 네이티브
실행), 운영은 `docker-stack.yaml`(Swarm)이다. `docker compose`는 로컬 전용이며
운영에서 쓰지 않는다.
