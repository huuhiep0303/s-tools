from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, desc
from typing import Optional, List

from app.models.bot import BotHistory, ManualReview

async def get_bot_history(db: AsyncSession, limit: int = 50) -> List[BotHistory]:
    result = await db.execute(select(BotHistory).order_by(desc(BotHistory.created_at)).limit(limit))
    return result.scalars().all()

async def create_bot_history(db: AsyncSession, history_data: dict) -> BotHistory:
    db_history = BotHistory(**history_data)
    db.add(db_history)
    await db.commit()
    await db.refresh(db_history)
    return db_history

async def get_manual_reviews(db: AsyncSession, reviewed: bool = None) -> List[ManualReview]:
    stmt = select(ManualReview).order_by(desc(ManualReview.created_at))
    if reviewed is not None:
        stmt = stmt.filter(ManualReview.reviewed == reviewed)
    
    result = await db.execute(stmt)
    return result.scalars().all()

async def create_manual_review(db: AsyncSession, review_data: dict) -> ManualReview:
    db_review = ManualReview(**review_data)
    db.add(db_review)
    await db.commit()
    await db.refresh(db_review)
    return db_review

async def resolve_manual_review(db: AsyncSession, review_id: str, final_category: str) -> Optional[ManualReview]:
    result = await db.execute(
        update(ManualReview)
        .where(ManualReview.id == review_id)
        .values(reviewed=True, manual_classification=final_category)
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount > 0:
        await db.commit()
        updated = await db.execute(select(ManualReview).filter(ManualReview.id == review_id))
        return updated.scalars().first()
    return None
