import os
import shutil
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ActionResponse,
    AppSettingsResponse,
    DownloadEventsListResponse,
    DownloadEventResponse,
    DownloadTestRequest,
    DownloadTestResponse,
    ErrorLogsListResponse,
    ErrorLogResponse,
    LimitUpdateRequest,
    ServiceStatusResponse,
    StatsResponse,
    StatsTrendPoint,
    UserLimitUpdateRequest,
    UserListItem,
    UserVipUpdateRequest,
    UsersListResponse,
)
from app.config import get_settings
from app.db.models import AppSetting, DownloadEvent, ErrorLog, Usage, User
from app.db.session import get_db
from app.services.downloader import probe_media
from app.services.limiter import (
    get_user_by_telegram_id,
    reset_usage_for_user,
    set_user_limit_override,
    set_user_vip,
)

router = APIRouter()
settings = get_settings()


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


async def upsert_app_setting(db: AsyncSession, key: str, value: str) -> None:
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    app_setting = result.scalar_one_or_none()
    if app_setting:
        app_setting.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    await db.commit()


@router.get("/users", response_model=UsersListResponse)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = None,
    banned: bool | None = None,
    vip: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if search:
        filters.append(cast(User.telegram_id, String).like(f"%{search}%"))
    if banned is not None:
        filters.append(User.is_banned == banned)
    if vip is not None:
        filters.append(User.is_vip == vip)

    total_query = select(func.count(User.id))
    if filters:
        total_query = total_query.where(*filters)
    total = (await db.execute(total_query)).scalar() or 0

    query = select(User).order_by(User.created_at.desc())
    if filters:
        query = query.where(*filters)
    query = query.offset((page - 1) * page_size).limit(page_size)

    users = (await db.execute(query)).scalars().all()
    today = date.today()
    global_limit = await get_global_daily_limit(db)
    items: list[UserListItem] = []

    for user in users:
        usage_result = await db.execute(
            select(Usage).where(Usage.user_id == user.id, Usage.date == today)
        )
        usage = usage_result.scalar_one_or_none()
        last_event_result = await db.execute(
            select(DownloadEvent.created_at)
            .where(DownloadEvent.user_id == user.id)
            .order_by(DownloadEvent.created_at.desc())
            .limit(1)
        )
        last_download_at = last_event_result.scalar_one_or_none()
        effective_limit = (
            user.daily_limit_override
            if user.daily_limit_override
            else global_limit * 10 if user.is_vip else global_limit
        )
        items.append(
            UserListItem(
                id=user.id,
                telegram_id=user.telegram_id,
                is_banned=user.is_banned,
                is_vip=user.is_vip,
                daily_limit_override=user.daily_limit_override,
                created_at=user.created_at,
                today_downloads=usage.requests_count if usage else 0,
                effective_daily_limit=effective_limit,
                last_download_at=last_download_at,
            )
        )

    return UsersListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/ban/{telegram_id}", response_model=ActionResponse)
async def ban_user(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_telegram_id(db, telegram_id)
    if not user:
        user = User(telegram_id=telegram_id, is_banned=True)
        db.add(user)
    else:
        user.is_banned = True
    await db.commit()
    return ActionResponse(status="ok", detail=f"User {telegram_id} banned")


@router.post("/unban/{telegram_id}", response_model=ActionResponse)
async def unban_user(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_banned = False
    await db.commit()
    return ActionResponse(status="ok", detail=f"User {telegram_id} unbanned")


@router.post("/users/{telegram_id}/vip", response_model=ActionResponse)
async def update_user_vip(
    telegram_id: int,
    payload: UserVipUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await set_user_vip(db, user, payload.is_vip)
    return ActionResponse(
        status="ok",
        detail=f"VIP status for user {telegram_id} updated to {payload.is_vip}",
    )


@router.post("/users/{telegram_id}/limit", response_model=ActionResponse)
async def update_user_limit(
    telegram_id: int,
    payload: UserLimitUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await set_user_limit_override(db, user, payload.daily_limit_override)
    return ActionResponse(status="ok", detail=f"Limit updated for user {telegram_id}")


@router.post("/users/{telegram_id}/reset-usage", response_model=ActionResponse)
async def reset_user_usage(telegram_id: int, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_telegram_id(db, telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await reset_usage_for_user(db, user)
    return ActionResponse(status="ok", detail=f"Usage reset for user {telegram_id}")


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    banned_users = (
        await db.execute(select(func.count(User.id)).where(User.is_banned.is_(True)))
    ).scalar() or 0
    vip_users = (
        await db.execute(select(func.count(User.id)).where(User.is_vip.is_(True)))
    ).scalar() or 0
    total_downloads = (
        await db.execute(select(func.sum(Usage.requests_count)))
    ).scalar() or 0

    today = date.today()
    today_downloads = (
        await db.execute(select(func.sum(Usage.requests_count)).where(Usage.date == today))
    ).scalar() or 0
    last_7_days_downloads = (
        await db.execute(
            select(func.sum(Usage.requests_count)).where(
                Usage.date >= today - timedelta(days=6)
            )
        )
    ).scalar() or 0
    last_30_days_downloads = (
        await db.execute(
            select(func.sum(Usage.requests_count)).where(
                Usage.date >= today - timedelta(days=29)
            )
        )
    ).scalar() or 0

    events_total = (
        await db.execute(select(func.count(DownloadEvent.id)))
    ).scalar() or 0
    success_events = (
        await db.execute(
            select(func.count(DownloadEvent.id)).where(DownloadEvent.status == "success")
        )
    ).scalar() or 0
    success_rate = round((success_events / events_total) * 100, 1) if events_total else 0.0

    top_result = await db.execute(
        select(DownloadEvent.telegram_id, func.count(DownloadEvent.id).label("count"))
        .where(DownloadEvent.telegram_id.is_not(None))
        .group_by(DownloadEvent.telegram_id)
        .order_by(desc("count"))
        .limit(5)
    )
    top_users = [
        {"telegram_id": row.telegram_id, "downloads": row.count} for row in top_result.all()
    ]

    trend_result = await db.execute(
        select(Usage.date, func.sum(Usage.requests_count).label("downloads"))
        .where(Usage.date >= today - timedelta(days=6))
        .group_by(Usage.date)
        .order_by(Usage.date.asc())
    )
    trend = [
        StatsTrendPoint(date=row.date, downloads=row.downloads) for row in trend_result.all()
    ]

    return StatsResponse(
        total_users=total_users,
        total_downloads=total_downloads,
        today_downloads=today_downloads,
        last_7_days_downloads=last_7_days_downloads,
        last_30_days_downloads=last_30_days_downloads,
        banned_users=banned_users,
        vip_users=vip_users,
        success_rate=success_rate,
        top_users=top_users,
        recent_trend=trend,
    )


@router.get("/downloads", response_model=DownloadEventsListResponse)
async def list_downloads(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    platform: str | None = None,
    status: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if platform:
        filters.append(DownloadEvent.platform == platform)
    if status:
        filters.append(DownloadEvent.status == status)
    if search:
        filters.append(
            or_(
                cast(DownloadEvent.telegram_id, String).like(f"%{search}%"),
                DownloadEvent.url.like(f"%{search}%"),
                DownloadEvent.title.like(f"%{search}%"),
            )
        )

    total_query = select(func.count(DownloadEvent.id))
    if filters:
        total_query = total_query.where(*filters)
    total = (await db.execute(total_query)).scalar() or 0

    query = select(DownloadEvent).order_by(DownloadEvent.created_at.desc())
    if filters:
        query = query.where(*filters)
    query = query.offset((page - 1) * page_size).limit(page_size)

    items = (await db.execute(query)).scalars().all()
    return DownloadEventsListResponse(
        items=[
            DownloadEventResponse(
                id=item.id,
                telegram_id=item.telegram_id,
                url=item.url,
                platform=item.platform,
                media_type=item.media_type,
                status=item.status,
                title=item.title,
                error_message=item.error_message,
                file_count=item.file_count,
                file_size_bytes=item.file_size_bytes,
                created_at=item.created_at,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/errors", response_model=ErrorLogsListResponse)
async def list_errors(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    scope: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if scope:
        filters.append(ErrorLog.scope == scope)
    if search:
        filters.append(
            or_(
                ErrorLog.message.like(f"%{search}%"),
                ErrorLog.details.like(f"%{search}%"),
                cast(ErrorLog.telegram_id, String).like(f"%{search}%"),
            )
        )

    total_query = select(func.count(ErrorLog.id))
    if filters:
        total_query = total_query.where(*filters)
    total = (await db.execute(total_query)).scalar() or 0

    query = select(ErrorLog).order_by(ErrorLog.created_at.desc())
    if filters:
        query = query.where(*filters)
    query = query.offset((page - 1) * page_size).limit(page_size)

    items = (await db.execute(query)).scalars().all()
    return ErrorLogsListResponse(
        items=[
            ErrorLogResponse(
                id=item.id,
                telegram_id=item.telegram_id,
                scope=item.scope,
                message=item.message,
                details=item.details,
                created_at=item.created_at,
            )
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/settings", response_model=AppSettingsResponse)
async def get_app_settings(db: AsyncSession = Depends(get_db)):
    return AppSettingsResponse(global_daily_limit=await get_global_daily_limit(db))


@router.post("/settings/limit", response_model=ActionResponse)
async def update_global_limit(
    payload: LimitUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    await upsert_app_setting(db, "global_daily_limit", str(payload.daily_limit))
    return ActionResponse(status="ok", detail="Global daily limit updated")


@router.get("/service-status", response_model=ServiceStatusResponse)
async def get_service_status(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(select(func.count(User.id)))
        database_status = "ok"
    except Exception:
        database_status = "error"

    yt_dlp_available = shutil.which("yt-dlp") is not None
    node_available = shutil.which("node") is not None

    return ServiceStatusResponse(
        api="ok",
        database=database_status,
        cookies_file=os.path.exists(settings.YTDLP_COOKIES_PATH),
        yt_dlp_available=yt_dlp_available,
        node_available=node_available,
        redis_configured=bool(settings.REDIS_URL),
        database_url=settings.DATABASE_URL,
        redis_url=settings.REDIS_URL,
        global_daily_limit=await get_global_daily_limit(db),
    )


@router.post("/downloads/test", response_model=DownloadTestResponse)
async def test_download(
    payload: DownloadTestRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await probe_media(payload.url)
    return DownloadTestResponse(
        success=result.success,
        platform=result.platform.value,
        media_type=result.media_type.value if result.media_type else None,
        title=result.title,
        error=result.error,
    )
