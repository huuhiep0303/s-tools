from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from typing import Optional, List

from app.models.financial import FinancialRecord

async def get_financial_records(db: AsyncSession, user_id: str = None, month: str = None) -> List[FinancialRecord]:
    stmt = select(FinancialRecord)
    if user_id:
        stmt = stmt.filter(FinancialRecord.user_id == user_id)
    if month:
        stmt = stmt.filter(FinancialRecord.month == month)
    
    result = await db.execute(stmt)
    return result.scalars().all()

async def create_financial_record(db: AsyncSession, record_data: dict) -> FinancialRecord:
    db_record = FinancialRecord(**record_data)
    db.add(db_record)
    await db.commit()
    await db.refresh(db_record)
    return db_record

async def update_financial_record(db: AsyncSession, record_id: str, update_data: dict) -> Optional[FinancialRecord]:
    result = await db.execute(
        update(FinancialRecord)
        .where(FinancialRecord.id == record_id)
        .values(**update_data)
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount > 0:
        await db.commit()
        # Fetch and return the updated record
        updated = await db.execute(select(FinancialRecord).filter(FinancialRecord.id == record_id))
        return updated.scalars().first()
    return None
