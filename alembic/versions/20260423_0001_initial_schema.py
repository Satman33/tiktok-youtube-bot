"""initial schema

Revision ID: 20260423_0001
Revises:
Create Date: 2026-04-23 22:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260423_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.Integer(), nullable=False),
        sa.Column("is_banned", sa.Boolean(), nullable=True),
        sa.Column("is_vip", sa.Boolean(), nullable=True),
        sa.Column("daily_limit_override", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "download_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("telegram_id", sa.Integer(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("media_type", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("file_count", sa.Integer(), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_download_events_created_at", "download_events", ["created_at"], unique=False)
    op.create_index("ix_download_events_id", "download_events", ["id"], unique=False)
    op.create_index("ix_download_events_status", "download_events", ["status"], unique=False)
    op.create_index("ix_download_events_telegram_id", "download_events", ["telegram_id"], unique=False)
    op.create_index("ix_download_events_user_id", "download_events", ["user_id"], unique=False)

    op.create_table(
        "error_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("telegram_id", sa.Integer(), nullable=True),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_error_logs_created_at", "error_logs", ["created_at"], unique=False)
    op.create_index("ix_error_logs_id", "error_logs", ["id"], unique=False)
    op.create_index("ix_error_logs_scope", "error_logs", ["scope"], unique=False)
    op.create_index("ix_error_logs_telegram_id", "error_logs", ["telegram_id"], unique=False)
    op.create_index("ix_error_logs_user_id", "error_logs", ["user_id"], unique=False)

    op.create_table(
        "usages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("requests_count", sa.Integer(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_usages_date", "usages", ["date"], unique=False)
    op.create_index("ix_usages_id", "usages", ["id"], unique=False)
    op.create_index("ix_usages_user_date", "usages", ["user_id", "date"], unique=True)

    op.execute(
        sa.text(
            "INSERT INTO app_settings (key, value, updated_at) VALUES "
            "('global_daily_limit', '5', NOW())"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_usages_user_date", table_name="usages")
    op.drop_index("ix_usages_id", table_name="usages")
    op.drop_index("ix_usages_date", table_name="usages")
    op.drop_table("usages")

    op.drop_index("ix_error_logs_user_id", table_name="error_logs")
    op.drop_index("ix_error_logs_telegram_id", table_name="error_logs")
    op.drop_index("ix_error_logs_scope", table_name="error_logs")
    op.drop_index("ix_error_logs_id", table_name="error_logs")
    op.drop_index("ix_error_logs_created_at", table_name="error_logs")
    op.drop_table("error_logs")

    op.drop_index("ix_download_events_user_id", table_name="download_events")
    op.drop_index("ix_download_events_telegram_id", table_name="download_events")
    op.drop_index("ix_download_events_status", table_name="download_events")
    op.drop_index("ix_download_events_id", table_name="download_events")
    op.drop_index("ix_download_events_created_at", table_name="download_events")
    op.drop_table("download_events")

    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")

    op.drop_table("app_settings")
