"""tests/unit/test_like_escape.py"""

from app.db.repositories._like import escape_like


def test_percent_escaped() -> None:
    assert escape_like("50%") == "50\\%"


def test_underscore_escaped() -> None:
    assert escape_like("a_b") == "a\\_b"


def test_bracket_escaped() -> None:
    """MSSQL은 [ 도 문자 클래스 와일드카드로 해석한다."""
    assert escape_like("[test]") == "\\[test]"


def test_backslash_escaped_first() -> None:
    """역슬래시를 가장 먼저 치환해야, 뒤에 붙인 이스케이프 문자가 다시 치환되지 않는다."""
    assert escape_like("50%\\") == "50\\%\\\\"


def test_plain_text_unchanged() -> None:
    assert escape_like("공지사항") == "공지사항"
