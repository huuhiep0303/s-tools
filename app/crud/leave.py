from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from typing import Optional, List
from datetime import date

from app.models.leave import LeaveRequest, LeaveTypeEnum

async def get_leave_requests(db: AsyncSession, user_id: str = None, leave_type: LeaveTypeEnum = None) -> List[LeaveRequest]:
    stmt = select(LeaveRequest)
    if user_id:
        stmt = stmt.filter(LeaveRequest.user_id == user_id)
    if leave_type:
        stmt = stmt.filter(LeaveRequest.type == leave_type)
        
    result = await db.execute(stmt)
    return result.scalars().all()

async def get_leaves_in_month(db: AsyncSession, month_start: date, month_end: date, leave_type: LeaveTypeEnum = None) -> int:
    from sqlalchemy import func
    stmt = select(func.count(LeaveRequest.id)).filter(LeaveRequest.date >= month_start, LeaveRequest.date <= month_end)
    if leave_type:
        stmt = stmt.filter(LeaveRequest.type == leave_type)
    result = await db.execute(stmt)
    return result.scalar() or 0

async def create_leave_request(db: AsyncSession, request_data: dict) -> LeaveRequest:
    db_request = LeaveRequest(**request_data)
    db.add(db_request)
    await db.commit()
    await db.refresh(db_request)
    return db_request

async def update_leave_request(db: AsyncSession, request_id: str, update_data: dict) -> Optional[LeaveRequest]:
    result = await db.execute(
        update(LeaveRequest)
        .where(LeaveRequest.id == request_id)
        .values(**update_data)
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount > 0:
        await db.commit()
        updated = await db.execute(select(LeaveRequest).filter(LeaveRequest.id == request_id))
        return updated.scalars().first()
    return None
