"""app/core/context.py

요청 스코프 컨텍스트 변수. middleware.py가 요청마다 설정하고,
logging.py가 로그 라인마다 읽어 prefix를 붙인다.
"""

from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
client_ip_var: ContextVar[str] = ContextVar("client_ip", default="-")
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


def get_request_id() -> str:
    return request_id_var.get()


def get_client_ip() -> str:
    return client_ip_var.get()


def get_user_id() -> str | None:
    return user_id_var.get()
