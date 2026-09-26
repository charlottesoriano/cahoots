import uuid
from datetime import datetime
from pydantic import BaseModel

# Event Invites - id, event_id, token, created_by, created_at, expires_at
class EventInviteValidate(BaseModel):
    token: str
    event_id: uuid.UUID | None = None
    expires_at: datetime | None = None
    is_valid: bool
    is_expired: bool
    is_member: bool

class EventInviteRead(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID
    token: str
    created_by: str
    created_at: datetime
    expires_at: datetime | None = None

    class Config:
        from_attributes = True