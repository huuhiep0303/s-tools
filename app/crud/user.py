from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from typing import Optional, List

from app.models.user import User, StatusEnum

async def get_user(db: AsyncSession, user_id: str) -> Optional[User]:
    result = await db.execute(select(User).filter(User.id == user_id))
    return result.scalars().first()

async def get_user_by_facebook_id(db: AsyncSession, facebook_id: str) -> Optional[User]:
    result = await db.execute(select(User).filter(User.facebook_id == facebook_id))
    return result.scalars().first()

async def get_user_by_phone(db: AsyncSession, phone: str) -> Optional[User]:
    result = await db.execute(select(User).filter(User.phone == phone))
    return result.scalars().first()

async def get_all_users(db: AsyncSession) -> List[User]:
    result = await db.execute(select(User))
    return result.scalars().all()

async def create_user(db: AsyncSession, user_data: dict) -> User:
    db_user = User(**user_data)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def update_user(db: AsyncSession, facebook_id: str, update_data: dict) -> Optional[User]:
    result = await db.execute(
        update(User)
        .where(User.facebook_id == facebook_id)
        .values(**update_data)
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount > 0:
        await db.commit()
        return await get_user_by_facebook_id(db, facebook_id)
    return None

async def count_users_by_status(db: AsyncSession, status: StatusEnum) -> int:
    # A bit inefficient for large DBs to load all and count, but fine for now
    # Or use func.count
    from sqlalchemy import func
    result = await db.execute(select(func.count(User.id)).filter(User.status == status))
    return result.scalar() or 0

async def update_user_by_id(db: AsyncSession, user_id: str, update_data: dict) -> Optional[User]:
    result = await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(**update_data)
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount > 0:
        await db.commit()
        return await get_user(db, user_id)
    return None

async def delete_user_by_id(db: AsyncSession, user_id: str) -> bool:
    from sqlalchemy import delete
    result = await db.execute(delete(User).where(User.id == user_id))
    if result.rowcount > 0:
        await db.commit()
        return True
    return False
