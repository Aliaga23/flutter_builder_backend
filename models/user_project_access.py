import datetime
from sqlalchemy import Column, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base

class UserProjectAccess(Base):
    __tablename__ = "user_project_access"

    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("project.id", ondelete="CASCADE"), primary_key=True)
    granted_at = Column(TIMESTAMP, default=datetime.datetime.utcnow)
