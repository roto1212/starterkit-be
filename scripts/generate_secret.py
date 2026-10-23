"""scripts/generate_secret.py

JWT_SECRET_KEY 등에 쓸 암호학적으로 안전한 랜덤 문자열을 생성한다.

사용:
    uv run python scripts/generate_secret.py
"""

import secrets


def main() -> None:
    print(secrets.token_urlsafe(48))


if __name__ == "__main__":
    main()
