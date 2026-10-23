"""app/db/schemas/user.py

repository → service 경계에서 쓰는 내부 DTO. api/schemas 와는 별개다 —
여기 필드가 그대로 openapi.json 에 나가지 않는다 (예: password_hash).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str
    password_hash: str
    roles: str
    is_active: bool
    failed_login_count: int
    locked_until: datetime | None
    created_at: datetime
    updated_at: datetime | None

    @property
    def role_set(self) -> frozenset[str]:
        return frozenset(r.strip() for r in self.roles.split(",") if r.strip())
