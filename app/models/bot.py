import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Boolean, Text
from app.db import Base

class BotHistory(Base):
    __tablename__ = "bot_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    facebook_id = Column(String, index=True, nullable=False)
    request_type = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    status = Column(String, nullable=False) # e.g. "SUCCESS", "FAILURE"
    
    created_at = Column(DateTime, default=datetime.utcnow)

class ManualReview(Base):
    __tablename__ = "manual_reviews"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_id = Column(String, index=True, nullable=False)
    sender_name = Column(String, nullable=True)
    message_content = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    
    reviewed = Column(Boolean, default=False, nullable=False)
    manual_classification = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
