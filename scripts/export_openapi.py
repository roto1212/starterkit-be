"""scripts/export_openapi.py

app.openapi()를 파일로 내보낸다. 서버 기동도 DB 연결도 하지 않는다
(lifespan은 실행되지 않는다 — app.main:app을 import만 할 뿐이다).

FE 킷은 이 파일을 openapi-typescript 등으로 소비한다. BE/FE가 별도 레포이므로,
커밋된 openapi.json이 두 레포 사이의 유일한 계약 문서가 된다.

사용:
    uv run python scripts/export_openapi.py            # openapi.json 갱신
    uv run python scripts/export_openapi.py --check     # 커밋된 파일과 다르면 비영 종료 (CI용)
"""

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_OUTPUT_PATH = _ROOT / "openapi.json"

# `python scripts/export_openapi.py`로 실행하면 sys.path[0]이 scripts/가 되어
# `app` 패키지를 못 찾는다 — 프로젝트 루트를 직접 넣어준다.
sys.path.insert(0, str(_ROOT))


def _generate() -> str:
    from app.main import app

    spec = app.openapi()
    return json.dumps(spec, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    check_mode = "--check" in sys.argv
    generated = _generate()

    if check_mode:
        current = _OUTPUT_PATH.read_text(encoding="utf-8") if _OUTPUT_PATH.exists() else ""
        if generated != current:
            print(
                "openapi.json이 최신이 아닙니다. "
                "uv run python scripts/export_openapi.py 로 갱신 후 커밋하세요.",
                file=sys.stderr,
            )
            sys.exit(1)
        print("openapi.json is up to date.")
        return

    _OUTPUT_PATH.write_text(generated, encoding="utf-8")
    print(f"Wrote {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
