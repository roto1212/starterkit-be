"""app/db/models/__init__.py

alembic/env.py 의 target_metadata = Base.metadata 가 드리프트를 올바르게 잡으려면,
모든 모델이 여기서 import 되어 Base.metadata 에 등록되어 있어야 한다.
새 모델을 추가하면 반드시 아래에 import를 추가한다.
"""

from app.db.models.base import Base
from app.db.models.notice import Notice
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import AppUser

__all__ = ["Base", "AppUser", "RefreshToken", "Notice"]
