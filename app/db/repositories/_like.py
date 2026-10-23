"""app/db/repositories/_like.py

LIKE 검색어 이스케이프 — 검색 기능이 있는 리포지토리가 공유한다.
이 함수가 리포지토리마다 복사되어 있으면 한쪽만 고쳐지는 일이 생긴다.
"""


def escape_like(value: str) -> str:
    """LIKE 와일드카드를 리터럴 문자로 만든다.

    검색창에 `%`를 치면 "모든 행"이 아니라 "%가 들어간 행"이 나와야 한다.
    MSSQL은 `%` `_` 외에 `[`도 와일드카드(문자 클래스)로 해석하므로 같이 막는다.
    역슬래시를 가장 먼저 치환해야 뒤에 붙인 이스케이프까지 다시 치환되지 않는다.

    쿼리에서는 반드시 `escape="\\\\"`와 함께 써야 한다 (ilike(pattern, escape="\\\\")).
    """
    for ch in ("\\", "%", "_", "["):
        value = value.replace(ch, f"\\{ch}")
    return value
