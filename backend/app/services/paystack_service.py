"""
Paystack Payment Service - Nigeria Payment Gateway
Created by: chAs
"""

import httpx
from typing import Dict, Any, Optional

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PaystackService:
    """Service for handling Paystack payments in Nigeria."""
    
    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.public_key = settings.PAYSTACK_PUBLIC_KEY
        self.base_url = settings.PAYSTACK_BASE_URL
        
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }
    
    async def initialize_transaction(
        self,
        email: str,
        amount: float,  # Amount in Naira (e.g., 5000 for ₦5,000)
        reference: str,
        callback_url: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Initialize a new payment transaction."""
        
        # Convert amount to kobo (Paystack uses kobo, 1 Naira = 100 kobo)
        amount_kobo = int(amount * 100)
        
        payload = {
            "email": email,
            "amount": amount_kobo,
            "reference": reference,
        }
        
        if callback_url:
            payload["callback_url"] = callback_url
        
        if metadata:
            payload["metadata"] = metadata
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/transaction/initialize",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("status"):
                    logger.info(f"Paystack transaction initialized: {reference}")
                    return {
                        "success": True,
                        "authorization_url": result["data"]["authorization_url"],
                        "access_code": result["data"]["access_code"],
                        "reference": result["data"]["reference"],
                    }
                else:
                    logger.error(f"Paystack initialization failed: {result}")
                    return {
                        "success": False,
                        "message": result.get("message", "Initialization failed"),
                    }
                    
        except httpx.HTTPError as e:
            logger.error(f"Paystack HTTP error: {e}")
            return {
                "success": False,
                "message": f"Payment service error: {str(e)}",
            }
    
    async def verify_transaction(self, reference: str) -> Dict[str, Any]:
        """Verify a transaction status."""
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/transaction/verify/{reference}",
                    headers=self.headers,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("status"):
                    data = result["data"]
                    logger.info(f"Paystack transaction verified: {reference}")
                    return {
                        "success": True,
                        "status": data["status"],  # success, failed, abandoned
                        "amount": data["amount"] / 100,  # Convert from kobo to Naira
                        "currency": data["currency"],
                        "reference": data["reference"],
                        "transaction_id": data["id"],
                        "authorization_code": data.get("authorization", {}).get("authorization_code"),
                        "customer_email": data["customer"]["email"],
                        "customer_code": data["customer"]["customer_code"],
                        "paid_at": data.get("paid_at"),
                        "channel": data.get("channel"),  # card, bank, ussd, etc.
                    }
                else:
                    logger.error(f"Paystack verification failed: {result}")
                    return {
                        "success": False,
                        "message": result.get("message", "Verification failed"),
                    }
                    
        except httpx.HTTPError as e:
            logger.error(f"Paystack verification error: {e}")
            return {
                "success": False,
                "message": f"Verification error: {str(e)}",
            }
    
    async def create_subscription_plan(
        self,
        name: str,
        amount: float,
        interval: str,  # daily, weekly, monthly, annually
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a subscription plan on Paystack."""
        
        amount_kobo = int(amount * 100)
        
        payload = {
            "name": name,
            "amount": amount_kobo,
            "interval": interval,
        }
        
        if description:
            payload["description"] = description
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/plan",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("status"):
                    logger.info(f"Paystack plan created: {name}")
                    return {
                        "success": True,
                        "plan_code": result["data"]["plan_code"],
                        "plan_id": result["data"]["id"],
                    }
                else:
                    return {
                        "success": False,
                        "message": result.get("message", "Plan creation failed"),
                    }
                    
        except httpx.HTTPError as e:
            logger.error(f"Paystack plan creation error: {e}")
            return {
                "success": False,
                "message": f"Plan creation error: {str(e)}",
            }
    
    async def create_subscription(
        self,
        customer_email: str,
        plan_code: str,
        authorization_code: Optional[str] = None,
        start_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a subscription for a customer."""
        
        payload = {
            "customer": customer_email,
            "plan": plan_code,
        }
        
        if authorization_code:
            payload["authorization"] = authorization_code
        
        if start_date:
            payload["start_date"] = start_date
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/subscription",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("status"):
                    logger.info(f"Paystack subscription created for {customer_email}")
                    return {
                        "success": True,
                        "subscription_code": result["data"]["subscription_code"],
                        "subscription_id": result["data"]["id"],
                        "status": result["data"]["status"],
                    }
                else:
                    return {
                        "success": False,
                        "message": result.get("message", "Subscription creation failed"),
                    }
                    
        except httpx.HTTPError as e:
            logger.error(f"Paystack subscription error: {e}")
            return {
                "success": False,
                "message": f"Subscription error: {str(e)}",
            }
    
    async def cancel_subscription(self, subscription_code: str) -> Dict[str, Any]:
        """Cancel a subscription."""
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/subscription/disable",
                    headers=self.headers,
                    json={"code": subscription_code},
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("status"):
                    logger.info(f"Paystack subscription cancelled: {subscription_code}")
                    return {"success": True}
                else:
                    return {
                        "success": False,
                        "message": result.get("message", "Cancellation failed"),
                    }
                    
        except httpx.HTTPError as e:
            logger.error(f"Paystack cancellation error: {e}")
            return {
                "success": False,
                "message": f"Cancellation error: {str(e)}",
            }
    
    def generate_reference(self, prefix: str = "chas") -> str:
        """Generate a unique transaction reference."""
        import uuid
        from datetime import datetime
        
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{prefix}_{timestamp}_{unique_id}"
