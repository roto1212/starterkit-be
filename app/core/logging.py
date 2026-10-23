"""app/core/logging.py

loguru 기반 로깅 설정. stdlib logging(uvicorn 등)을 가로채 loguru로 통일하고,
LOG_FORMAT 설정에 따라 로컬용(rich, 사람이 읽기 좋음) 또는 운영용(json, 로그
수집기가 파싱하기 좋음) sink를 붙인다.
"""

import json
import logging
import sys
import traceback
from types import FrameType, TracebackType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Record

from loguru import logger
from rich.console import Console
from rich.logging import RichHandler

from app.config import settings
from app.core.context import get_client_ip, get_request_id, get_user_id

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
_NOISE_PACKAGES = {
    "starlette",
    "anyio",
    "fastapi",
    "uvicorn",
    "asyncio",
    "watchfiles",
    "httptools",
    "websockets",
}

# 여기 올라간 로거는 NullHandler + propagate=False 로 완전히 죽는다.
#
# uvicorn.error 는 넣지 않는다: 이름과 달리 이 로거는 에러 전용이 아니라
# uvicorn의 기동/종료 라이프사이클 채널이고, 기동 실패 시 다음이 여기로 나간다:
#   - starlette가 lifespan에서 잡은 예외의 트레이스백 전문
#   - "Application startup failed. Exiting."
# 이걸 죽여두면 DB 점검처럼 기동 자체가 실패했을 때 원인이 로그에 한 줄도
# 안 남는다. 대신 소음이던 개별 메시지는 아래 InterceptHandler의 메시지
# 필터에서 걸러낸다.
_SUPPRESSED_LOGGERS = {
    "uvicorn.access",
    "watchfiles.main",
}

_INTERCEPT_LOGGERS = {
    "",
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "fastapi",
}

_initialized = False
_json_mode = False


def is_json_mode() -> bool:
    return _json_mode


# ──────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────
def _is_noise_frame(filename: str) -> bool:
    return any(pkg in filename for pkg in _NOISE_PACKAGES)


def _extract_root_cause(exc: BaseException) -> BaseException:
    visited: set[int] = set()
    current = exc
    while True:
        exc_id = id(current)
        if exc_id in visited:
            return current
        visited.add(exc_id)
        if isinstance(current, BaseExceptionGroup) and current.exceptions:
            current = current.exceptions[0]
            continue
        if current.__cause__ is not None:
            current = current.__cause__
            continue
        if current.__context__ is not None and not current.__suppress_context__:
            current = current.__context__
            continue
        return current


def _filter_traceback(tb: TracebackType | None) -> list[traceback.FrameSummary]:
    frames = traceback.extract_tb(tb)
    app_frames = [f for f in frames if not _is_noise_frame(f.filename)]
    return app_frames if app_frames else frames


def format_exception_cleanly(exc: BaseException) -> str:
    try:
        root = _extract_root_cause(exc)
        app_frames = _filter_traceback(root.__traceback__)
        lines = ["Traceback (app frames only):\n"]
        lines += traceback.format_list(app_frames)
        lines += traceback.format_exception_only(type(root), root)
        return "".join(lines)
    except Exception as e:
        return f"[traceback 포맷 실패: {e}]\n{traceback.format_exc()}"


# ──────────────────────────────────────────────
# Rich 모드: message 자체에 prefix 삽입
# ──────────────────────────────────────────────
def _inject_context_to_message(record: "Record") -> None:
    """loguru patcher. logger.xxx() 호출 시점에 실행되어
    record["message"] 앞에 context prefix를 삽입한다."""
    rid = get_request_id()
    ip = get_client_ip()
    uid = get_user_id()

    if rid == "-" and ip == "-":
        return  # startup 등은 prefix 없음

    parts = [rid, ip]
    if uid:
        parts.append(uid)

    prefix = " | ".join(parts)
    record["message"] = f"[{prefix}] {record['message']}"


# ──────────────────────────────────────────────
# JSON sink (운영용 — 로그 수집기가 필드 단위로 파싱)
# ──────────────────────────────────────────────
def _json_sink(message: object) -> None:
    record = message.record  # type: ignore[attr-defined]

    log_entry: dict[str, object] = {
        "timestamp": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "level": record["level"].name,
        "message": record["message"],
        "logger": record["name"] or "app",
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
        "request_id": get_request_id(),
        "client_ip": get_client_ip(),
    }

    uid = get_user_id()
    if uid:
        log_entry["user_id"] = uid

    for k, v in record["extra"].items():
        if k not in log_entry:
            log_entry[f"extra_{k}"] = _to_str(v)

    if record["exception"] and record["exception"].value:
        exc = record["exception"].value
        log_entry["exc_type"] = type(exc).__name__
        log_entry["exc_message"] = str(exc)
        log_entry["exc_traceback"] = format_exception_cleanly(exc)

    sys.stdout.write(json.dumps(log_entry, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


def _to_str(v: object) -> object:
    if isinstance(v, str | int | float | bool):
        return v
    return str(v)


# ──────────────────────────────────────────────
# Intercept Handler — stdlib logging → loguru
# ──────────────────────────────────────────────
class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if record.name in _SUPPRESSED_LOGGERS:
            return

        msg = record.getMessage()
        # 소음만 골라 버린다 — "Application startup failed"는 절대 여기 넣지 말 것.
        # "Exception in ASGI application"은 exception_handlers가 이미 같은 예외를
        # 더 읽기 좋게 남기므로 중복이라 버린다.
        if any(
            kw in msg
            for kw in (
                "Exception in ASGI application",
                "Application startup complete",
            )
        ):
            return

        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame: FrameType | None = sys._getframe(1)  # f_back이 None일 수 있음
        depth = 1
        while frame and (
            "logging" in frame.f_code.co_filename or "loguru" in frame.f_code.co_filename
        ):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, msg)


# ──────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────
def setup_logging(level: str = "DEBUG") -> None:
    # _json_mode도 global로 선언해야 한다. 빠뜨리면 아래 대입이 지역 변수만
    # 만들어 모듈 전역은 계속 False로 남고, is_json_mode()가 운영(json)
    # 환경에서도 False를 돌려준다 — exception_handlers가 traceback을 별도
    # 필드가 아니라 message 안에 줄바꿈째로 밀어넣게 되어 로그 수집기에서
    # 읽기 어려워진다.
    global _initialized, _json_mode
    if _initialized:
        logger.debug("setup_logging() already called, skipping.")
        return
    _initialized = True

    # ① loguru 기존 sink 전부 제거
    logger.remove()

    # ② stdlib root logger 정리
    root = logging.root
    root.handlers.clear()
    root.setLevel(logging.DEBUG)

    # ③ intercept 대상 로거 설정
    intercept_handler = InterceptHandler()
    for logger_name in _INTERCEPT_LOGGERS:
        stdlib_logger = logging.getLogger(logger_name)
        stdlib_logger.handlers.clear()
        stdlib_logger.addHandler(intercept_handler)
        stdlib_logger.setLevel(logging.DEBUG)
        if logger_name:
            stdlib_logger.propagate = False

    # ④ 완전 무시 로거
    for name in _SUPPRESSED_LOGGERS:
        suppressed = logging.getLogger(name)
        suppressed.handlers.clear()
        suppressed.addHandler(logging.NullHandler())
        suppressed.propagate = False

    # ⑤-α httpx는 INFO 레벨로 요청 전체 URL(로그인 시 비밀번호 쿼리 포함 가능)을
    # 남기므로 억제
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # ⑤ 환경별 sink 선택
    log_format = getattr(settings, "LOG_FORMAT", "rich").lower()
    _json_mode = log_format == "json"

    if _json_mode:
        # ── JSON: patcher 불필요 (_json_sink에서 직접 context 읽음) ──
        logger.add(
            _json_sink,
            level=level,
            format="{message}",
            backtrace=False,
            diagnose=False,
        )
        logger.info("Logging initialized (JSON mode)")
    else:
        # ── Rich: patcher로 message에 prefix 삽입 ──
        logger.configure(patcher=_inject_context_to_message)

        console = Console(stderr=True)
        rich_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            tracebacks_suppress=["starlette", "anyio", "fastapi", "uvicorn", "asyncio"],
            markup=True,
            show_time=True,
            show_level=True,
            show_path=True,
            log_time_format="[%H:%M:%S]",
        )
        logger.add(
            rich_handler,
            level=level,
            format="{message}",
            backtrace=False,
            diagnose=False,
        )
        logger.info("Logging initialized (Rich mode)")
