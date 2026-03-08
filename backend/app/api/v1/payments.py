"""Payment and subscription API routes - Nigeria Friendly Version (Paystack)."""

from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.exceptions import (
    NotFoundException,
    AuthenticationException,
    PaymentException,
)
from app.core.logging import get_logger
from app.core.security import verify_token
from app.db.base import get_db
from app.models.user import User, SubscriptionTier
from app.models.payment import SubscriptionPlan, Payment, CreditPackage, PaymentStatus
from app.services.paystack_service import paystack_service

logger = get_logger(__name__)
router = APIRouter()


# Dependency to get current user
def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Get current authenticated user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationException("Authorization header required")
    
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    user_id = payload.get("sub")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AuthenticationException("User not found")
    
    return user


# Request/Response Models
class CreateSubscriptionRequest(BaseModel):
    plan_id: str
    billing_cycle: str = "monthly"  # monthly, yearly


class InitializePaymentRequest(BaseModel):
    package_id: str
    callback_url: Optional[str] = None


class VerifyPaymentRequest(BaseModel):
    reference: str


class SubscriptionResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str]
    price_monthly_ngn: Optional[float]
    price_yearly_ngn: Optional[float]
    currency: str
    daily_video_limit: int
    max_video_length: int
    max_video_resolution: str
    has_narration: bool
    has_custom_music: bool
    has_character_consistency: bool
    has_batch_scheduling: bool
    has_priority_support: bool
    has_white_label: bool
    features: List[str]
    is_popular: bool


class CreditPackageResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    credits: int
    bonus_credits: int
    total_credits: int
    price_ngn: float
    currency: str
    is_popular: bool


@router.get("/plans")
async def get_subscription_plans(
    db: Session = Depends(get_db),
):
    """Get available subscription plans with Nigeria pricing."""
    plans = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.is_active == True
    ).order_by(SubscriptionPlan.display_order).all()
    
    return {
        "plans": [SubscriptionResponse(
            id=p.id,
            name=p.name,
            slug=p.slug,
            description=p.description,
            price_monthly_ngn=p.price_monthly_ngn,
            price_yearly_ngn=p.price_yearly_ngn,
            currency="NGN",
            daily_video_limit=p.daily_video_limit,
            max_video_length=p.max_video_length,
            max_video_resolution=p.max_video_resolution,
            has_narration=p.has_narration,
            has_custom_music=p.has_custom_music,
            has_character_consistency=p.has_character_consistency,
            has_batch_scheduling=p.has_batch_scheduling,
            has_priority_support=p.has_priority_support,
            has_white_label=p.has_white_label,
            features=p.features or [],
            is_popular=p.is_popular,
        ) for p in plans]
    }


@router.get("/credit-packages")
async def get_credit_packages(
    db: Session = Depends(get_db),
):
    """Get available credit packages with Nigeria pricing."""
    packages = db.query(CreditPackage).filter(
        CreditPackage.is_active == True
    ).order_by(CreditPackage.display_order).all()
    
    return {
        "packages": [CreditPackageResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            credits=p.credits,
            bonus_credits=p.bonus_credits,
            total_credits=p.credits + p.bonus_credits,
            price_ngn=p.price_ngn,
            currency="NGN",
            is_popular=p.is_popular,
        ) for p in packages]
    }


@router.post("/initialize")
async def initialize_payment(
    request: InitializePaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initialize Paystack payment for credit purchase."""
    # Get package
    package = db.query(CreditPackage).filter(
        CreditPackage.id == request.package_id,
        CreditPackage.is_active == True
    ).first()
    
    if not package:
        raise NotFoundException("Package not found")
    
    try:
        # Generate unique reference
        import uuid
        reference = f"chas_{current_user.id}_{package.id}_{uuid.uuid4().hex[:8]}"
        
        # Initialize Paystack transaction
        amount_ngn = package.price_ngn
        
        result = await paystack_service.initialize_transaction(
            email=current_user.email,
            amount=amount_ngn,
            reference=reference,
            callback_url=request.callback_url,
            metadata={
                "user_id": current_user.id,
                "package_id": package.id,
                "credits": package.credits + package.bonus_credits,
            }
        )
        
        # Create pending payment record
        payment = Payment(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            payment_type="credits",
            status=PaymentStatus.PENDING,
            amount=amount_ngn,
            currency="NGN",
            paystack_reference=reference,
            credits_purchased=package.credits + package.bonus_credits,
            description=f"{package.credits + package.bonus_credits} credits",
        )
        db.add(payment)
        db.commit()
        
        logger.info(
            "Payment initialized",
            user_id=current_user.id,
            package_id=package.id,
            reference=reference,
        )
        
        return {
            "authorization_url": result.get("authorization_url"),
            "reference": reference,
            "access_code": result.get("access_code"),
        }
        
    except Exception as e:
        logger.error("Paystack initialization error", error=str(e))
        raise PaymentException(f"Payment initialization failed: {str(e)}")


@router.post("/verify")
async def verify_payment(
    request: VerifyPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify Paystack payment and add credits."""
    try:
        # Verify with Paystack
        result = await paystack_service.verify_transaction(request.reference)
        
        if not result.get("status"):
            raise PaymentException("Payment verification failed")
        
        payment_data = result.get("data", {})
        
        if payment_data.get("status") != "success":
            raise PaymentException(f"Payment status: {payment_data.get('status')}")
        
        # Find payment record
        payment = db.query(Payment).filter(
            Payment.paystack_reference == request.reference,
            Payment.user_id == current_user.id,
        ).first()
        
        if not payment:
            raise NotFoundException("Payment record not found")
        
        if payment.status == PaymentStatus.COMPLETED:
            return {
                "message": "Payment already processed",
                "credits_added": payment.credits_purchased,
            }
        
        # Update payment status
        payment.status = PaymentStatus.COMPLETED
        payment.completed_at = datetime.utcnow()
        payment.paystack_transaction_id = str(payment_data.get("id"))
        
        # Add credits to user
        if payment.credits_purchased:
            current_user.credits += payment.credits_purchased
        
        db.commit()
        
        logger.info(
            "Payment verified and credits added",
            payment_id=payment.id,
            user_id=current_user.id,
            credits=payment.credits_purchased,
        )
        
        return {
            "message": "Payment successful",
            "credits_added": payment.credits_purchased,
            "total_credits": current_user.credits,
        }
        
    except PaymentException:
        raise
    except Exception as e:
        logger.error("Payment verification error", error=str(e))
        raise PaymentException(f"Payment verification failed: {str(e)}")


@router.post("/subscribe")
async def create_subscription(
    request: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create subscription using Paystack."""
    # Get plan
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == request.plan_id,
        SubscriptionPlan.is_active == True
    ).first()
    
    if not plan:
        raise NotFoundException("Plan not found")
    
    try:
        # Get price in Naira
        amount_ngn = plan.price_monthly_ngn if request.billing_cycle == "monthly" else plan.price_yearly_ngn
        
        if not amount_ngn:
            raise PaymentException("Plan pricing not configured")
        
        # Generate reference
        import uuid
        reference = f"chas_sub_{current_user.id}_{plan.id}_{uuid.uuid4().hex[:8]}"
        
        # Initialize transaction
        result = await paystack_service.initialize_transaction(
            email=current_user.email,
            amount=amount_ngn,
            reference=reference,
            metadata={
                "user_id": current_user.id,
                "plan_id": plan.id,
                "billing_cycle": request.billing_cycle,
                "type": "subscription",
            }
        )
        
        # Create payment record
        payment = Payment(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            payment_type="subscription",
            status=PaymentStatus.PENDING,
            amount=amount_ngn,
            currency="NGN",
            paystack_reference=reference,
            plan_id=plan.id,
            description=f"{plan.name} subscription ({request.billing_cycle})",
        )
        db.add(payment)
        db.commit()
        
        logger.info(
            "Subscription payment initialized",
            user_id=current_user.id,
            plan_id=plan.id,
            reference=reference,
        )
        
        return {
            "authorization_url": result.get("authorization_url"),
            "reference": reference,
            "access_code": result.get("access_code"),
            "message": "Please complete payment to activate subscription",
        }
        
    except Exception as e:
        logger.error("Subscription creation error", error=str(e))
        raise PaymentException(f"Subscription creation failed: {str(e)}")


@router.post("/webhook")
async def paystack_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle Paystack webhooks."""
    payload = await request.body()
    
    try:
        import json
        event = json.loads(payload)
        
        event_type = event.get("event")
        data = event.get("data", {})
        
        logger.info("Paystack webhook received", event=event_type)
        
        if event_type == "charge.success":
            reference = data.get("reference")
            
            # Find payment
            payment = db.query(Payment).filter(
                Payment.paystack_reference == reference
            ).first()
            
            if payment and payment.status != PaymentStatus.COMPLETED:
                payment.status = PaymentStatus.COMPLETED
                payment.completed_at = datetime.utcnow()
                payment.paystack_transaction_id = str(data.get("id"))
                
                # Add credits if credit purchase
                if payment.credits_purchased:
                    user = db.query(User).filter(User.id == payment.user_id).first()
                    if user:
                        user.credits += payment.credits_purchased
                
                # Update subscription if subscription purchase
                if payment.payment_type == "subscription" and payment.plan_id:
                    user = db.query(User).filter(User.id == payment.user_id).first()
                    if user:
                        tier_map = {
                            "free": SubscriptionTier.FREE,
                            "pro": SubscriptionTier.PRO,
                            "enterprise": SubscriptionTier.ENTERPRISE,
                        }
                        plan = db.query(SubscriptionPlan).filter(
                            SubscriptionPlan.id == payment.plan_id
                        ).first()
                        if plan:
                            user.subscription_tier = tier_map.get(plan.slug, SubscriptionTier.FREE)
                            user.subscription_expires_at = datetime.utcnow()
                            # Add 30 days or 365 days based on billing cycle
                            from dateutil.relativedelta import relativedelta
                            if "year" in payment.description.lower():
                                user.subscription_expires_at += relativedelta(years=1)
                            else:
                                user.subscription_expires_at += relativedelta(months=1)
                
                db.commit()
                
                logger.info(
                    "Payment completed via webhook",
                    payment_id=payment.id,
                    reference=reference,
                )
        
        elif event_type == "subscription.disable":
            # Handle subscription cancellation
            logger.info("Subscription disabled", data=data)
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error("Webhook processing error", error=str(e))
        return {"status": "error", "message": str(e)}


@router.get("/history")
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's payment history."""
    payments = db.query(Payment).filter(
        Payment.user_id == current_user.id
    ).order_by(Payment.created_at.desc()).all()
    
    return {
        "payments": [{
            "id": p.id,
            "type": p.payment_type.value if hasattr(p.payment_type, 'value') else str(p.payment_type),
            "status": p.status.value if hasattr(p.status, 'value') else str(p.status),
            "amount": p.amount,
            "currency": p.currency,
            "description": p.description,
            "credits_purchased": p.credits_purchased,
            "paystack_reference": p.paystack_reference,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        } for p in payments]
    }


@router.post("/cancel-subscription")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel subscription."""
    if not current_user.subscription:
        raise NotFoundException("No active subscription found")
    
    try:
        # For Paystack, we mark for cancellation at period end
        current_user.subscription.cancel_at_period_end = True
        db.commit()
        
        logger.info("Subscription marked for cancellation", user_id=current_user.id)
        
        return {"message": "Subscription will be cancelled at the end of the billing period"}
        
    except Exception as e:
        logger.error("Cancel subscription error", error=str(e))
        raise PaymentException(f"Failed to cancel subscription: {str(e)}")


@router.get("/current")
async def get_current_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current subscription details."""
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.slug == current_user.subscription_tier.value
    ).first()
    
    return {
        "tier": current_user.subscription_tier.value,
        "credits": current_user.credits,
        "daily_video_limit": current_user.daily_video_limit,
        "max_video_length": current_user.max_video_length,
        "subscription_expires_at": current_user.subscription_expires_at.isoformat() 
            if current_user.subscription_expires_at else None,
        "cancel_at_period_end": current_user.subscription.cancel_at_period_end 
            if current_user.subscription else False,
        "plan": plan.to_dict() if plan else None,
    }
