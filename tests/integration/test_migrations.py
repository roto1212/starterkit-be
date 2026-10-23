"""tests/integration/test_migrations.py

_migrated fixture가 이미 `alembic upgrade head`를 실제로 실행하므로, 이 파일이
실패한다는 것 자체가 "마이그레이션이 깨끗한 DB에 처음부터 끝까지 적용된다"는
걸 검증한다. 여기서는 추가로 모델과 DB 사이에 드리프트가 없는지까지 확인한다.
"""


async def test_migrations_apply_and_no_drift(_migrated: None) -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    command.check(cfg)  # 드리프트가 있으면 예외를 던진다
