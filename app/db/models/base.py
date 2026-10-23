"""app/db/models/base.py

스키마는 여기 한 곳(Base.metadata)에서만 선언한다. 테이블마다 __table_args__ =
{"schema": "dbo"}를 반복하면, 나중에 스키마를 바꿀 때 일부 테이블만 빠뜨리기 쉽고
그 어긋남이 Alembic autogenerate에서 가짜 FK 드리프트로 나타난다.

문자열/시간 컬럼은 반드시 아래 별칭만 쓴다 (String/Text/DateTime 직접 사용 금지).
모델과 DB의 타입이 항상 일치해야 alembic/env.py의 compare_type=True가
진짜 안전망으로 동작한다 (거짓 드리프트를 감추려고 끄지 않아도 된다).
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import DeclarativeBase

DB_SCHEMA = "dbo"

# NVARCHAR(n) — 가변 길이 유니코드 문자열. String() 대신 이것만 쓴다.
Unicode = sa.Unicode
# NVARCHAR(MAX) — 긴 텍스트. Text() 대신 이것만 쓴다.
UnicodeText = sa.UnicodeText
# DATETIME2(3) — MSSQL 표준 타임스탬프. DateTime() 대신 이것만 쓴다.
DATETIME2_3 = sa.DateTime().with_variant(mssql.DATETIME2(3), "mssql")


def utcnow_naive() -> datetime:
    """DATETIME2_3 컬럼에 넣을 UTC 현재시각.

    MSSQL DATETIME2는 타임존 정보가 없다(naive) — DB에서 읽어온 값도 naive로
    돌아온다. `datetime.utcnow()`는 deprecated(Python 3.12+)라서 그냥 못 쓰고,
    그렇다고 `datetime.now(UTC)`를 그대로 쓰면 aware/naive 비교에서
    `TypeError`가 난다. UTC로 구한 뒤 tzinfo만 벗겨서 DB 쪽과 형태를 맞춘다.
    """
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    """모든 모델의 베이스 클래스. 스키마는 metadata에서 전역 지정."""

    metadata = sa.MetaData(schema=DB_SCHEMA)
