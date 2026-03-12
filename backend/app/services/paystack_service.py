"""
Paystack Payment Service.
FILE: app/services/paystack_service.py

FIXES:
1. CRITICAL — verify_transaction() returned a flat dict with
   "status", "amount", "reference", etc. But payments.py called
   result.get("data") which was always None, then checked
   payment_data.get("status") on that None → always failed.
   Fixed: verify_transaction() now returns the same flat shape that
   payments.py expects, documented clearly.

2. initialize_transaction() swallowed Paystack-level errors
   (result["status"] == False) and still returned without raising.
   Caller couldn't distinguish success from Paystack-level error.
   Fixed: "success" key is always present in return dict.

3. httpx.HTTPError doesn't catch all httpx exceptions — httpx raises
   httpx.RequestError (network issues) separately from HTTPStatusError
   (bad HTTP responses). Fixed: catch both explicitly.

4. All methods reused the same httpx.AsyncClient instance in headers
   but created a new client per call — correct, but the Authorization
   header was set on self.headers at init time when secret_key may not
   be available yet (env vars loaded after __init__). Fixed: build
   headers lazily inside each method call.

5. Missing get_banks() method — used in the "pay with bank" flow when
   users want to pay via bank transfer instead of card.

6. Missing charge_authorization() — needed for recurring subscription
   renewals without user re-entering card details.
"""

import hashlib
import hmac
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

PAYSTACK_BASE = "https://api.paystack.co"


class PaystackService:
    """Async Paystack payment gateway service for Nigeria."""

    def _headers(self) -> Dict[str, str]:
        """FIX 4 — build headers lazily so secret_key is always fresh."""
        return {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type":  "application/json",
        }

    def _base(self) -> str:
        return getattr(settings, "PAYSTACK_BASE_URL", PAYSTACK_BASE)

    # ─── TRANSACTIONS ─────────────────────────────────────────────────────────

    async def initialize_transaction(
        self,
        email: str,
        amount: float,           # Naira — converted to kobo here
        reference: str,
        callback_url: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Initialize a Paystack transaction.
        Returns: {"success": bool, "authorization_url": str, "access_code": str,
                  "reference": str, "message": str (on failure)}
        """
        payload: Dict[str, Any] = {
            "email":     email,
            "amount":    int(amount * 100),   # kobo
            "reference": reference,
            "currency":  "NGN",
        }
        if callback_url:
            payload["callback_url"] = callback_url
        if metadata:
            payload["metadata"] = metadata

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base()}/transaction/initialize",
                    headers=self._headers(),
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()

                if result.get("status"):
                    data = result["data"]
                    logger.info(f"Paystack tx initialized: {reference}")
                    return {
                        "success":           True,
                        "authorization_url": data["authorization_url"],
                        "access_code":       data["access_code"],
                        "reference":         data["reference"],
                    }
                else:
                    msg = result.get("message", "Paystack: initialization failed")
                    logger.error(f"Paystack init failed: {msg}")
                    return {"success": False, "message": msg}

        except httpx.HTTPStatusError as e:
            msg = f"Paystack HTTP {e.response.status_code}: {e.response.text[:200]}"
            logger.error(msg)
            return {"success": False, "message": msg}
        except httpx.RequestError as e:          # FIX 3 — network errors
            msg = f"Paystack network error: {e}"
            logger.error(msg)
            return {"success": False, "message": msg}

    async def verify_transaction(self, reference: str) -> Dict[str, Any]:
        """
        Verify a transaction by reference.

        FIX 1 — Returns a FLAT dict (no nested "data" key) so payments.py
        can do result.get("status"), result.get("amount") directly:

        {"success": bool, "status": "success"|"failed"|"abandoned",
         "amount": float (Naira), "currency": str, "reference": str,
         "transaction_id": int, "authorization_code": str,
         "customer_email": str, "channel": str, "paid_at": str,
         "message": str (on failure)}
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base()}/transaction/verify/{reference}",
                    headers=self._headers(),
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()

                if result.get("status"):
                    d = result["data"]
                    logger.info(f"Paystack verified: {reference} → {d['status']}")
                    return {
                        "success":            True,
                        "status":             d["status"],
                        "amount":             d["amount"] / 100,  # kobo → Naira
                        "currency":           d.get("currency", "NGN"),
                        "reference":          d["reference"],
                        "transaction_id":     d["id"],
                        "authorization_code": d.get("authorization", {}).get("authorization_code"),
                        "customer_email":     d["customer"]["email"],
                        "customer_code":      d["customer"].get("customer_code", ""),
                        "paid_at":            d.get("paid_at"),
                        "channel":            d.get("channel"),
                    }
                else:
                    msg = result.get("message", "Paystack: verification failed")
                    logger.error(f"Paystack verify failed: {msg}")
                    return {"success": False, "message": msg}

        except httpx.HTTPStatusError as e:
            msg = f"Paystack HTTP {e.response.status_code}: {e.response.text[:200]}"
            logger.error(msg)
            return {"success": False, "message": msg}
        except httpx.RequestError as e:
            msg = f"Paystack network error: {e}"
            logger.error(msg)
            return {"success": False, "message": msg}

    # FIX 6 — recurring charge without user re-entering card
    async def charge_authorization(
        self,
        email: str,
        amount: float,
        authorization_code: str,
        reference: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Charge a previously saved card authorization (subscription renewals)."""
        if not reference:
            reference = self.generate_reference("chas_renew")

        payload: Dict[str, Any] = {
            "email":         email,
            "amount":        int(amount * 100),
            "authorization_code": authorization_code,
            "reference":     reference,
            "currency":      "NGN",
        }
        if metadata:
            payload["metadata"] = metadata

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base()}/transaction/charge_authorization",
                    headers=self._headers(),
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()

                if result.get("status"):
                    d = result["data"]
                    return {
                        "success":   True,
                        "status":    d["status"],
                        "reference": d["reference"],
                        "amount":    d["amount"] / 100,
                    }
                else:
                    return {"success": False, "message": result.get("message", "Charge failed")}

        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            return {"success": False, "message": str(e)}

    # ─── PLANS ────────────────────────────────────────────────────────────────

    async def create_plan(
        self,
        name: str,
        amount: float,
        interval: str,           # monthly | annually | weekly
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a recurring billing plan on Paystack."""
        payload: Dict[str, Any] = {
            "name":     name,
            "amount":   int(amount * 100),
            "interval": interval,
        }
        if description:
            payload["description"] = description

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base()}/plan",
                    headers=self._headers(),
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()

                if result.get("status"):
                    d = result["data"]
                    return {"success": True, "plan_code": d["plan_code"], "plan_id": d["id"]}
                return {"success": False, "message": result.get("message", "Plan creation failed")}

        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            return {"success": False, "message": str(e)}

    # ─── SUBSCRIPTIONS ────────────────────────────────────────────────────────

    async def create_subscription(
        self,
        customer_email: str,
        plan_code: str,
        authorization_code: Optional[str] = None,
        start_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "customer": customer_email,
            "plan":     plan_code,
        }
        if authorization_code:
            payload["authorization"] = authorization_code
        if start_date:
            payload["start_date"] = start_date

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base()}/subscription",
                    headers=self._headers(),
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()

                if result.get("status"):
                    d = result["data"]
                    return {
                        "success":           True,
                        "subscription_code": d["subscription_code"],
                        "subscription_id":   d["id"],
                        "status":            d["status"],
                    }
                return {"success": False, "message": result.get("message", "Subscription failed")}

        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            return {"success": False, "message": str(e)}

    async def cancel_subscription(self, subscription_code: str, token: str) -> Dict[str, Any]:
        """Disable (cancel) a Paystack subscription."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base()}/subscription/disable",
                    headers=self._headers(),
                    json={"code": subscription_code, "token": token},
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()

                if result.get("status"):
                    return {"success": True}
                return {"success": False, "message": result.get("message", "Cancel failed")}

        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            return {"success": False, "message": str(e)}

    # ─── BANKS (FIX 5) ────────────────────────────────────────────────────────

    async def get_banks(self, country: str = "nigeria") -> Dict[str, Any]:
        """
        FIX 5 — Get list of Nigerian banks for bank transfer payment option.
        Used in the pay-with-bank flow on the payment screen.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base()}/bank",
                    headers=self._headers(),
                    params={"country": country, "per_page": "100"},
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()

                if result.get("status"):
                    return {
                        "success": True,
                        "banks":   [
                            {"id": b["id"], "name": b["name"], "code": b["code"]}
                            for b in result.get("data", [])
                        ],
                    }
                return {"success": False, "banks": [], "message": result.get("message")}

        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.error(f"get_banks error: {e}")
            return {"success": False, "banks": [], "message": str(e)}

    # ─── REFUNDS ──────────────────────────────────────────────────────────────

    async def refund_transaction(
        self,
        transaction_id: str,
        amount: Optional[float] = None,   # None = full refund
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"transaction": transaction_id}
        if amount is not None:
            payload["amount"] = int(amount * 100)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base()}/refund",
                    headers=self._headers(),
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()

                if result.get("status"):
                    return {"success": True, "data": result["data"]}
                return {"success": False, "message": result.get("message", "Refund failed")}

        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            return {"success": False, "message": str(e)}

    # ─── UTILITIES ────────────────────────────────────────────────────────────

    def generate_reference(self, prefix: str = "chas") -> str:
        """Generate a unique Paystack transaction reference."""
        ts  = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        uid = str(uuid.uuid4())[:8]
        return f"{prefix}_{ts}_{uid}"

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify Paystack webhook HMAC-SHA512 signature.
        Call this in the webhook endpoint before processing.
        """
        secret = getattr(settings, "PAYSTACK_SECRET_KEY", "")
        if not secret:
            return False
        expected = hmac.new(secret.encode(), payload, hashlib.sha512).hexdigest()
        return hmac.compare_digest(expected, signature)


# Singleton — imported by payments.py
paystack_service = PaystackService()
