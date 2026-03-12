"""
Payment and subscription models.
FILE: app/models/payment.py

FIXES:
1. Payment.status used PaymentStatus.SUCCESS but payments.py code checks
   for PaymentStatus.COMPLETED — mismatch meant completed payments were
   never found by the verification query. Renamed SUCCESS → COMPLETED
   and added COMPLETED = "completed" to match payments.py usage.

2. Payment.payment_type stored as SQLEnum(PaymentType) but payments.py
   creates records with payment_type="credits" (plain string). SQLAlchemy
   enum column rejects raw strings that don't match — silent insert failure.
   Fixed: use String(50) with a check constraint instead of SQLEnum,
   matching how every caller actually writes this field.

3. Payment.status same issue — stored as SQLEnum(PaymentStatus) but
   payments.py queries Payment.status == PaymentStatus.COMPLETED while
   webhook writes payment.status = PaymentStatus.COMPLETED. Both work
   correctly now that COMPLETED exists in the enum.

4. CreditPackage and SubscriptionPlan had no seed data helper. On a fresh
   Render deploy the /plans and /credit-packages endpoints returned empty
   lists. Added seed_default_plans() and seed_default_packages() called
   from main.py lifespan after create_tables().
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Session, relationship

from app.db.base import Base


# ─── ENUMS ────────────────────────────────────────────────────────────────────

class PaymentStatus(str, Enum):
    PENDING   = "pending"
    COMPLETED = "completed"   # FIX 1 — was "success", payments.py uses COMPLETED
    FAILED    = "failed"
    ABANDONED = "abandoned"
    REFUNDED  = "refunded"


class PaymentType(str, Enum):
    SUBSCRIPTION = "subscription"
    CREDITS      = "credits"
    ONE_TIME     = "one_time"


# ─── SUBSCRIPTION PLAN ────────────────────────────────────────────────────────

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id          = Column(String(36), primary_key=True, index=True)
    name        = Column(String(50),  nullable=False)
    slug        = Column(String(50),  unique=True, nullable=False)
    description = Column(Text,        nullable=True)

    # Pricing — Naira (primary) + USD (international)
    price_monthly_ngn = Column(Float, nullable=True)
    price_yearly_ngn  = Column(Float, nullable=True)
    price_monthly_usd = Column(Float, nullable=True)
    price_yearly_usd  = Column(Float, nullable=True)
    currency          = Column(String(3), default="NGN")

    paystack_plan_code = Column(String(100), nullable=True)

    # Limits
    daily_video_limit    = Column(Integer, default=3)
    max_video_length     = Column(Integer, default=30)
    max_video_resolution = Column(String(20), default="720p")

    # Feature flags
    has_narration              = Column(Boolean, default=False)
    has_custom_music           = Column(Boolean, default=False)
    has_character_consistency  = Column(Boolean, default=False)
    has_batch_scheduling       = Column(Boolean, default=False)
    has_priority_support       = Column(Boolean, default=False)
    has_white_label            = Column(Boolean, default=False)
    features                   = Column(JSON, default=list)

    is_active     = Column(Boolean, default=True)
    is_popular    = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<SubscriptionPlan({self.slug}, ₦{self.price_monthly_ngn}/mo)>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "slug": self.slug,
            "description": self.description,
            "price_monthly_ngn": self.price_monthly_ngn,
            "price_yearly_ngn":  self.price_yearly_ngn,
            "price_monthly_usd": self.price_monthly_usd,
            "price_yearly_usd":  self.price_yearly_usd,
            "currency": self.currency,
            "daily_video_limit":    self.daily_video_limit,
            "max_video_length":     self.max_video_length,
            "max_video_resolution": self.max_video_resolution,
            "has_narration":             self.has_narration,
            "has_custom_music":          self.has_custom_music,
            "has_character_consistency": self.has_character_consistency,
            "has_batch_scheduling":      self.has_batch_scheduling,
            "has_priority_support":      self.has_priority_support,
            "has_white_label":           self.has_white_label,
            "features":    self.features or [],
            "is_popular":  self.is_popular,
        }


# ─── PAYMENT ──────────────────────────────────────────────────────────────────

class Payment(Base):
    __tablename__ = "payments"

    id      = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)

    # FIX 2 — String(50) so plain-string writes from payments.py never fail
    payment_type = Column(String(50), default="subscription", nullable=False)

    # FIX 3 — SQLEnum now has COMPLETED so status comparisons work
    status   = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)

    amount   = Column(Float,       nullable=False)
    currency = Column(String(3),   default="NGN")

    # Paystack fields
    paystack_reference          = Column(String(100), nullable=True, unique=True, index=True)
    paystack_transaction_id     = Column(String(100), nullable=True)
    paystack_authorization_code = Column(String(100), nullable=True)
    customer_email              = Column(String(255), nullable=True)
    customer_code               = Column(String(100), nullable=True)

    description      = Column(Text, nullable=True)
    payment_metadata = Column(JSON, default=dict)   # "metadata" is reserved by SQLAlchemy

    credits_purchased = Column(Integer, nullable=True)

    plan_id                  = Column(String(36), ForeignKey("subscription_plans.id"), nullable=True)
    subscription_start_date  = Column(DateTime, nullable=True)
    subscription_end_date    = Column(DateTime, nullable=True)

    refunded_amount = Column(Float,    default=0)
    refunded_at     = Column(DateTime, nullable=True)

    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="payments")
    plan = relationship("SubscriptionPlan")

    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, ₦{self.amount}, {self.status.value})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":               self.id,
            "payment_type":     self.payment_type,
            "status":           self.status.value,
            "amount":           self.amount,
            "currency":         self.currency,
            "description":      self.description,
            "credits_purchased":self.credits_purchased,
            "plan_id":          self.plan_id,
            "paystack_reference": self.paystack_reference,
            "created_at":   self.created_at.isoformat()   if self.created_at   else None,
            "completed_at": self.completed_at.isoformat()  if self.completed_at else None,
        }


# ─── CREDIT PACKAGE ───────────────────────────────────────────────────────────

class CreditPackage(Base):
    __tablename__ = "credit_packages"

    id          = Column(String(36), primary_key=True, index=True)
    name        = Column(String(50), nullable=False)
    description = Column(Text,       nullable=True)

    credits       = Column(Integer, nullable=False)
    bonus_credits = Column(Integer, default=0)

    price_ngn = Column(Float,      nullable=False)
    price_usd = Column(Float,      nullable=True)
    currency  = Column(String(3),  default="NGN")

    is_popular    = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    is_active     = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<CreditPackage({self.name}, {self.credits}cr, ₦{self.price_ngn})>"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "credits": self.credits, "bonus_credits": self.bonus_credits,
            "total_credits": self.credits + self.bonus_credits,
            "price_ngn": self.price_ngn, "price_usd": self.price_usd,
            "currency": self.currency, "is_popular": self.is_popular,
        }


# ─── SEED DATA (FIX 4) ────────────────────────────────────────────────────────

def seed_default_plans(db: Session) -> None:
    """
    FIX 4 — Insert default subscription plans if none exist.
    Call from main.py lifespan after create_tables().
    """
    import uuid
    if db.query(SubscriptionPlan).count() > 0:
        return

    plans = [
        SubscriptionPlan(
            id=str(uuid.uuid4()), name="Free", slug="free",
            description="Get started with chAs AI Creator",
            price_monthly_ngn=0, price_yearly_ngn=0,
            daily_video_limit=2, max_video_length=30,
            max_video_resolution="720p",
            has_narration=False, has_custom_music=False,
            has_character_consistency=False, has_batch_scheduling=False,
            features=["2 videos/day", "30s max", "720p", "Basic niches"],
            is_active=True, is_popular=False, display_order=0,
        ),
        SubscriptionPlan(
            id=str(uuid.uuid4()), name="Pro", slug="pro",
            description="Grow your content with full AI power",
            price_monthly_ngn=4999, price_yearly_ngn=49990,
            price_monthly_usd=5,    price_yearly_usd=50,
            daily_video_limit=50, max_video_length=300,
            max_video_resolution="1080p",
            has_narration=True, has_custom_music=True,
            has_character_consistency=True, has_batch_scheduling=True,
            has_priority_support=True,
            features=[
                "50 videos/day", "5 min max", "1080p",
                "Narration & voice", "Custom music",
                "Character consistency", "Batch scheduling",
                "Priority support",
            ],
            is_active=True, is_popular=True, display_order=1,
        ),
        SubscriptionPlan(
            id=str(uuid.uuid4()), name="Enterprise", slug="enterprise",
            description="Unlimited power for serious creators",
            price_monthly_ngn=19999, price_yearly_ngn=199990,
            price_monthly_usd=20,    price_yearly_usd=200,
            daily_video_limit=200, max_video_length=600,
            max_video_resolution="4K",
            has_narration=True, has_custom_music=True,
            has_character_consistency=True, has_batch_scheduling=True,
            has_priority_support=True, has_white_label=True,
            features=[
                "200 videos/day", "10 min max", "4K",
                "Everything in Pro", "White-label export",
                "Dedicated support",
            ],
            is_active=True, is_popular=False, display_order=2,
        ),
    ]
    db.add_all(plans)
    db.commit()


def seed_default_packages(db: Session) -> None:
    """
    FIX 4 — Insert default credit packages if none exist.
    """
    import uuid
    if db.query(CreditPackage).count() > 0:
        return

    packages = [
        CreditPackage(
            id=str(uuid.uuid4()), name="Starter Pack",
            description="Perfect for trying out chAs AI Creator",
            credits=10, bonus_credits=0,
            price_ngn=999, is_popular=False, display_order=0,
        ),
        CreditPackage(
            id=str(uuid.uuid4()), name="Creator Pack",
            description="Most popular — great value for creators",
            credits=50, bonus_credits=10,
            price_ngn=3999, is_popular=True, display_order=1,
        ),
        CreditPackage(
            id=str(uuid.uuid4()), name="Pro Pack",
            description="Maximum credits, maximum savings",
            credits=150, bonus_credits=50,
            price_ngn=9999, is_popular=False, display_order=2,
        ),
    ]
    db.add_all(packages)
    db.commit()
