"""
Vidhya Bot — ORM Models Package

All 14 SQLAlchemy models exported from one place.
Import this module to ensure all models are registered with Base.metadata.
"""

from app.models.admin import Admin
from app.models.ai_query import AIQuery
from app.models.analytics import Analytics
from app.models.audit_log import AuditLog
from app.models.chunk import DocumentChunk
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.message import Message
from app.models.payment import Payment
from app.models.plan import Plan
from app.models.session import Session
from app.models.subscription import UserSubscription
from app.models.usage_tracking import UsageTracking
from app.models.user import User

__all__ = [
    "Admin",
    "AIQuery",
    "Analytics",
    "AuditLog",
    "DocumentChunk",
    "Conversation",
    "Document",
    "Message",
    "Payment",
    "Plan",
    "Session",
    "UserSubscription",
    "UsageTracking",
    "User",
]
