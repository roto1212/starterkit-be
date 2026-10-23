# 새 프로젝트 시작하기

GitHub template로 "Use this template"한 뒤 이 체크리스트를 따라간다.

## 1. Python 확보 + 의존성

```bash
uv python install 3.12
uv sync
```

pyenv 전역이 3.11.9여도 상관없다 — `pyproject.toml`의
`[tool.uv] python-preference = "managed"`가 uv 자체 관리 3.12를 쓰게 만든다.

## 2. 환경변수

```bash
cp .env.example .env
uv run python scripts/generate_secret.py   # 출력값을 JWT_SECRET_KEY에 붙여넣기
```

`.env`의 `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD`를 채운다.
**아래 값 그대로 두면 부팅 자체가 실패한다** — `app/config.py`의 fail-fast
장치가 의도한 동작이다:

- `JWT_SECRET_KEY`가 `.env.example`의 플레이스홀더 문자열 그대로면 거부
- `JWT_SECRET_KEY`가 32자 미만이면 거부
- `ENV=prod`인데 `CORS_ORIGINS=*` 또는 `COOKIE_SECURE=false`면 거부

## 3. 프로젝트명 치환

```bash
uv run python scripts/rename_project.py --name my-service          # 미리보기
uv run python scripts/rename_project.py --name my-service --apply  # 실제 적용
```

**`ALEMBIC_VERSION_TABLE`을 반드시 확인한다.** 운영 환경은 공유 MSSQL
인스턴스라, 이 값을 안 바꾸면 두 프로젝트가 같은 버전 테이블을 보고 서로의
Alembic 리비전을 덮어쓴다 — 다른 항목(컨테이너 이름 등)과 달리 이건 나중에
조용히 터진다. `rename_project.py`가 `.env.example`은 갱신하지만 이미 만들어둔
`.env`는 손대지 않으니, 2단계에서 이미 `.env`를 만들었다면 여기서 직접
`ALEMBIC_VERSION_TABLE`을 맞춰준다.

## 4. DB 기동 + 마이그레이션

```bash
docker compose up -d
uv run alembic upgrade head
```

이미 공유 MSSQL이 떠 있다면 `docker compose up -d`는 생략하고 `.env`의
`DB_HOST`/`DB_PORT`만 그 인스턴스에 맞추면 된다.

## 5. 실행 확인

```bash
uv run uvicorn app.main:app --reload
```

`http://localhost:8000/docs`에서 Swagger UI가 뜨고 상단에 프로젝트명이
보이는지 확인한다.

## 6. 인증 슬라이스 결정 — 이 프로젝트에 자체 로그인이 필요한가?

**필요 없다면** (예: 기존 사이트에 붙는 부가 기능처럼 신원을 이미 다른 시스템이
갖고 있는 경우) 아래 파일을 지운다. `app/api/deps.py`의 `get_current_user`는
그대로 두되, `credentials`/`decode_access_token` 검증 부분을 신원을 넘겨주는
외부 시스템의 검증 로직으로 바꾼다 — `CurrentUser`를 반환한다는 계약만
지키면 나머지(각 엔드포인트의 `Depends(get_current_user)`)는 그대로 쓸 수 있다.

삭제 대상 (파일 상단에 `★ 신원 저장소 슬라이스` 표시):
```
app/core/security.py
app/db/models/user.py
app/db/models/refresh_token.py
app/db/repositories/user.py
app/db/repositories/refresh_token.py
app/db/schemas/user.py
app/db/schemas/refresh_token.py
app/services/auth_service.py
app/api/schemas/auth.py
app/api/v1/endpoints/auth.py
tests/unit/test_security.py
tests/api/test_auth_api.py
```
그리고 `app/api/v1/router.py`에서 `auth` 라우터 등록을 지우고,
`app/api/deps.py`의 `get_auth_service`와 관련 import를 지운다.
`alembic/versions/`의 최초 마이그레이션은 `app_user`/`auth_refresh_token`
테이블 생성분을 새 마이그레이션으로 덮어쓰거나(`alembic revision --autogenerate`),
그대로 두고 그냥 안 쓰는 테이블로 남겨도 무방하다(권장은 새로 정리).

**필요하다면** 그대로 둔다. 설계 근거는 [`AUTH.md`](AUTH.md) 참조.

## 7. 예제 도메인(notice) 처리

`notice`를 지울지, 첫 실제 도메인의 이름만 바꿔 쓸지 정한다. 파일 목록은
[`.claude/CLAUDE.md`](../.claude/CLAUDE.md)의 "새 도메인 추가하기" 절 참조.

## 8. FE 킷에 타입 넘기기

```bash
uv run python scripts/export_openapi.py
git add openapi.json
```

## 9. 운영 배포 전 확인

- `.env`의 `ENV=prod`, `COOKIE_SECURE=true`, `CORS_ORIGINS`를 실제 도메인으로
  — 셋 중 하나라도 안 맞으면 부팅이 거부되므로 사실상 자동 강제된다.
- `docker-stack.yaml`의 서비스명·이미지명이 `rename_project.py`로 갱신됐는지 확인.
