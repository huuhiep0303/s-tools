import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Enum, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.db import Base

class RoleEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    USER = "USER"

class StatusEnum(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    QUIT = "QUIT"

class FeeEligibilityEnum(str, enum.Enum):
    ELIGIBLE = "ELIGIBLE"
    EXEMPT = "EXEMPT"

class User(Base):
    __tablename__ = "users"

    # We use String to store UUID as text in sqlite, or native UUID in Postgres
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    facebook_id = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, unique=True, index=True, nullable=True)
    full_name = Column(String, nullable=False)
    
    role = Column(Enum(RoleEnum, name="role_enum", create_type=False), default=RoleEnum.USER, nullable=False)
    status = Column(Enum(StatusEnum, name="status_enum", create_type=False), default=StatusEnum.ACTIVE, nullable=False)
    fee_eligibility = Column(Enum(FeeEligibilityEnum, name="fee_eligibility_enum", create_type=False), default=FeeEligibilityEnum.ELIGIBLE, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
