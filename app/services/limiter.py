from datetime import date, datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import AppSetting, User, Usage
from app.config import get_settings

settings = get_settings()


async def ensure_user_exists(db: AsyncSession, telegram_id: int) -> User:
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(telegram_id=telegram_id)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user


async def get_user_usage(db: AsyncSession, user: User) -> tuple[int, date]:
    today = date.today()

    result = await db.execute(
        select(Usage).where(Usage.user_id == user.id, Usage.date == today)
    )
    usage = result.scalar_one_or_none()

    if not usage:
        usage = Usage(user_id=user.id, requests_count=0, date=today)
        db.add(usage)
        await db.commit()
        await db.refresh(usage)

    return usage.requests_count, usage.date


async def increment_usage(db: AsyncSession, user: User) -> bool:
    today = date.today()

    result = await db.execute(
        select(Usage).where(Usage.user_id == user.id, Usage.date == today)
    )
    usage = result.scalar_one_or_none()

    if not usage:
        usage = Usage(user_id=user.id, requests_count=1, date=today)
        db.add(usage)
    else:
        usage.requests_count += 1

    await db.commit()

    return usage.requests_count <= await get_user_daily_limit(db, user)


async def check_limit(db: AsyncSession, user: User) -> tuple[bool, int, int]:
    """Check if user has remaining downloads. Returns (allowed, current_count, limit)."""
    current_count, _ = await get_user_usage(db, user)
    limit = await get_user_daily_limit(db, user)
    remaining = limit - current_count

    if remaining <= 0:
        return False, current_count, limit

    return True, current_count, limit


async def get_global_daily_limit(db: AsyncSession) -> int:
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == "global_daily_limit")
    )
    app_setting = result.scalar_one_or_none()
    if not app_setting:
        return settings.DAILY_LIMIT

    try:
        return int(app_setting.value)
    except ValueError:
        return settings.DAILY_LIMIT


async def get_user_daily_limit(db: AsyncSession, user: User) -> int:
    global_limit = await get_global_daily_limit(db)

    if user.is_vip:
        return user.daily_limit_override or global_limit * 10

    if user.daily_limit_override and user.daily_limit_override > 0:
        return user.daily_limit_override

    return global_limit


async def is_user_banned(db: AsyncSession, telegram_id: int) -> bool:
    user = await ensure_user_exists(db, telegram_id)
    return user.is_banned


async def ban_user(db: AsyncSession, telegram_id: int) -> bool:
    user = await ensure_user_exists(db, telegram_id)
    user.is_banned = True
    await db.commit()
    return True


async def unban_user(db: AsyncSession, telegram_id: int) -> bool:
    user = await ensure_user_exists(db, telegram_id)
    user.is_banned = False
    await db.commit()
    return True


async def get_all_users(
    db: AsyncSession, limit: int = 100, offset: int = 0
) -> list[User]:
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    return result.scalars().all()


async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> User | None:
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_total_downloads(db: AsyncSession) -> int:
    result = await db.execute(select(Usage))
    usages = result.scalars().all()
    return sum(u.requests_count for u in usages)


async def get_total_users(db: AsyncSession) -> int:
    result = await db.execute(select(User))
    return len(result.scalars().all())


async def reset_usage_for_user(db: AsyncSession, user: User) -> None:
    today = date.today()
    result = await db.execute(
        select(Usage).where(Usage.user_id == user.id, Usage.date == today)
    )
    usage = result.scalar_one_or_none()
    if usage:
        usage.requests_count = 0
        await db.commit()


async def set_user_vip(db: AsyncSession, user: User, is_vip: bool) -> User:
    user.is_vip = is_vip
    await db.commit()
    await db.refresh(user)
    return user


async def set_user_limit_override(
    db: AsyncSession, user: User, limit_override: int | None
) -> User:
    user.daily_limit_override = limit_override
    await db.commit()
    await db.refresh(user)
    return user
