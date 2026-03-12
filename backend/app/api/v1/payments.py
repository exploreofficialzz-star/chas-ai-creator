"""
Payment and subscription API routes.
FILE: app/api/v1/payments.py

FIXES:
1. CRITICAL — verify_payment() checked result.get("status") but
   paystack_service.verify_transaction() returns {"success": True,
   "status": "success", ...} — not {"status": True, "data": {...}}.
   The old code tried result.get("data") which was always None.
   Fixed to match the actual response shape from paystack_service.py.

2. CRITICAL — webhook handler used dateutil.relativedelta which is not
   in the standard requirements. Added fallback using timedelta so the
   webhook never crashes on import.

3. cancel_subscription() accessed current_user.subscription without
   None check — AttributeError when user has no active subscription.
   Fixed: look up the most recent completed subscription payment instead.

4. get_current_subscription() accessed current_user.daily_video_limit
   and current_user.max_video_length — attributes that don't exist on
   the User model. Fixed with tier lookup dict.

5. Webhook HMAC signature verification added — Paystack signs every
   webhook. Without verification, anyone can fake a payment event.

6. initialize_payment() and create_subscription() both crashed when
   paystack returned success=False (e.g. duplicate reference) — now
   raises PaymentException with the actual error message from Paystack.

7. Added GET /current endpoint guards for None plan gracefully.
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AuthenticationException,
    NotFoundException,
    PaymentException,
)
from app.core.logging import get_logger
from app.core.security import verify_token
from app.db.base import get_db
from app.models.payment import CreditPackage, Payment, PaymentStatus, SubscriptionPlan
from app.models.user import SubscriptionTier, User
from app.services.paystack_service import paystack_service

logger = get_logger(__name__)
router = APIRouter()

_TIER_LIMITS = {
    "free":       {"daily": 2,   "max_duration": 30},
    "basic":      {"daily": 10,  "max_duration": 60},
    "pro":        {"daily": 50,  "max_duration": 300},
    "enterprise": {"daily": 200, "max_duration": 600},
}

_TIER_MAP = {
    "free":       SubscriptionTier.FREE,
    "basic":      SubscriptionTier.BASIC  if hasattr(SubscriptionTier, "BASIC")  else SubscriptionTier.FREE,
    "pro":        SubscriptionTier.PRO    if hasattr(SubscriptionTier, "PRO")    else SubscriptionTier.FREE,
    "enterprise": SubscriptionTier.ENTERPRISE if hasattr(SubscriptionTier, "ENTERPRISE") else SubscriptionTier.FREE,
}


# ─── AUTH DEPENDENCY ──────────────────────────────────────────────────────────

def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationException("Authorization header required")
    token   = authorization.split(" ")[1]
    payload = verify_token(token)
    user    = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise AuthenticationException("User not found")
    return user


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _tier_str(user: User) -> str:
    t = user.subscription_tier
    return t.value if hasattr(t, "value") else str(t)


def _daily_limit(user: User) -> int:
    return _TIER_LIMITS.get(_tier_str(user), _TIER_LIMITS["free"])["daily"]


def _max_duration(user: User) -> int:
    return _TIER_LIMITS.get(_tier_str(user), _TIER_LIMITS["free"])["max_duration"]


def _add_months(dt: datetime, months: int) -> datetime:
    """FIX 2 — replace dateutil.relativedelta with stdlib timedelta."""
    try:
        from dateutil.relativedelta import relativedelta
        return dt + relativedelta(months=months)
    except ImportError:
        return dt + timedelta(days=30 * months)


def _activate_subscription(user: User, plan: SubscriptionPlan, billing_cycle: str) -> None:
    """Apply the subscription tier and expiry to the user."""
    user.subscription_tier = _TIER_MAP.get(plan.slug.lower(), SubscriptionTier.FREE)
    months = 12 if "year" in billing_cycle else 1
    if user.subscription_expires_at and user.subscription_expires_at > datetime.utcnow():
        user.subscription_expires_at = _add_months(user.subscription_expires_at, months)
    else:
        user.subscription_expires_at = _add_months(datetime.utcnow(), months)


# ─── PYDANTIC MODELS ──────────────────────────────────────────────────────────

class CreateSubscriptionRequest(BaseModel):
    plan_id:       str
    billing_cycle: str = "monthly"


class InitializePaymentRequest(BaseModel):
    package_id:   str
    callback_url: Optional[str] = None


class VerifyPaymentRequest(BaseModel):
    reference: str


class SubscriptionResponse(BaseModel):
    id:                        str
    name:                      str
    slug:                      str
    description:               Optional[str]
    price_monthly_ngn:         Optional[float]
    price_yearly_ngn:          Optional[float]
    currency:                  str
    daily_video_limit:         int
    max_video_length:          int
    max_video_resolution:      str
    has_narration:             bool
    has_custom_music:          bool
    has_character_consistency: bool
    has_batch_scheduling:      bool
    has_priority_support:      bool
    has_white_label:           bool
    features:                  List[str]
    is_popular:                bool


class CreditPackageResponse(BaseModel):
    id:            str
    name:          str
    description:   Optional[str]
    credits:       int
    bonus_credits: int
    total_credits: int
    price_ngn:     float
    currency:      str
    is_popular:    bool


# ─── ROUTES ───────────────────────────────────────────────────────────────────

@router.get("/plans")
async def get_subscription_plans(db: Session = Depends(get_db)):
    """Return active subscription plans ordered by display_order."""
    plans = (
        db.query(SubscriptionPlan)
        .filter(SubscriptionPlan.is_active == True)
        .order_by(SubscriptionPlan.display_order)
        .all()
    )
    return {
        "plans": [
            SubscriptionResponse(
                id=p.id, name=p.name, slug=p.slug,
                description=p.description,
                price_monthly_ngn=p.price_monthly_ngn,
                price_yearly_ngn=p.price_yearly_ngn,
                currency="NGN",
                daily_video_limit=p.daily_video_limit,
                max_video_length=p.max_video_length,
                max_video_resolution=getattr(p, "max_video_resolution", "720p"),
                has_narration=getattr(p, "has_narration", False),
                has_custom_music=getattr(p, "has_custom_music", False),
                has_character_consistency=getattr(p, "has_character_consistency", False),
                has_batch_scheduling=getattr(p, "has_batch_scheduling", False),
                has_priority_support=getattr(p, "has_priority_support", False),
                has_white_label=getattr(p, "has_white_label", False),
                features=p.features or [],
                is_popular=getattr(p, "is_popular", False),
            )
            for p in plans
        ]
    }


@router.get("/credit-packages")
async def get_credit_packages(db: Session = Depends(get_db)):
    """Return active credit packages."""
    pkgs = (
        db.query(CreditPackage)
        .filter(CreditPackage.is_active == True)
        .order_by(CreditPackage.display_order)
        .all()
    )
    return {
        "packages": [
            CreditPackageResponse(
                id=p.id, name=p.name, description=p.description,
                credits=p.credits, bonus_credits=p.bonus_credits,
                total_credits=p.credits + p.bonus_credits,
                price_ngn=p.price_ngn, currency="NGN",
                is_popular=getattr(p, "is_popular", False),
            )
            for p in pkgs
        ]
    }


@router.post("/initialize")
async def initialize_payment(
    request: InitializePaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initialize Paystack payment for credit purchase."""
    pkg = db.query(CreditPackage).filter(
        CreditPackage.id == request.package_id,
        CreditPackage.is_active == True,
    ).first()
    if not pkg:
        raise NotFoundException("Credit package not found")

    reference = paystack_service.generate_reference("chas_credits")
    total_credits = pkg.credits + pkg.bonus_credits

    result = await paystack_service.initialize_transaction(
        email=current_user.email,
        amount=pkg.price_ngn,
        reference=reference,
        callback_url=request.callback_url,
        metadata={
            "user_id":    current_user.id,
            "package_id": pkg.id,
            "credits":    total_credits,
            "type":       "credits",
        },
    )

    # FIX 6 — check success flag, not just no exception
    if not result.get("success"):
        raise PaymentException(result.get("message", "Paystack initialization failed"))

    payment = Payment(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        payment_type="credits",
        status=PaymentStatus.PENDING,
        amount=pkg.price_ngn,
        currency="NGN",
        paystack_reference=reference,
        credits_purchased=total_credits,
        description=f"{total_credits} credits",
    )
    db.add(payment)
    db.commit()

    logger.info(f"Payment initialized: {reference} | user={current_user.id}")
    return {
        "authorization_url": result["authorization_url"],
        "reference":         reference,
        "access_code":       result.get("access_code"),
    }


@router.post("/verify")
async def verify_payment(
    request: VerifyPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify Paystack payment and credit the user."""
    result = await paystack_service.verify_transaction(request.reference)

    # FIX 1 — use "success" key, not "status"
    if not result.get("success"):
        raise PaymentException(result.get("message", "Verification failed"))

    if result.get("status") != "success":
        raise PaymentException(f"Payment not successful: {result.get('status')}")

    payment = db.query(Payment).filter(
        Payment.paystack_reference == request.reference,
        Payment.user_id            == current_user.id,
    ).first()

    if not payment:
        raise NotFoundException("Payment record not found")

    if payment.status == PaymentStatus.COMPLETED:
        return {
            "message":      "Payment already processed",
            "credits_added": payment.credits_purchased,
            "total_credits": current_user.credits,
        }

    payment.status = PaymentStatus.COMPLETED
    payment.completed_at = datetime.utcnow()
    payment.paystack_transaction_id = str(result.get("transaction_id", ""))

    if payment.credits_purchased:
        current_user.credits = (current_user.credits or 0) + payment.credits_purchased

    db.commit()
    logger.info(
        f"Credits added: {payment.credits_purchased} → user {current_user.id}"
    )
    return {
        "message":       "Payment successful ✅",
        "credits_added": payment.credits_purchased,
        "total_credits": current_user.credits,
    }


@router.post("/subscribe")
async def create_subscription(
    request: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initialize Paystack subscription payment."""
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == request.plan_id,
        SubscriptionPlan.is_active == True,
    ).first()
    if not plan:
        raise NotFoundException("Plan not found")

    amount = (
        plan.price_monthly_ngn
        if request.billing_cycle == "monthly"
        else plan.price_yearly_ngn
    )
    if not amount:
        raise PaymentException("Plan pricing not configured")

    reference = paystack_service.generate_reference("chas_sub")

    result = await paystack_service.initialize_transaction(
        email=current_user.email,
        amount=amount,
        reference=reference,
        metadata={
            "user_id":       current_user.id,
            "plan_id":       plan.id,
            "billing_cycle": request.billing_cycle,
            "type":          "subscription",
        },
    )

    if not result.get("success"):  # FIX 6
        raise PaymentException(result.get("message", "Paystack initialization failed"))

    payment = Payment(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        payment_type="subscription",
        status=PaymentStatus.PENDING,
        amount=amount,
        currency="NGN",
        paystack_reference=reference,
        plan_id=plan.id,
        description=f"{plan.name} ({request.billing_cycle})",
    )
    db.add(payment)
    db.commit()

    logger.info(f"Subscription initialized: {reference} | plan={plan.slug}")
    return {
        "authorization_url": result["authorization_url"],
        "reference":         reference,
        "access_code":       result.get("access_code"),
        "message":           "Complete payment to activate your subscription",
    }


@router.post("/webhook")
async def paystack_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle Paystack webhook events with HMAC signature verification."""
    payload = await request.body()

    # FIX 5 — verify webhook signature
    from app.config import settings as app_settings
    secret = getattr(app_settings, "PAYSTACK_SECRET_KEY", "")
    if secret:
        signature = request.headers.get("x-paystack-signature", "")
        expected  = hmac.new(
            secret.encode(), payload, hashlib.sha512
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            logger.warning("⚠️  Paystack webhook: invalid signature — rejected")
            return {"status": "invalid_signature"}

    try:
        event      = json.loads(payload)
        event_type = event.get("event", "")
        data       = event.get("data", {})

        logger.info(f"Paystack webhook: {event_type}")

        if event_type == "charge.success":
            reference = data.get("reference", "")
            payment   = db.query(Payment).filter(
                Payment.paystack_reference == reference
            ).first()

            if not payment:
                logger.warning(f"Webhook: no payment record for ref={reference}")
                return {"status": "not_found"}

            if payment.status == PaymentStatus.COMPLETED:
                return {"status": "already_processed"}

            payment.status = PaymentStatus.COMPLETED
            payment.completed_at = datetime.utcnow()
            payment.paystack_transaction_id = str(data.get("id", ""))

            user = db.query(User).filter(User.id == payment.user_id).first()
            if not user:
                logger.error(f"Webhook: user {payment.user_id} not found")
                return {"status": "user_not_found"}

            if payment.payment_type == "credits" and payment.credits_purchased:
                user.credits = (user.credits or 0) + payment.credits_purchased
                logger.info(f"Webhook: +{payment.credits_purchased} credits → {user.id}")

            elif payment.payment_type == "subscription" and payment.plan_id:
                plan = db.query(SubscriptionPlan).filter(
                    SubscriptionPlan.id == payment.plan_id
                ).first()
                if plan:
                    billing = payment.description or "monthly"
                    _activate_subscription(user, plan, billing)
                    logger.info(
                        f"Webhook: subscription activated {plan.slug} → {user.id}"
                    )

            db.commit()

        elif event_type == "subscription.disable":
            logger.info(f"Webhook: subscription disabled — {data}")

        elif event_type == "invoice.payment_failed":
            logger.warning(f"Webhook: invoice payment failed — {data}")

        return {"status": "success"}

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/history")
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payments = (
        db.query(Payment)
        .filter(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .all()
    )
    return {
        "payments": [
            {
                "id":                 p.id,
                "type":               p.payment_type.value if hasattr(p.payment_type, "value") else str(p.payment_type),
                "status":             p.status.value       if hasattr(p.status, "value")       else str(p.status),
                "amount":             p.amount,
                "currency":           p.currency,
                "description":        p.description,
                "credits_purchased":  p.credits_purchased,
                "paystack_reference": p.paystack_reference,
                "created_at":         p.created_at.isoformat()   if p.created_at   else None,
                "completed_at":       p.completed_at.isoformat()  if p.completed_at else None,
            }
            for p in payments
        ]
    }


@router.post("/cancel-subscription")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FIX 3 — Cancel by looking up latest subscription payment."""
    latest_sub = (
        db.query(Payment)
        .filter(
            Payment.user_id      == current_user.id,
            Payment.payment_type == "subscription",
            Payment.status       == PaymentStatus.COMPLETED,
        )
        .order_by(Payment.created_at.desc())
        .first()
    )

    if not latest_sub:
        raise NotFoundException("No active subscription found")

    # Downgrade to free immediately (or you could set cancel_at_period_end)
    current_user.subscription_tier    = SubscriptionTier.FREE
    current_user.subscription_expires_at = datetime.utcnow()
    db.commit()

    logger.info(f"Subscription cancelled: {current_user.id}")
    return {"message": "Subscription cancelled. You've been moved to the free plan."}


@router.get("/current")
async def get_current_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return current subscription details."""
    tier_s = _tier_str(current_user)
    plan   = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.slug == tier_s
    ).first()

    return {
        "tier":                    tier_s,
        "credits":                 current_user.credits or 0,
        "daily_video_limit":       _daily_limit(current_user),    # FIX 4
        "max_video_length":        _max_duration(current_user),   # FIX 4
        "subscription_expires_at": (
            current_user.subscription_expires_at.isoformat()
            if current_user.subscription_expires_at else None
        ),
        "plan": {
            "id":    plan.id,
            "name":  plan.name,
            "slug":  plan.slug,
            "features": plan.features or [],
        } if plan else None,
    }
