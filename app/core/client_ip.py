"""실제 클라이언트 IP 취득 유틸.

트래픽 경로(표준): 브라우저 → nginx(Swarm) → FastAPI.
nginx가 X-Real-IP / X-Forwarded-For를 신뢰할 수 있게 설정했다는 전제
(proxy_set_header 로 실제 클라이언트 IP를 넣어준다는 뜻 — nginx 설정 확인 항목).

CloudFront 등 CDN을 앞단에 두는 경우 그 CDN이 넣어주는 헤더를 최우선으로
추가해야 한다(예: CloudFront-Viewer-Address). 이 스타터킷은 표준 배포
경로(Swarm + nginx)만 전제하므로 CDN 헤더는 포함하지 않는다.
"""

from fastapi import Request


def get_client_ip(request: Request) -> str:
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "-"
