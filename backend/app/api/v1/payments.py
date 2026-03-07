"""Payment and subscription API routes."""

from typing import Optional, List

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


class CreatePaymentIntentRequest(BaseModel):
    package_id: str


class SubscriptionResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str]
    price_monthly: Optional[float]
    price_yearly: Optional[float]
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
    price: float
    currency: str
    is_popular: bool


# Stripe integration helper
import stripe
from app.config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


@router.get("/plans")
async def get_subscription_plans(
    db: Session = Depends(get_db),
):
    """Get available subscription plans."""
    plans = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.is_active == True
    ).order_by(SubscriptionPlan.display_order).all()
    
    return {
        "plans": [SubscriptionResponse(
            id=p.id,
            name=p.name,
            slug=p.slug,
            description=p.description,
            price_monthly=p.price_monthly,
            price_yearly=p.price_yearly,
            currency=p.currency,
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
    """Get available credit packages."""
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
            price=p.price,
            currency=p.currency,
            is_popular=p.is_popular,
        ) for p in packages]
    }


@router.post("/subscribe")
async def create_subscription(
    request: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create subscription."""
    # Get plan
    plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == request.plan_id,
        SubscriptionPlan.is_active == True
    ).first()
    
    if not plan:
        raise NotFoundException("Plan not found")
    
    # Get or create Stripe customer
    try:
        if not current_user.subscription or not current_user.subscription.stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={"user_id": current_user.id},
            )
            stripe_customer_id = customer.id
        else:
            stripe_customer_id = current_user.subscription.stripe_customer_id
        
        # Get price ID
        price_id = plan.stripe_price_id_monthly if request.billing_cycle == "monthly" else plan.stripe_price_id_yearly
        
        if not price_id:
            raise PaymentException("Plan pricing not configured")
        
        # Create subscription
        subscription = stripe.Subscription.create(
            customer=stripe_customer_id,
            items=[{"price": price_id}],
            metadata={"user_id": current_user.id, "plan_id": plan.id},
        )
        
        # Create payment record
        import uuid
        payment = Payment(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            payment_type="subscription",
            status=PaymentStatus.COMPLETED,
            amount=plan.price_monthly if request.billing_cycle == "monthly" else plan.price_yearly,
            currency=plan.currency,
            stripe_subscription_id=subscription.id,
            plan_id=plan.id,
            description=f"{plan.name} subscription ({request.billing_cycle})",
        )
        db.add(payment)
        
        # Update user subscription
        from app.models.user import UserSubscription
        if not current_user.subscription:
            user_sub = UserSubscription(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=subscription.id,
                plan_id=plan.slug,
            )
            db.add(user_sub)
        else:
            current_user.subscription.stripe_subscription_id = subscription.id
            current_user.subscription.plan_id = plan.slug
        
        # Update user tier
        tier_map = {
            "free": SubscriptionTier.FREE,
            "pro": SubscriptionTier.PRO,
            "enterprise": SubscriptionTier.ENTERPRISE,
        }
        current_user.subscription_tier = tier_map.get(plan.slug, SubscriptionTier.FREE)
        
        db.commit()
        
        logger.info(
            "Subscription created",
            user_id=current_user.id,
            plan_id=plan.id,
            subscription_id=subscription.id,
        )
        
        return {
            "message": "Subscription created successfully",
            "subscription_id": subscription.id,
            "status": subscription.status,
        }
        
    except stripe.error.StripeError as e:
        logger.error("Stripe error", error=str(e))
        raise PaymentException(f"Payment failed: {str(e)}")


@router.post("/create-payment-intent")
async def create_payment_intent(
    request: CreatePaymentIntentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create payment intent for credit purchase."""
    # Get package
    package = db.query(CreditPackage).filter(
        CreditPackage.id == request.package_id,
        CreditPackage.is_active == True
    ).first()
    
    if not package:
        raise NotFoundException("Package not found")
    
    try:
        # Create payment intent
        intent = stripe.PaymentIntent.create(
            amount=int(package.price * 100),  # Convert to cents
            currency=package.currency.lower(),
            metadata={
                "user_id": current_user.id,
                "package_id": package.id,
                "credits": package.credits + package.bonus_credits,
            },
        )
        
        # Create pending payment record
        import uuid
        payment = Payment(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            payment_type="credits",
            status=PaymentStatus.PENDING,
            amount=package.price,
            currency=package.currency,
            stripe_payment_intent_id=intent.id,
            credits_purchased=package.credits + package.bonus_credits,
            description=f"{package.credits + package.bonus_credits} credits",
        )
        db.add(payment)
        db.commit()
        
        logger.info(
            "Payment intent created",
            user_id=current_user.id,
            package_id=package.id,
            intent_id=intent.id,
        )
        
        return {
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
        }
        
    except stripe.error.StripeError as e:
        logger.error("Stripe error", error=str(e))
        raise PaymentException(f"Payment failed: {str(e)}")


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle Stripe webhooks."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise PaymentException("Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise PaymentException("Invalid signature")
    
    # Handle events
    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        
        # Update payment status
        payment = db.query(Payment).filter(
            Payment.stripe_payment_intent_id == payment_intent["id"]
        ).first()
        
        if payment:
            payment.status = PaymentStatus.COMPLETED
            payment.completed_at = datetime.utcnow()
            
            # Add credits to user
            user = db.query(User).filter(User.id == payment.user_id).first()
            if user and payment.credits_purchased:
                user.credits += payment.credits_purchased
            
            db.commit()
            
            logger.info(
                "Payment completed",
                payment_id=payment.id,
                user_id=payment.user_id,
                credits=payment.credits_purchased,
            )
    
    elif event["type"] == "invoice.payment_failed":
        subscription = event["data"]["object"]
        
        logger.warning(
            "Subscription payment failed",
            subscription_id=subscription.get("subscription"),
        )
    
    return {"status": "success"}


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
            "type": p.payment_type.value,
            "status": p.status.value,
            "amount": p.amount,
            "currency": p.currency,
            "description": p.description,
            "credits_purchased": p.credits_purchased,
            "created_at": p.created_at.isoformat(),
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        } for p in payments]
    }


@router.post("/cancel-subscription")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel subscription."""
    if not current_user.subscription or not current_user.subscription.stripe_subscription_id:
        raise NotFoundException("No active subscription found")
    
    try:
        # Cancel at period end
        stripe.Subscription.modify(
            current_user.subscription.stripe_subscription_id,
            cancel_at_period_end=True,
        )
        
        current_user.subscription.cancel_at_period_end = True
        db.commit()
        
        logger.info("Subscription cancelled", user_id=current_user.id)
        
        return {"message": "Subscription will be cancelled at the end of the billing period"}
        
    except stripe.error.StripeError as e:
        logger.error("Stripe error", error=str(e))
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
