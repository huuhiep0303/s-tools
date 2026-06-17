from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from sqlalchemy import update
from typing import Optional, List
from datetime import datetime

from app.models.training import Course, CourseSession, CourseMember

# --- Courses ---

async def get_all_courses(db: AsyncSession) -> List[Course]:
    result = await db.execute(select(Course))
    return result.scalars().all()

async def get_course_by_id(db: AsyncSession, course_id: str) -> Optional[Course]:
    result = await db.execute(select(Course).filter(Course.id == course_id))
    return result.scalars().first()

async def create_course(db: AsyncSession, course_data: dict) -> Course:
    db_course = Course(**course_data)
    db.add(db_course)
    await db.commit()
    await db.refresh(db_course)
    return db_course

async def update_course(db: AsyncSession, course_id: str, update_data: dict) -> Optional[Course]:
    result = await db.execute(
        update(Course)
        .where(Course.id == course_id)
        .values(**update_data)
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount > 0:
        await db.commit()
        return await get_course_by_id(db, course_id)
    return None

async def delete_course(db: AsyncSession, course_id: str) -> bool:
    from sqlalchemy import delete
    result = await db.execute(delete(Course).where(Course.id == course_id))
    if result.rowcount > 0:
        await db.commit()
        return True
    return False

# --- Course Sessions ---

async def get_sessions_by_course(db: AsyncSession, course_id: str) -> List[CourseSession]:
    result = await db.execute(select(CourseSession).filter(CourseSession.course_id == course_id).order_by(CourseSession.date))
    return result.scalars().all()

async def get_session_by_id(db: AsyncSession, session_id: str) -> Optional[CourseSession]:
    result = await db.execute(select(CourseSession).filter(CourseSession.id == session_id))
    return result.scalars().first()

async def create_course_session(db: AsyncSession, session_data: dict) -> CourseSession:
    db_session = CourseSession(**session_data)
    db.add(db_session)
    await db.commit()
    await db.refresh(db_session)
    return db_session

async def update_course_session(db: AsyncSession, session_id: str, update_data: dict) -> Optional[CourseSession]:
    result = await db.execute(
        update(CourseSession)
        .where(CourseSession.id == session_id)
        .values(**update_data)
        .execution_options(synchronize_session="fetch")
    )
    if result.rowcount > 0:
        await db.commit()
        return await get_session_by_id(db, session_id)
    return None

async def delete_course_session(db: AsyncSession, session_id: str) -> bool:
    from sqlalchemy import delete
    result = await db.execute(delete(CourseSession).where(CourseSession.id == session_id))
    if result.rowcount > 0:
        await db.commit()
        return True
    return False

# --- Course Members ---

async def get_members_by_course(db: AsyncSession, course_id: str) -> List[CourseMember]:
    result = await db.execute(select(CourseMember).filter(CourseMember.course_id == course_id))
    return result.scalars().all()

async def get_courses_by_user(db: AsyncSession, user_id: str) -> List[CourseMember]:
    result = await db.execute(select(CourseMember).filter(CourseMember.user_id == user_id))
    return result.scalars().all()

async def add_member_to_course(db: AsyncSession, course_id: str, user_id: str) -> CourseMember:
    # check if already exists
    result = await db.execute(select(CourseMember).filter(CourseMember.course_id == course_id, CourseMember.user_id == user_id))
    existing = result.scalars().first()
    if existing:
        return existing
        
    db_member = CourseMember(course_id=course_id, user_id=user_id)
    db.add(db_member)
    await db.commit()
    await db.refresh(db_member)
    return db_member

async def remove_member_from_course(db: AsyncSession, course_id: str, user_id: str) -> bool:
    from sqlalchemy import delete
    result = await db.execute(delete(CourseMember).where(CourseMember.course_id == course_id, CourseMember.user_id == user_id))
    if result.rowcount > 0:
        await db.commit()
        return True
    return False
