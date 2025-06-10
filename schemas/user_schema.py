from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    color: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str
