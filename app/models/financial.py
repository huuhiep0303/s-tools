import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, Enum, DateTime, ForeignKey
from app.db import Base

class PaymentStatusEnum(str, enum.Enum):
    PAID = "PAID"
    UNPAID = "UNPAID"
    PARTIAL = "PARTIAL"

class FinancialRecord(Base):
    __tablename__ = "financial_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    month = Column(String(7), nullable=False) # Format: YYYY-MM
    amount_due = Column(Integer, default=200000, nullable=False)
    amount_paid = Column(Integer, default=0, nullable=False)
    
    status = Column(Enum(PaymentStatusEnum, name="payment_status_enum", create_type=False), default=PaymentStatusEnum.UNPAID, nullable=False)
    updated_by_admin_id = Column(String(36), ForeignKey("users.id"), nullable=True) # Which admin confirmed it
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
