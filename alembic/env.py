"""alembic/env.py

런타임(aioodbc, 비동기)과 마이그레이션(pyodbc, 동기)은 드라이버가 다르다.
비밀번호는 alembic.ini에 적지 않고 app.config.settings에서 가져온다.
"""

from logging.config import fileConfig
from typing import Any

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.config import settings
from app.db.models import Base

config = context.config

# alembic.ini에 sqlalchemy.url을 비워둔 이유: 비밀번호를 커밋하지 않기 위해.
# configparser는 %를 보간 문법으로 해석하므로, URL 인코딩된 비밀번호(quote_plus 결과)에
# 든 %XX 시퀀스가 그대로 들어가면 깨진다 — %%로 이스케이프해야 한다.
config.set_main_option("sqlalchemy.url", settings.db_url_sync.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _include_object(
    object: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
) -> bool:
    """FK 제약은 항상 비교 대상에서 뺀다 — 프로젝트 특수 사정이 아니라
    SQLAlchemy MSSQL 방언 자체의 한계다: 기본 스키마(dbo)의 테이블을 리플렉션하면
    FK가 참조하는 테이블의 schema가 항상 None으로 보고되는데, 모델은 schema="dbo"를
    명시하므로 매번 "제거 후 추가"로 오탐지된다. `include_schemas=True`를 켜도,
    FK 문자열에서 "dbo." 접두사를 빼도 재현됐다(둘 다 실제로 시도해서 확인함) —
    즉 스타터킷 코드로 고칠 수 있는 문제가 아니다. 테이블 자체 비교는 정상 동작하므로
    영향은 FK 존재 여부를 alembic이 자동으로 못 잡는다는 것뿐이고, `alembic check`가
    깨끗하려면 이 필터가 필요하다.

    공유 MSSQL 인스턴스에 다른 프로젝트 테이블도 있어서 autogenerate가 그것까지
    DROP 후보로 잡는 상황이 되면, 아래 주석을 풀어 테이블 비교도 이 프로젝트
    메타데이터에 있는 것만으로 좁혀라:

        if type_ == "table":
            return name in {t.name for t in target_metadata.tables.values()}
    """
    return type_ != "foreign_key_constraint"


def _configure_opts() -> dict[str, Any]:
    return {
        "target_metadata": target_metadata,
        # 공유 MSSQL 인스턴스에 여러 프로젝트가 붙는 현실 때문에 프로젝트마다
        # 반드시 바꿔야 한다 (안 바꾸면 두 프로젝트가 같은 버전 테이블을 보고
        # 서로의 리비전을 덮어쓴다). scripts/rename_project.py가 자동 갱신한다.
        "version_table": settings.ALEMBIC_VERSION_TABLE,
        # 모델 타입 규약(app/db/models/base.py의 Unicode/UnicodeText/DATETIME2_3)을
        # 지키는 한 String vs nvarchar 같은 가짜 드리프트가 나지 않으므로 True로 켜서
        # 진짜 드리프트를 잡는 안전망으로 쓴다. 서드파티 도구가 만든 테이블이 섞여
        # 시끄러워지면 그때 False로 낮춰라.
        "compare_type": True,
        "include_object": _include_object,
    }


def run_migrations_offline() -> None:
    """오프라인 모드 — DB 연결 없이 SQL 스크립트만 출력."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_configure_opts(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """온라인 모드 — 동기 pyodbc 엔진으로 실제 DB에 적용."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, **_configure_opts())
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
