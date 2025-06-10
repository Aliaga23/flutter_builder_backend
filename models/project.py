import uuid
import datetime
from sqlalchemy import Column, String, TIMESTAMP, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from core.database import Base

class Project(Base):
    __tablename__ = "project"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"))
    created_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    data = Column(JSON, nullable=False)
