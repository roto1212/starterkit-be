"""app/core/exceptions.py

Service 계층에서 이 예외들을 던지면 exception_handlers.py가 HTTP 응답으로
변환한다. Endpoint에서 HTTPException을 직접 만들지 않는다.
"""


class AppError(Exception):
    """비즈니스 로직 에러 (전역 핸들러에서 자동 처리)"""

    def __init__(self, detail: str, code: str = "BAD_REQUEST", status_code: int = 400) -> None:
        self.detail = detail
        self.code = code
        self.status_code = status_code
        super().__init__(detail)


class NotFoundError(AppError):
    """리소스 없음"""

    def __init__(self, detail: str = "요청한 리소스를 찾을 수 없습니다.") -> None:
        super().__init__(detail=detail, code="NOT_FOUND", status_code=404)


class ConflictError(AppError):
    """중복/충돌"""

    def __init__(self, detail: str = "이미 존재하는 리소스입니다.") -> None:
        super().__init__(detail=detail, code="CONFLICT", status_code=409)


class ForbiddenError(AppError):
    """권한 없음"""

    def __init__(self, detail: str = "접근 권한이 없습니다.") -> None:
        super().__init__(detail=detail, code="FORBIDDEN", status_code=403)


class IntegrityError(AppError):
    """DB 무결성 (FK 위반 등)"""

    def __init__(self, detail: str = "데이터 무결성 오류입니다.") -> None:
        super().__init__(detail=detail, code="INTEGRITY_ERROR", status_code=400)


class AuthError(AppError):
    """인증 실패.

    로그인 관련 실패(아이디 없음/비번 틀림/계정 잠김)는 전부 이 예외를
    동일한 메시지로 던진다 — 사유별로 다른 메시지를 주면 계정 존재 여부가
    노출된다(계정 열거 공격).
    """

    def __init__(self, detail: str = "인증에 실패했습니다.") -> None:
        super().__init__(detail=detail, code="UNAUTHORIZED", status_code=401)
