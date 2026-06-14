import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

# Get DATABASE_URL from environment variable
# If not set, fallback to a local SQLite database for development
raw_db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./sgroup.db")

# If Railway provides postgres:// we need to convert it to postgresql+asyncpg://
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif raw_db_url.startswith("postgresql://"):
    raw_db_url = raw_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# SQLite specifically needs connect_args check_same_thread
connect_args = {"check_same_thread": False} if "sqlite" in raw_db_url else {}

engine = create_async_engine(
    raw_db_url,
    echo=False,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
