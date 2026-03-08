"""
Payment and subscription models for monetization - Paystack (Nigeria)
Created by: chAs
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    Float,
    JSON,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class PaymentStatus(str, Enum):
    """Payment status options."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    ABANDONED = "abandoned"
    REFUNDED = "refunded"


class PaymentType(str, Enum):
    """Payment type options."""
    SUBSCRIPTION = "subscription"
    CREDITS = "credits"
    ONE_TIME = "one_time"


class SubscriptionPlan(Base):
    """Available subscription plans - Nigeria Friendly."""
    
    __tablename__ = "subscription_plans"
    
    id = Column(String(36), primary_key=True, index=True)
    
    # Plan Details
    name = Column(String(50), nullable=False)  # Free, Pro, Enterprise
    slug = Column(String(50), unique=True, nullable=False)  # free, pro, enterprise
    description = Column(Text, nullable=True)
    
    # Pricing in Naira (₦) - Nigeria
    price_monthly_ngn = Column(Float, nullable=True)  # Nigerian Naira
    price_yearly_ngn = Column(Float, nullable=True)
    
    # Pricing in USD (for international)
    price_monthly_usd = Column(Float, nullable=True)
    price_yearly_usd = Column(Float, nullable=True)
    
    currency = Column(String(3), default="NGN")  # Default to Naira
    
    # Paystack Plan Code
    paystack_plan_code = Column(String(100), nullable=True)
    
    # Features
    daily_video_limit = Column(Integer, default=3)
    max_video_length = Column(Integer, default=30)
    max_video_resolution = Column(String(20), default="720p")
    
    # Feature Flags
    has_narration = Column(Boolean, default=False)
    has_custom_music = Column(Boolean, default=False)
    has_character_consistency = Column(Boolean, default=False)
    has_batch_scheduling = Column(Boolean, default=False)
    has_priority_support = Column(Boolean, default=False)
    has_white_label = Column(Boolean, default=False)
    
    # Additional Features
    features = Column(JSON, default=list)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_popular = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<SubscriptionPlan(name={self.name}, price={self.price_monthly_ngn})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "price_monthly_ngn": self.price_monthly_ngn,
            "price_yearly_ngn": self.price_yearly_ngn,
            "price_monthly_usd": self.price_monthly_usd,
            "price_yearly_usd": self.price_yearly_usd,
            "currency": self.currency,
            "daily_video_limit": self.daily_video_limit,
            "max_video_length": self.max_video_length,
            "max_video_resolution": self.max_video_resolution,
            "has_narration": self.has_narration,
            "has_custom_music": self.has_custom_music,
            "has_character_consistency": self.has_character_consistency,
            "has_batch_scheduling": self.has_batch_scheduling,
            "has_priority_support": self.has_priority_support,
            "has_white_label": self.has_white_label,
            "features": self.features,
            "is_popular": self.is_popular,
        }


class Payment(Base):
    """Payment transactions - Paystack Integration."""
    
    __tablename__ = "payments"
    
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Payment Details
    payment_type = Column(SQLEnum(PaymentType), default=PaymentType.SUBSCRIPTION)
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)
    
    # Amount
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="NGN")  # Nigerian Naira
    
    # Paystack
    paystack_reference = Column(String(100), nullable=True, unique=True)
    paystack_transaction_id = Column(String(100), nullable=True)
    paystack_authorization_code = Column(String(100), nullable=True)
    
    # Customer Info (for Paystack)
    customer_email = Column(String(255), nullable=True)
    customer_code = Column(String(100), nullable=True)
    
    # Description
    description = Column(Text, nullable=True)
    metadata = Column(JSON, default=dict)
    
    # Credits (for credit purchases)
    credits_purchased = Column(Integer, nullable=True)
    
    # Subscription Details
    plan_id = Column(String(36), ForeignKey("subscription_plans.id"), nullable=True)
    subscription_start_date = Column(DateTime, nullable=True)
    subscription_end_date = Column(DateTime, nullable=True)
    
    # Refund
    refunded_amount = Column(Float, default=0)
    refunded_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="payments")
    plan = relationship("SubscriptionPlan")
    
    def __repr__(self) -> str:
        return f"<Payment(id={self.id}, amount={self.amount}, status={self.status})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert payment to dictionary."""
        return {
            "id": self.id,
            "payment_type": self.payment_type.value,
            "status": self.status.value,
            "amount": self.amount,
            "currency": self.currency,
            "description": self.description,
            "credits_purchased": self.credits_purchased,
            "plan_id": self.plan_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class CreditPackage(Base):
    """Credit packages for purchase - Nigeria Friendly."""
    
    __tablename__ = "credit_packages"
    
    id = Column(String(36), primary_key=True, index=True)
    
    # Package Details
    name = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    
    # Credits
    credits = Column(Integer, nullable=False)
    bonus_credits = Column(Integer, default=0)
    
    # Pricing in Naira
    price_ngn = Column(Float, nullable=False)
    price_usd = Column(Float, nullable=True)
    currency = Column(String(3), default="NGN")
    
    # Display
    is_popular = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<CreditPackage(name={self.name}, credits={self.credits}, price={self.price_ngn})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert package to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "credits": self.credits,
            "bonus_credits": self.bonus_credits,
            "total_credits": self.credits + self.bonus_credits,
            "price_ngn": self.price_ngn,
            "price_usd": self.price_usd,
            "currency": self.currency,
            "is_popular": self.is_popular,
    }
