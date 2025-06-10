import uuid
import datetime
from sqlalchemy import Column, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base

class User(Base):
    __tablename__ = "user"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, nullable=False)
    email = Column(String, unique=True)
    password = Column(String, nullable=False)
    color = Column(String, default="#3b82f6")
    created_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)
