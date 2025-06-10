from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Any

class ProjectCreate(BaseModel):
    name: str
    data: dict

class ProjectOut(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    created_at: datetime
    updated_at: datetime | None
    data: dict

    class Config:
        from_attributes = True
