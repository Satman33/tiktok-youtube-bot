from datetime import date, datetime

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    id: int
    telegram_id: int
    is_banned: bool
    is_vip: bool
    daily_limit_override: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class UserListItem(UserResponse):
    today_downloads: int = 0
    effective_daily_limit: int
    last_download_at: datetime | None = None


class UsersListResponse(BaseModel):
    items: list[UserListItem]
    total: int
    page: int
    page_size: int


class StatsTrendPoint(BaseModel):
    date: date
    downloads: int


class StatsResponse(BaseModel):
    total_users: int
    total_downloads: int
    today_downloads: int
    last_7_days_downloads: int
    last_30_days_downloads: int
    banned_users: int
    vip_users: int
    success_rate: float
    top_users: list[dict[str, int]]
    recent_trend: list[StatsTrendPoint]


class DownloadEventResponse(BaseModel):
    id: int
    telegram_id: int | None
    url: str
    platform: str
    media_type: str | None
    status: str
    title: str | None
    error_message: str | None
    file_count: int
    file_size_bytes: int
    created_at: datetime

    class Config:
        from_attributes = True


class DownloadEventsListResponse(BaseModel):
    items: list[DownloadEventResponse]
    total: int
    page: int
    page_size: int


class ErrorLogResponse(BaseModel):
    id: int
    telegram_id: int | None
    scope: str
    message: str
    details: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ErrorLogsListResponse(BaseModel):
    items: list[ErrorLogResponse]
    total: int
    page: int
    page_size: int


class ServiceStatusResponse(BaseModel):
    api: str
    database: str
    cookies_file: bool
    yt_dlp_available: bool
    node_available: bool
    redis_configured: bool
    database_url: str
    redis_url: str
    global_daily_limit: int


class LimitUpdateRequest(BaseModel):
    daily_limit: int = Field(..., ge=1, le=1000)


class UserLimitUpdateRequest(BaseModel):
    daily_limit_override: int | None = Field(default=None, ge=1, le=1000)


class UserVipUpdateRequest(BaseModel):
    is_vip: bool


class AppSettingsResponse(BaseModel):
    global_daily_limit: int


class ActionResponse(BaseModel):
    status: str
    detail: str


class DownloadTestRequest(BaseModel):
    url: str


class DownloadTestResponse(BaseModel):
    success: bool
    platform: str
    media_type: str | None = None
    title: str | None = None
    error: str | None = None
