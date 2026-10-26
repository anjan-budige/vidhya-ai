"""
Vidhya Bot — ORM Models Package

All 14 SQLAlchemy models exported from one place.
Import this module to ensure all models are registered with Base.metadata.
"""

from app.models.admin import Admin
from app.models.ai_chat_model import AIChatModel
from app.models.ai_embedding_model import AIEmbeddingModel
from app.models.ai_provider import AIProvider
from app.models.ai_query import AIQuery
from app.models.analytics import Analytics
from app.models.audit_log import AuditLog
from app.models.chunk import DocumentChunk
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.email_otp import EmailOTP
from app.models.message import Message
from app.models.payment import PaymentEvent, PaymentOrder, PaymentProvider
from app.models.plan import Plan
from app.models.platform_setting import PlatformSetting
from app.models.session import Session
from app.models.subscription import UserSubscription
from app.models.usage_tracking import UsageTracking
from app.models.user import User
from app.models.user_api_key import UserApiKey

__all__ = [
    "Admin",
    "AIChatModel",
    "AIEmbeddingModel",
    "AIProvider",
    "AIQuery",
    "Analytics",
    "AuditLog",
    "DocumentChunk",
    "Conversation",
    "Document",
    "EmailOTP",
    "Message",
    "PaymentEvent",
    "PaymentOrder",
    "PaymentProvider",
    "Plan",
    "PlatformSetting",
    "Session",
    "UserSubscription",
    "UsageTracking",
    "User",
    "UserApiKey",
]
