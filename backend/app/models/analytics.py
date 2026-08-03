"""
Vidhya Bot — Analytics Model

Aggregated metrics for dashboard — daily/weekly/monthly rollups
of user activity, revenue, AI usage, and system performance.
"""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import UUIDPrimaryKeyMixin


class Analytics(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "analytics"
    __table_args__ = (
        UniqueConstraint(
            "metric_name", "period_type", "period_date", "dimensions",
            name="uq_analytics_metric_period"
        ),
    )

    # ── Metric ────────────────────────────────────────────────────
    metric_name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # e.g. "total_users", "revenue", "ai_queries", "avg_response_time"
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    dimensions: Mapped[Optional[dict]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )  # e.g. {"plan": "premium"}, {"model": "qwen:4b-instruct"}

    # ── Period ────────────────────────────────────────────────────
    period_type: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # 'daily' | 'weekly' | 'monthly'
    period_date: Mapped[date] = mapped_column(Date, nullable=False)

    # ── Timestamp ─────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<Analytics(metric='{self.metric_name}', value={self.metric_value}, "
            f"{self.period_type}={self.period_date})>"
        )
