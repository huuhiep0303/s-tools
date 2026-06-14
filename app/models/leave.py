import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Date, Enum, DateTime, ForeignKey, Text
from app.db import Base

class LeaveTypeEnum(str, enum.Enum):
    TRAINING = "training_leave"
    MONTHLY_MEETING = "meeting_leave"
    OTHER = "other"

class LeaveStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    type = Column(Enum(LeaveTypeEnum, name="leave_type_enum", create_type=False), nullable=False)
    date = Column(Date, nullable=False)
    reason = Column(Text, nullable=False)
    
    status = Column(Enum(LeaveStatusEnum, name="leave_status_enum", create_type=False), default=LeaveStatusEnum.PENDING, nullable=False)
    admin_notes = Column(Text, nullable=True) # Reason for rejection or notes
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
