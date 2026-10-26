"""Vidhya Bot — Analytics Schemas"""

from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.schemas.base import VidhyaBaseModel


class DashboardStats(BaseModel):
    """Admin dashboard summary stats."""
    total_users: int = 0
    active_users_today: int = 0
    total_conversations: int = 0
    total_messages_today: int = 0
    total_tokens_today: int = 0
    total_revenue: float = 0.0
    revenue_this_month: float = 0.0
    active_subscriptions: int = 0
    total_documents: int = 0


class UserAnalytics(BaseModel):
    """User growth analytics."""
    period: str
    data: List[Dict[str, int]]  # [{"date": "2024-05-28", "new_users": 5, "active_users": 120}]


class RevenueAnalytics(BaseModel):
    """Revenue analytics."""
    total_revenue: float
    period: str
    data: List[Dict]  # [{"date": "2024-05-28", "amount": 2999, "transactions": 10}]
    by_plan: Dict[str, float]  # {"basic": 990, "premium": 2990}


class RAGAnalytics(BaseModel):
    """RAG pipeline analytics."""
    total_queries: int
    avg_response_time_ms: float
    cache_hit_rate: float
    avg_chunks_retrieved: float
    avg_confidence_score: float


class ConversationAnalytics(BaseModel):
    """Conversation analytics."""
    total_conversations: int
    avg_messages_per_conversation: float
    avg_conversation_duration_min: float
    timeout_rate: float
    by_status: Dict[str, int]


class QuotaUsageAnalytics(BaseModel):
    """Quota usage analytics across all users."""
    avg_daily_usage_percent: float
    users_at_daily_limit: int
    users_at_monthly_limit: int
    by_plan: Dict[str, Dict[str, float]]
