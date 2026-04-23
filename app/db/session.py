from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import Base

settings = get_settings()

engine_kwargs = {
    "echo": False,
    "future": True,
}

if settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await run_lightweight_migrations(conn)
        await ensure_default_settings(conn)


async def run_lightweight_migrations(conn):
    if settings.DATABASE_URL.startswith("sqlite"):
        existing_columns = await conn.execute(text("PRAGMA table_info(users)"))
        user_columns = {row[1] for row in existing_columns.fetchall()}

        if "is_vip" not in user_columns:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN is_vip BOOLEAN DEFAULT 0")
            )

        if "daily_limit_override" not in user_columns:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN daily_limit_override INTEGER")
            )


async def ensure_default_settings(conn):
    await conn.execute(
        text(
            "INSERT INTO app_settings (key, value, updated_at) "
            "SELECT 'global_daily_limit', :value, CURRENT_TIMESTAMP "
            "WHERE NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'global_daily_limit')"
        ),
        {"value": str(settings.DAILY_LIMIT)},
    )


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
