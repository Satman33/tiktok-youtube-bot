from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    is_banned = Column(Boolean, default=False)
    is_vip = Column(Boolean, default=False)
    daily_limit_override = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    usages = relationship("Usage", back_populates="user", cascade="all, delete-orphan")
    download_events = relationship(
        "DownloadEvent", back_populates="user", cascade="all, delete-orphan"
    )
    error_logs = relationship(
        "ErrorLog", back_populates="user", cascade="all, delete-orphan"
    )


class Usage(Base):
    __tablename__ = "usages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    requests_count = Column(Integer, default=0)
    date = Column(Date, nullable=False, index=True)

    user = relationship("User", back_populates="usages")

    __table_args__ = (Index("ix_usages_user_date", "user_id", "date", unique=True),)


class DownloadEvent(Base):
    __tablename__ = "download_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    telegram_id = Column(Integer, nullable=True, index=True)
    url = Column(Text, nullable=False)
    platform = Column(String(32), nullable=False, default="unknown")
    media_type = Column(String(32), nullable=True)
    status = Column(String(32), nullable=False, default="pending", index=True)
    title = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    file_count = Column(Integer, default=0)
    file_size_bytes = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="download_events")


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    telegram_id = Column(Integer, nullable=True, index=True)
    scope = Column(String(64), nullable=False, index=True)
    message = Column(Text, nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="error_logs")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(String(500), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
