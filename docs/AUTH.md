# 인증 설계 근거

`app/core/security.py`, `app/services/auth_service.py` 등 신원 저장소
슬라이스(파일 상단 ★ 표시)의 설계 결정과 그 이유를 정리한다. 이 슬라이스를
통째로 지워도 되는 프로젝트라면 [`BOOTSTRAP.md`](BOOTSTRAP.md)의 6단계를 본다.

## 비밀번호 해싱: argon2-cffi

`passlib`이 아니라 `argon2-cffi`를 직접 쓴다.

- **passlib 배제**: 마지막 릴리스가 2020년(1.7.4) 이후 유지보수가 사실상
  중단됐다. `crypt` 모듈 의존이 최신 Python에서 깨지는 문제가 이미 보고되어
  있다. 우선순위가 "보안 > 안정성"인데, 유지보수 안 되는 인증 라이브러리는
  두 항목 모두에서 탈락이다.
- **Argon2id 선택**: PHC(Password Hashing Competition) 우승 알고리즘이고
  메모리 하드라 GPU/ASIC 공격 비용이 bcrypt 대비 훨씬 높다. bcrypt는 72바이트
  입력이 잘리는 함정도 있다.
- `needs_rehash()`를 로그인 성공 경로에 넣어둔 이유: 해싱 파라미터
  (`time_cost`/`memory_cost`)를 나중에 올릴 수 있는 유일한 지점이 "사용자가
  평문 비밀번호를 아는 순간"(=로그인 성공 시)이기 때문이다. 나중에 넣으려면
  전체 비밀번호 재설정을 강제해야 한다.

## 토큰: access(JWT) + refresh(불투명 랜덤, DB 저장)

| | access | refresh |
|---|---|---|
| 형식 | JWT (HS256) | 불투명 랜덤 문자열 (`secrets.token_urlsafe(48)`) |
| 수명 | 30분 (`ACCESS_TOKEN_EXPIRE_MINUTES`) | 14일 (`REFRESH_TOKEN_EXPIRE_DAYS`) |
| 저장 | 서버 무상태 | `auth_refresh_token` 테이블에 **SHA-256 해시로만** |
| 전달 | 응답 JSON 본문 | HttpOnly + Secure + SameSite=Lax 쿠키 |
| 폐기 | 불가 (수명이 짧아 감수) | 즉시 가능 (`/logout`) |

**refresh를 JWT로 하지 않은 이유**: 로그아웃이 실제로 로그아웃이어야 한다.
무상태 refresh JWT는 서버가 취소할 방법이 없어서, 결국 블랙리스트 테이블을
만들게 된다. 그럴 거면 처음부터 불투명 토큰 + DB 조회가 더 단순하고 안전하다.
DB에는 평문이 아니라 SHA-256 해시만 저장해, DB가 유출돼도 저장된 값만으로는
토큰을 재사용할 수 없게 한다.

**회전(rotation)**: `/refresh`를 호출할 때마다 기존 토큰을 폐기(`revoked_at`)하고
새 토큰을 발급한다.

**access 토큰 클레임 검증**: `typ`(access인지), `iss`, `aud`,
`algorithms=["HS256"]`(화이트리스트 고정)을 전부 검증한다. 알고리즘을
화이트리스트로 고정하는 이유는 `alg: none`이나 RS256→HS256 같은 알고리즘
혼동 공격을 막기 위함이다.

## 로그인 실패는 전부 같은 메시지

아이디 없음 / 비밀번호 틀림 / 계정 잠김을 **전부 동일한 응답**
(`"이메일 또는 비밀번호가 올바르지 않습니다."`, 401)으로 처리한다. 사유별로
다른 메시지를 주면 공격자가 순차 대입으로 어느 이메일이 가입되어 있는지
알아낼 수 있다(계정 열거 공격).

## 브루트포스 방어: DB 컬럼 (Redis 아님)

`app_user.failed_login_count` / `locked_until` 컬럼으로 구현했다.

이 킷이 참고한 레퍼런스 프로젝트는 Redis로 구현했는데, 그 이유는 "Swarm에서
replica가 여러 개 떠도 실패 카운트가 공유돼야 한다"였다. 이 킷도 그 요구는
그대로 유효하지만, **DB도 이미 공유 상태**라 같은 요구를 인프라 추가 없이
만족한다. 스타터킷 스코프를 "코어 + 운영 필수"로 잡았으므로, 꼭 필요하지 않은
한 새 인프라(Redis)를 기본으로 얹지 않는다.

IP 단위 rate limit(레퍼런스에 있던 기능)은 이 킷에 없다 — nginx/WAF 영역의
책임으로 본다.

## 이 슬라이스가 일부러 안 하는 것 (업그레이드 경로)

다음은 스코프를 억제하려는 의도적 판단이며, 필요해지면 여기서부터 확장한다:

- **refresh 토큰 재사용 탐지(family 체인 무효화)**: 이미 폐기된 refresh
  토큰이 다시 들어오면 탈취로 간주해 그 사용자의 모든 refresh 토큰을
  무효화하는 패턴. 지금은 폐기된 토큰이 다시 오면 그냥 401만 반환한다.
  필요해지면 `RefreshToken`에 `family_id`를 추가하고, 재사용 감지 시
  `RefreshTokenRepository.revoke_all_for_user()`를 호출하도록
  `AuthService.refresh()`를 확장한다.
- **IP 단위 rate limit**: 위 참조. 필요해지면 Redis를 얹거나 nginx
  `limit_req`로 처리한다.
- **역할(role) 정규화 테이블**: 지금은 `app_user.roles`가 콤마 구분
  문자열이다. 역할 종류가 늘어나고 역할별 세부 권한 관리가 필요해지면
  별도 `role`/`user_role` 테이블로 정규화한다.
