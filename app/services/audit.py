from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DownloadEvent, ErrorLog, User


async def create_download_event(
    db: AsyncSession,
    telegram_id: int | None,
    url: str,
    platform: str,
    user: User | None = None,
    media_type: str | None = None,
    status: str = "pending",
    title: str | None = None,
    error_message: str | None = None,
    file_count: int = 0,
    file_size_bytes: int = 0,
) -> DownloadEvent:
    event = DownloadEvent(
        user_id=user.id if user else None,
        telegram_id=telegram_id,
        url=url,
        platform=platform,
        media_type=media_type,
        status=status,
        title=title,
        error_message=error_message,
        file_count=file_count,
        file_size_bytes=file_size_bytes,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def update_download_event(
    db: AsyncSession,
    event: DownloadEvent,
    *,
    status: str | None = None,
    media_type: str | None = None,
    title: str | None = None,
    error_message: str | None = None,
    file_count: int | None = None,
    file_size_bytes: int | None = None,
) -> DownloadEvent:
    if status is not None:
        event.status = status
    if media_type is not None:
        event.media_type = media_type
    if title is not None:
        event.title = title
    if error_message is not None:
        event.error_message = error_message
    if file_count is not None:
        event.file_count = file_count
    if file_size_bytes is not None:
        event.file_size_bytes = file_size_bytes

    await db.commit()
    await db.refresh(event)
    return event


async def log_error(
    db: AsyncSession,
    scope: str,
    message: str,
    *,
    details: str | None = None,
    telegram_id: int | None = None,
    user: User | None = None,
) -> ErrorLog:
    error_log = ErrorLog(
        user_id=user.id if user else None,
        telegram_id=telegram_id,
        scope=scope,
        message=message,
        details=details,
    )
    db.add(error_log)
    await db.commit()
    await db.refresh(error_log)
    return error_log
