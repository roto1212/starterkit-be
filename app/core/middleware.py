"""app/core/middleware.py

요청/응답 로깅 + 민감 필드 마스킹 + 업로드 크기 제한.

민감 필드 마스킹은 실전에서 값을 치른 부분이다: 이게 없으면 로그인 요청
바디의 비밀번호가 DEBUG 로그에 평문으로 남는다.
"""

import re
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.client_ip import get_client_ip
from app.core.context import client_ip_var, request_id_var

# ── 민감 필드 마스킹 ──────────────────────────
_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "pw",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "apikey",
    "authorization",
    "credit_card",
    "card_number",
    "ssn",
    "social_security",
}

_SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "x-api-key",
}

_QUIET_PATHS = ("/health",)  # 튜플 — 콤마를 빼면 문자열이 되어 부분 일치로 동작한다

# body 로깅 최대 크기 (bytes)
_MAX_BODY_LOG_SIZE = 2048


def _mask_value(key: str, value: object) -> str:
    """민감 필드 마스킹 (부분 노출 없이 전체 마스킹)"""
    if key.lower() in _SENSITIVE_KEYS:
        return "****"
    return str(value)


def _mask_dict(data: Mapping[str, object]) -> dict[str, object]:
    """dict 내 민감 필드 마스킹 (1 depth). Mapping을 받는 이유: dict는 값 타입에
    invariant라 dict[str, str]를 dict[str, object] 자리에 못 넣는다."""
    return {k: _mask_value(k, v) for k, v in data.items()}


_SENSITIVE_ALT = "|".join(re.escape(k) for k in _SENSITIVE_KEYS)
# urlencoded: password=xxx&...  /  JSON: "password": "xxx"
_FORM_SENSITIVE_RE = re.compile(rf"(?i)\b({_SENSITIVE_ALT})=([^&]*)")
_JSON_SENSITIVE_RE = re.compile(rf'(?i)"({_SENSITIVE_ALT})"\s*:\s*"((?:[^"\\]|\\.)*)"')


def _mask_body_text(text: str) -> str:
    """body 미리보기 텍스트 내 민감 필드 값 마스킹"""
    text = _FORM_SENSITIVE_RE.sub(r"\1=****", text)
    text = _JSON_SENSITIVE_RE.sub(r'"\1": "****"', text)
    return text


async def _safe_read_body(request: Request) -> str:
    """안전하게 body 미리보기.
    - multipart/binary → 메타 정보만
    - stream 소비 문제 → Starlette의 body() 캐싱으로 해결
    - 메모리 폭발 → Content-Length 사전 체크
    """
    try:
        content_type = request.headers.get("content-type", "")

        if "multipart/form-data" in content_type:
            content_length_hint = request.headers.get("content-length", "?")
            return f"[multipart/form-data | {content_length_hint} bytes]"

        if any(t in content_type for t in ("image/", "audio/", "video/", "octet-stream")):
            size = request.headers.get("content-length", "?")
            return f"[binary {size} bytes]"

        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_BODY_LOG_SIZE:
            return f"[body too large: {int(content_length)} bytes]"

        if not content_length:
            return "[chunked/unknown length - skipped]"

        # Note: Starlette의 Request.body()는 내부적으로 캐싱하므로
        # endpoint에서 다시 읽을 수 있음 (stream은 아님)
        body = await request.body()

        if not body:
            return "(empty)"

        text = _mask_body_text(body[:_MAX_BODY_LOG_SIZE].decode("utf-8", errors="replace"))

        if len(body) > _MAX_BODY_LOG_SIZE:
            return text + f"... (truncated, total {len(body)} bytes)"

        return text

    except Exception:
        return "[body 읽기 실패]"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """요청 추적 + 상세 디버그 로깅"""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:16])
        client_ip = get_client_ip(request)

        rid_token = request_id_var.set(request_id)
        ip_token = client_ip_var.set(client_ip)

        request.state.request_id = request_id
        request.state.client_ip = client_ip

        start = time.monotonic()
        quiet = request.url.path in _QUIET_PATHS

        try:
            if not quiet:
                logger.info("→ {method} {path}", method=request.method, path=request.url.path)

            # loguru 비공개 API지만 "현재 설정된 최소 레벨" 공개 대체재가 없음
            if logger._core.min_level <= 10:  # type: ignore[attr-defined]  # DEBUG 이하일 때만
                await _log_request_detail(request)

            response = await call_next(request)

            elapsed_ms = (time.monotonic() - start) * 1000
            status = response.status_code
            log_fn = (
                logger.error if status >= 500 else logger.warning if status >= 400 else logger.info
            )
            if not quiet:
                log_fn(
                    "← {method} {path} | {status} | {elapsed:.1f}ms",
                    method=request.method,
                    path=request.url.path,
                    status=status,
                    elapsed=elapsed_ms,
                )

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"
            return response

        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            logger.error(
                "✗ {method} {path} | {elapsed:.1f}ms | {exc_type}: {exc_msg}",
                method=request.method,
                path=request.url.path,
                elapsed=elapsed_ms,
                exc_type=type(exc).__name__,
                exc_msg=str(exc),
            )
            raise

        finally:
            request_id_var.reset(rid_token)
            client_ip_var.reset(ip_token)


async def _log_request_detail(request: Request) -> None:
    """DEBUG 레벨 상세 요청 정보"""
    query_params = dict(request.query_params)
    if query_params:
        logger.debug("  query: {params}", params=_mask_dict(query_params))

    headers_to_log: dict[str, str] = {}
    for key in ("content-type", "accept", "user-agent", "authorization", "x-api-key"):
        value = request.headers.get(key)
        if value:
            if key in _SENSITIVE_HEADERS:
                # Bearer 토큰은 앞부분만
                if value.lower().startswith("bearer ") and len(value) > 15:
                    headers_to_log[key] = value[:15] + "****"
                else:
                    headers_to_log[key] = "****"
            else:
                headers_to_log[key] = value

    if headers_to_log:
        logger.debug("  headers: {headers}", headers=headers_to_log)

    if request.method in ("POST", "PUT", "PATCH"):
        body_str = await _safe_read_body(request)
        if body_str and body_str != "(empty)":
            logger.debug("  body: {body}", body=body_str)


class FileSizeMiddleware(BaseHTTPMiddleware):
    """Content-Length 기반 업로드 크기 제한 + chunked 방어"""

    def __init__(self, app: object, max_size: int = 10 * 1024 * 1024) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.max_size = max_size

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                size = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "code": "INVALID_HEADER",
                        "detail": "잘못된 Content-Length 헤더입니다.",
                    },
                )
            if size > self.max_size:
                max_mb = self.max_size / (1024 * 1024)
                cur_mb = size / (1024 * 1024)
                return JSONResponse(
                    status_code=413,
                    content={
                        "success": False,
                        "code": "FILE_TOO_LARGE",
                        "detail": (
                            f"파일 크기가 {max_mb:.1f}MB를 초과합니다. (현재: {cur_mb:.1f}MB)"
                        ),
                    },
                )

        transfer_encoding = request.headers.get("transfer-encoding", "")
        if "chunked" in transfer_encoding and not content_length:
            logger.debug("Chunked transfer without Content-Length: {path}", path=request.url.path)

        return await call_next(request)
