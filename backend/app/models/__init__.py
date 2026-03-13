"""
app/models/__init__.py

Import all models here so Base.metadata knows about every table.
Without this, create_tables() / Alembic autogenerate misses models
that haven't been explicitly imported elsewhere in the startup path.

Also re-exports the most-used symbols so route files can do:
    from app.models import User, Video, VideoStatus
instead of reaching into sub-modules directly.
"""

from app.models.user import (       # noqa: F401
    User,
    UserSettings,
    UserSubscription,
    SubscriptionTier,
)
from app.models.video import (      # noqa: F401
    Video,
    VideoScene,
    VideoSchedule,
    VideoStatus,
    VideoType,
    VideoStyle,
    SceneStatus,
)
from app.models.payment import (    # noqa: F401
    Payment,
    PaymentStatus,
    PaymentType,
    SubscriptionPlan,
    CreditPackage,
    seed_default_plans,
    seed_default_packages,
)

__all__ = [
    # Users
    "User", "UserSettings", "UserSubscription", "SubscriptionTier",
    # Videos
    "Video", "VideoScene", "VideoSchedule",
    "VideoStatus", "VideoType", "VideoStyle", "SceneStatus",
    # Payments
    "Payment", "PaymentStatus", "PaymentType",
    "SubscriptionPlan", "CreditPackage",
    "seed_default_plans", "seed_default_packages",
]
