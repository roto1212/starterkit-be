"""tests/unit/test_config_validation.py

시크릿 fail-fast 장치들을 회귀 테스트한다. Settings는 프로세스 시작 시
한 번만 로드되는 모듈 레벨 싱글턴이라(app/config.py), 여기서는 별도
프로세스로 띄워 부팅 실패 여부만 확인한다 — 현재 프로세스의 app.config.settings를
건드리면 다른 테스트에 영향을 준다.
"""

import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

_BASE_ENV = {
    "DB_HOST": "localhost",
    "DB_PORT": "1433",
    "DB_NAME": "irrelevant",
    "DB_USER": "sa",
    "DB_PASSWORD": "irrelevant",
    "JWT_SECRET_KEY": "a" * 32,
}


def _boot_with_env(
    overrides: dict[str, str], removals: set[str] = frozenset()
) -> subprocess.CompletedProcess:
    import os

    env = {
        k: v
        for k, v in os.environ.items()
        if k
        not in {
            "DB_HOST",
            "DB_PORT",
            "DB_NAME",
            "DB_USER",
            "DB_PASSWORD",
            "JWT_SECRET_KEY",
            "ENV",
            "CORS_ORIGINS",
            "COOKIE_SECURE",
        }
    }
    env["ENV_FILE"] = "/nonexistent/.env"  # .env 파일에 기대지 않고 순수 환경변수로만 테스트
    env.update(_BASE_ENV)
    env.update(overrides)
    for key in removals:
        env.pop(key, None)
    return subprocess.run(
        [sys.executable, "-c", "from app.config import settings"],
        cwd=_PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_missing_required_field_fails_fast() -> None:
    result = _boot_with_env({}, removals={"DB_HOST"})
    assert result.returncode != 0
    assert "DB_HOST" in result.stderr


def test_placeholder_jwt_secret_rejected() -> None:
    result = _boot_with_env(
        {"JWT_SECRET_KEY": "CHANGE_ME_run_scripts_generate_secret_to_create_a_real_key"}
    )
    assert result.returncode != 0
    assert "플레이스홀더" in result.stderr


def test_short_jwt_secret_rejected() -> None:
    result = _boot_with_env({"JWT_SECRET_KEY": "short"})
    assert result.returncode != 0
    assert "32자" in result.stderr


def test_prod_rejects_wildcard_cors() -> None:
    result = _boot_with_env({"ENV": "prod", "CORS_ORIGINS": "*", "COOKIE_SECURE": "true"})
    assert result.returncode != 0
    assert "CORS_ORIGINS" in result.stderr


def test_prod_rejects_insecure_cookie() -> None:
    result = _boot_with_env(
        {"ENV": "prod", "CORS_ORIGINS": "https://example.com", "COOKIE_SECURE": "false"}
    )
    assert result.returncode != 0
    assert "COOKIE_SECURE" in result.stderr


def test_valid_config_boots_successfully() -> None:
    result = _boot_with_env(
        {"ENV": "prod", "CORS_ORIGINS": "https://example.com", "COOKIE_SECURE": "true"}
    )
    assert result.returncode == 0, result.stderr
