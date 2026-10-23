"""app/core/exception_handlers.py

전역 예외 → HTTP 응답 변환. 응답 봉투(success/code/detail/request_id)는
FE 킷이 이 형태를 전제로 파싱하므로 임의로 바꾸지 않는다.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.context import get_request_id
from app.core.exceptions import AppError
from app.core.logging import format_exception_cleanly, is_json_mode


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """비즈니스 로직 에러 → 적절한 status_code로 반환"""
    request_id = get_request_id()

    log_fn = logger.error if exc.status_code >= 500 else logger.warning
    log_fn(
        "[{status}] {path} | {code}: {detail}",
        status=exc.status_code,
        path=request.url.path,
        code=exc.code,
        detail=exc.detail,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "code": exc.code,
            "detail": exc.detail,
            "request_id": request_id,
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = get_request_id()
    logger.warning(
        "[{status}] {path} | {detail}",
        status=exc.status_code,
        path=request.url.path,
        detail=exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "code": f"HTTP_{exc.status_code}",
            "detail": exc.detail,
            "request_id": request_id,
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = get_request_id()
    errors = [
        {"field": " → ".join(str(loc) for loc in err["loc"]), "message": err["msg"]}
        for err in exc.errors()
    ]
    logger.warning(
        "[422] {path} | validation errors: {errors}", path=request.url.path, errors=errors
    )
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "code": "VALIDATION_ERROR",
            "detail": "입력값이 올바르지 않습니다.",
            "request_id": request_id,
            "errors": errors,
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = get_request_id()
    clean_trace = format_exception_cleanly(exc)

    if is_json_mode():
        logger.error(
            "UNHANDLED {method} {path} | {error_type}: {error_msg}",
            method=request.method,
            path=request.url.path,
            error_type=type(exc).__name__,
            error_msg=str(exc),
            traceback=clean_trace,
        )
    else:
        logger.error(
            "UNHANDLED {method} {path} | {error_type}: {error_msg}\n{trace}",
            method=request.method,
            path=request.url.path,
            error_type=type(exc).__name__,
            error_msg=str(exc),
            trace=clean_trace,
        )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "code": "INTERNAL_SERVER_ERROR",
            "detail": "서버 오류입니다. 잠시 후 다시 시도해 주세요.",
            "request_id": request_id,
        },
    )


def add_exception_handlers(app: FastAPI) -> None:
    # starlette 스텁은 핸들러 시그니처를 Exception으로만 받지만,
    # 런타임은 등록한 예외 타입만 각 핸들러로 라우팅하므로 구체 타입이 안전하다
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
