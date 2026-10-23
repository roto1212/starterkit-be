"""app/db/schemas/refresh_token.py — repository → service 경계 내부 DTO."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RefreshTokenRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    token_id: int
    user_id: int
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime
