"""app/config.py

시크릿은 기본값을 두지 않는다 — 이 모듈이 앱 import 체인의 최상단이므로,
필수 필드가 비어있으면 uvicorn이 기동조차 못 하고 즉시 실패한다(fail-fast).
.env.example 은 플레이스홀더만 담고, 실제 값은 각 개발자가 .env 에 채운다.
"""

import os
from urllib.parse import quote_plus

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env.example 에 박아둔 플레이스홀더 원문. 이 값 그대로 배포되는 사고를 막기 위해
# JWT_SECRET_KEY 가 이 문자열과 같으면 fail-fast 시킨다.
_JWT_SECRET_PLACEHOLDER = "CHANGE_ME_run_scripts_generate_secret_to_create_a_real_key"  # noqa: S105


class Settings(BaseSettings):
    ENV: str = "dev"  # dev | prod

    # ── DB ──
    # DB_ENGINE 문자열을 통째로 env 에서 받지 않는다. 부품만 받아 앱이 URL을 조립한다.
    # (레퍼런스 프로젝트는 .env 의 DB_ENGINE=...${DB_USER_ID}... 형태가 env_file 에서
    #  ${} 로 전개되지 않아, docker-compose.yml 의 environment: 블록으로 재조립하는
    #  우회를 써야 했다. 부품만 넘기면 이 문제 자체가 없다.)
    DB_HOST: str
    DB_PORT: int = 1433
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: SecretStr
    DB_ODBC_DRIVER: str = "ODBC Driver 18 for SQL Server"

    # 공유 MSSQL 인스턴스에 여러 프로젝트가 붙는 현실 때문에 반드시 프로젝트마다
    # 바꿔야 하는 값. scripts/rename_project.py 가 자동으로 갱신한다.
    ALEMBIC_VERSION_TABLE: str = "alembic_version"

    # ── 인증 (신원 저장소 슬라이스 — 삭제 시 이 3개 필드도 함께 제거) ──
    JWT_SECRET_KEY: SecretStr
    JWT_ISSUER: str = "starterkit-be"
    JWT_AUDIENCE: str = "starterkit-be-clients"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # 로그인 브루트포스 방어 (DB 컬럼 기반 — Redis 불필요. docs/AUTH.md 참조)
    LOGIN_FAIL_WINDOW_SEC: int = 600
    LOGIN_FAIL_MAX: int = 10
    LOGIN_LOCK_SEC: int = 300

    # ── 로깅 ──
    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: str = "rich"  # rich(로컬) | json(운영)

    # ── CORS / 쿠키 ──
    CORS_ORIGINS: str = ""  # 콤마 구분. 비우면 전부 거부(prod 기본 안전)
    COOKIE_SECURE: bool = True  # 로컬 .env 에서만 false

    # 테스트에서는 conftest.py가 monkeypatch.setenv로 필드를 직접 덮어쓴다
    # (tests/integration/conftest.py). 별도 .env.test 파일은 두지 않는다.
    model_config = SettingsConfigDict(env_file=os.environ.get("ENV_FILE", ".env"), extra="forbid")

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _reject_weak_jwt_secret(cls, v: SecretStr) -> SecretStr:
        raw = v.get_secret_value()
        if raw == _JWT_SECRET_PLACEHOLDER:
            raise ValueError(
                "JWT_SECRET_KEY 가 .env.example 의 플레이스홀더 그대로입니다. "
                "uv run python scripts/generate_secret.py 로 실제 키를 생성해 .env 에 넣으세요."
            )
        if len(raw) < 32:
            raise ValueError("JWT_SECRET_KEY 는 최소 32자 이상이어야 합니다.")
        return v

    @model_validator(mode="after")
    def _prod_guards(self) -> "Settings":
        if self.ENV == "prod":
            if not self.CORS_ORIGINS or self.CORS_ORIGINS.strip() == "*":
                raise ValueError(
                    "ENV=prod 에서는 CORS_ORIGINS 를 실제 허용 도메인으로 명시해야 합니다 "
                    "('*' 또는 미설정 불가)."
                )
            if not self.COOKIE_SECURE:
                raise ValueError("ENV=prod 에서는 COOKIE_SECURE=true 여야 합니다.")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def db_url_async(self) -> str:
        """런타임용 — aioodbc(비동기)."""
        return self._build_db_url("mssql+aioodbc")

    @property
    def db_url_sync(self) -> str:
        """Alembic 마이그레이션용 — pyodbc(동기)."""
        return self._build_db_url("mssql+pyodbc")

    def _build_db_url(self, dialect_driver: str) -> str:
        password = quote_plus(self.DB_PASSWORD.get_secret_value())
        user = quote_plus(self.DB_USER)
        driver = quote_plus(self.DB_ODBC_DRIVER)
        return (
            f"{dialect_driver}://{user}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?driver={driver}&TrustServerCertificate=yes&MARS_Connection=Yes"
        )


settings = Settings()  # type: ignore[call-arg]  # 필드는 .env 에서 채워짐
