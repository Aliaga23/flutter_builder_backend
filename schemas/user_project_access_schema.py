from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class UserProjectAccessCreate(BaseModel):
    user_id: UUID
    project_id: UUID

class UserProjectAccessOut(BaseModel):
    user_id: UUID
    project_id: UUID
    granted_at: datetime

    class Config:
        from_attributes = True
