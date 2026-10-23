"""scripts/rename_project.py

템플릿을 새 프로젝트로 바꿀 때 흩어진 이름표를 한 번에 치환한다.

가장 중요한 건 ALEMBIC_VERSION_TABLE이다 — 운영 환경은 공유 MSSQL
인스턴스라, 이걸 안 바꾸면 두 프로젝트가 같은 버전 테이블을 보고 서로의
Alembic 리비전을 덮어쓴다. 다른 항목(컨테이너 이름 등)은 틀려도 바로
눈에 보이지만, 이건 나중에 조용히 터진다 — 그래서 스크립트로 강제한다.

기본은 dry-run이다. 실제로 파일을 바꾸려면 --apply를 붙인다.

사용:
    uv run python scripts/rename_project.py --name my-service          # dry-run (미리보기만)
    uv run python scripts/rename_project.py --name my-service --apply  # 실제 적용
"""

import argparse
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_OLD_KEBAB = "starterkit-be"
_OLD_SNAKE = "starterkit_be"

# (파일, 바꿀 내용 설명) — 정규식이 아니라 단순 치환이라 오탐 위험이 낮다.
_TARGET_FILES = [
    _ROOT / "pyproject.toml",
    _ROOT / "app" / "main.py",
    _ROOT / "docker-compose.yml",
    _ROOT / "docker-stack.yaml",
    _ROOT / ".env.example",
    _ROOT / "README.md",
    _ROOT / ".claude" / "CLAUDE.md",
]


def _validate_name(name: str) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9-]*[a-z0-9]", name):
        print(
            f"'{name}'은(는) 유효한 프로젝트명이 아닙니다. "
            "소문자/숫자/하이픈만 쓰고 하이픈으로 시작·끝나지 않아야 합니다 (예: my-service).",
            file=sys.stderr,
        )
        sys.exit(1)


def _apply_to_text(text: str, new_kebab: str, new_snake: str) -> tuple[str, int]:
    new_text, n1 = re.subn(re.escape(_OLD_KEBAB), new_kebab, text)
    new_text, n2 = re.subn(re.escape(_OLD_SNAKE), new_snake, new_text)
    return new_text, n1 + n2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="새 프로젝트명 (kebab-case, 예: my-service)")
    parser.add_argument(
        "--apply", action="store_true", help="실제로 파일을 수정한다 (기본은 dry-run)"
    )
    args = parser.parse_args()

    _validate_name(args.name)
    new_kebab = args.name
    new_snake = args.name.replace("-", "_")

    total_changes = 0
    for path in _TARGET_FILES:
        if not path.exists():
            continue
        original = path.read_text(encoding="utf-8")
        updated, count = _apply_to_text(original, new_kebab, new_snake)
        if count == 0:
            continue
        total_changes += count
        rel = path.relative_to(_ROOT)
        if args.apply:
            path.write_text(updated, encoding="utf-8")
            print(f"[적용] {rel}: {count}곳 변경")
        else:
            print(f"[미리보기] {rel}: {count}곳 변경 예정")

    if total_changes == 0:
        print("변경할 곳을 찾지 못했습니다 — 이미 이름이 바뀌어 있는지 확인하세요.")
        return

    if not args.apply:
        print(f"\n총 {total_changes}곳. 실제 적용하려면 --apply를 붙여 다시 실행하세요.")
    else:
        print(f"\n총 {total_changes}곳 변경 완료.")
        print(
            "다음 단계: .env.example의 ALEMBIC_VERSION_TABLE 값이 바뀌었는지 확인하고, "
            ".env도 같은 값으로 맞추세요 (이미 .env가 있었다면 자동으로 안 바뀝니다)."
        )


if __name__ == "__main__":
    main()
