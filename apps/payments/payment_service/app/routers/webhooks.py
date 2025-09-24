from fastapi import APIRouter, Request, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
import os
import logging
import stripe
import json
import httpx
import asyncio
from app.config import settings
from datetime import datetime

# Configure logger
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/webhooks")

# Stripe API key and webhook secret
STRIPE_API_KEY = settings.STRIPE_API_KEY
STRIPE_WEBHOOK_SECRET = settings.STRIPE_WEBHOOK_SECRET

# Initialize Stripe
stripe.api_key = STRIPE_API_KEY

class WebhookResponse(BaseModel):
    status: str
    message: str

@router.post("/stripe", response_model=WebhookResponse)
async def stripe_webhook(request: Request):
    print("🔥 WEBHOOK HANDLER CALLED")
    logger.info("stripe_webhook called")
    try:
        # Get the raw request body
        body = await request.body()
        body_str = body.decode("utf-8")
        logger.info(f"[DEBUG] Raw body type: {type(body)}")
        logger.info(f"[DEBUG] Raw body length: {len(body)}")
        logger.info(f"[DEBUG] Body string length: {len(body_str)}")
        logger.info(f"[DEBUG] Raw Stripe webhook body (first 500 chars): {body_str[:500]}")
        print(f"🔥 WEBHOOK DEBUG: Headers: {dict(request.headers)}")
        print(f"🔥 WEBHOOK DEBUG: Body (first 500 chars): {body_str[:500]}")

        # Get the Stripe signature from headers
        sig_header = request.headers.get("stripe-signature")
        logger.info(f"[DEBUG] Stripe-Signature header: {sig_header}")
        logger.info(f"[DEBUG] Webhook secret configured: {bool(STRIPE_WEBHOOK_SECRET)}")
        if STRIPE_WEBHOOK_SECRET:
            logger.info(f"[DEBUG] Secret starts with whsec_: {STRIPE_WEBHOOK_SECRET.startswith('whsec_')}")
            logger.info(f"[DEBUG] Secret length: {len(STRIPE_WEBHOOK_SECRET)}")
            logger.info(f"[DEBUG] Secret preview: {STRIPE_WEBHOOK_SECRET[:15]}...")
        else:
            logger.error("[DEBUG] STRIPE_WEBHOOK_SECRET is None or empty!")

        if not sig_header:
            logger.warning("Missing Stripe signature header")
            print("🔥 WEBHOOK DEBUG: Missing signature header")
            return {"detail": "Missing Stripe signature header"}

        if not STRIPE_WEBHOOK_SECRET:
            logger.warning("Stripe webhook secret not configured")
            print("🔥 WEBHOOK DEBUG: Missing webhook secret")
            return WebhookResponse(
                status="error",
                message="Stripe webhook secret not configured"
            )

        # Verify the webhook signature
        try:
            logger.info("[DEBUG] About to verify signature...")
            print("🔥 WEBHOOK DEBUG: About to verify signature...")
            event = stripe.Webhook.construct_event(
                body,  # Use raw bytes for signature verification
                sig_header,
                STRIPE_WEBHOOK_SECRET
            )
            logger.info("✅ [DEBUG] Signature verification successful!")
            print("🔥 WEBHOOK DEBUG: ✅ Signature verification SUCCESS!")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"❌ [DEBUG] Signature verification failed: {str(e)}")
            logger.error(f"[DEBUG] Error type: {type(e)}")
            logger.error(f"[DEBUG] Using secret: {STRIPE_WEBHOOK_SECRET[:15]}...")
            logger.error(f"[DEBUG] Using signature: {sig_header}")
            logger.error(f"[DEBUG] Body hash (for debugging): {hash(body)}")
            print(f"🔥 WEBHOOK DEBUG: ❌ Signature verification FAILED: {str(e)}")
            return {"status": "error", "message": f"Invalid signature: {str(e)}"}
        except Exception as e:
            logger.error(f"❌ [DEBUG] Unexpected error during signature verification: {str(e)}")
            logger.error(f"[DEBUG] Error type: {type(e)}")
            print(f"🔥 WEBHOOK DEBUG: ❌ Unexpected error: {str(e)}")
            return {"status": "error", "message": f"Webhook processing error: {str(e)}"}

        # Process the event
        event_type = event["type"]
        event_object = event["data"]["object"]
        logger.info(f"[DEBUG] Event type: {event_type}")
        logger.info(f"[DEBUG] Event object: {event_object}")
        logger.info(f"Received Stripe webhook event: {event_type}")
        print(f"🔥 WEBHOOK DEBUG: Routing event type: {event_type}")
        print(f"🔥 WEBHOOK DEBUG: Event object: {json.dumps(event_object, default=str)[:500]}")

        # Handle specific event types
        if event_type == "checkout.session.completed":
            await handle_checkout_session_completed(event_object)
        elif event_type == "subscription.created":
            await handle_subscription_created(event_object)
        elif event_type == "subscription.updated":
            await handle_subscription_updated(event_object)
        elif event_type == "subscription.deleted":
            await handle_subscription_deleted(event_object)
        elif event_type == "invoice.payment_succeeded":
            await handle_invoice_payment_succeeded(event_object)
        elif event_type == "invoice.payment_failed":
            await handle_invoice_payment_failed(event_object)
        else:
            logger.info(f"Unhandled event type: {event_type}")
            print(f"🔥 WEBHOOK DEBUG: Unhandled event type: {event_type}")

        print(f"🔥 WEBHOOK DEBUG: Handler completed for event type: {event_type}")
        return WebhookResponse(
            status="success",
            message=f"Processed webhook event: {event_type}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in webhook handler: {str(e)}")
        print(f"🔥 WEBHOOK DEBUG: Unexpected error in handler: {str(e)}")
        return {"status": "error", "message": f"Internal server error: {str(e)}"}

@router.get("/test")
async def test_webhook_routing():
    logger.info("✅ Webhook routing test endpoint called!")
    return {"status": "webhook routing works", "service": "payments"}

async def handle_checkout_session_completed(session):
    logger.info(f"[DEBUG] Entered handle_checkout_session_completed for session: {session}")
    """Handle checkout.session.completed event"""
    logger.info(f"Processing checkout.session.completed: {session.id}")
    
    try:
        # If this was a subscription checkout, update user's subscription status
        if session.mode == "subscription":
            # Get the customer and subscription IDs
            customer_id = session.customer
            subscription_id = session.subscription
            
            if not subscription_id:
                logger.warning(f"No subscription ID in session {session.id}")
                return
            
            # Get user ID from metadata
            user_id = session.metadata.get("user_id")
            if not user_id:
                # Try to get it from the customer
                customer = stripe.Customer.retrieve(customer_id)
                user_id = customer.metadata.get("user_id")
            
            if not user_id:
                logger.warning(f"No user ID found for subscription {subscription_id}")
                return
            
            # Get the subscription
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            # Update subscription metadata if needed
            if "user_id" not in subscription.metadata:
                stripe.Subscription.modify(
                    subscription_id,
                    metadata={"user_id": user_id}
                )
            
            # Notify the user service (or any other service) about the subscription change
            await notify_subscription_update(user_id, subscription)
        # If this was a top-up (one-off payment)
        elif session.mode == "payment":
            # Get user ID and plan_id from metadata
            user_id = session.metadata.get("user_id")
            plan_id = session.metadata.get("plan_id")
            logger.info(f"[TOPUP] Detected payment session: user_id={user_id}, plan_id={plan_id}")
            # Check if plan_id matches the top-up price ID
            topup_price_id = os.getenv("TOPUP_PLAN_PRICE_ID")
            if plan_id == topup_price_id:
                logger.info(f"[TOPUP] Top-up payment detected for user {user_id}, calling user service to add credits.")
                # Call user service to add top-up credits
                user_service_url = os.getenv("USER_SERVICE_URL", "http://candidate5-9cbd5b79.railway.internal:8080")
                add_topup_url = f"{user_service_url}/api/user/topup/add"
                payload = {"user_id": user_id}
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.post(add_topup_url, json=payload)
                        logger.info(f"[TOPUP] User service response: {response.status_code} {response.text}")
                        print(f"🔥 TOPUP: User service response: {response.status_code} {response.text}")
                        if response.status_code != 200:
                            logger.warning(f"[TOPUP] Failed to add top-up credits: {response.status_code} {response.text}")
                            print(f"🔥 TOPUP: Failed to add top-up credits: {response.status_code} {response.text}")
                except Exception as e:
                    logger.warning(f"[TOPUP] Error adding top-up credits: {str(e)}")
                    print(f"🔥 TOPUP: Error adding top-up credits: {str(e)}")
            else:
                logger.info(f"[TOPUP] Payment session is not a top-up (plan_id={plan_id}, expected={topup_price_id})")
    
    except Exception as e:
        logger.error(f"Error handling checkout.session.completed: {str(e)}")
    logger.info(f"[DEBUG] Exiting handle_checkout_session_completed")

async def handle_subscription_created(subscription):
    logger.info(f"[DEBUG] Entered handle_subscription_created for subscription: {subscription}")
    """Handle subscription.created event"""
    logger.info(f"Processing subscription.created: {subscription.id}")
    
    try:
        # Get user ID from metadata
        user_id = subscription.metadata.get("user_id")
        if not user_id:
            # Try to get it from the customer
            customer = stripe.Customer.retrieve(subscription.customer)
            user_id = customer.metadata.get("user_id")
        
        if not user_id:
            logger.warning(f"No user ID found for subscription {subscription.id}")
            return
        
        # Update user's subscription status
        await notify_subscription_update(user_id, subscription)
    
    except Exception as e:
        logger.error(f"Error handling subscription.created: {str(e)}")
    logger.info(f"[DEBUG] Exiting handle_subscription_created")

async def handle_subscription_updated(subscription):
    logger.info(f"[DEBUG] Entered handle_subscription_updated for subscription: {subscription}")
    """Handle subscription.updated event"""
    logger.info(f"Processing subscription.updated: {subscription.id}")
    
    try:
        # Get user ID from metadata
        user_id = subscription.metadata.get("user_id")
        if not user_id:
            # Try to get it from the customer
            customer = stripe.Customer.retrieve(subscription.customer)
            user_id = customer.metadata.get("user_id")
        
        if not user_id:
            logger.warning(f"No user ID found for subscription {subscription.id}")
            return
        
        # Update user's subscription status
        await notify_subscription_update(user_id, subscription)
    
    except Exception as e:
        logger.error(f"Error handling subscription.updated: {str(e)}")
    logger.info(f"[DEBUG] Exiting handle_subscription_updated")

async def handle_subscription_deleted(subscription):
    logger.info(f"[DEBUG] Entered handle_subscription_deleted for subscription: {subscription}")
    """Handle subscription.deleted event"""
    logger.info(f"Processing subscription.deleted: {subscription.id}")
    
    try:
        # Get user ID from metadata
        user_id = subscription.metadata.get("user_id")
        if not user_id:
            # Try to get it from the customer
            customer = stripe.Customer.retrieve(subscription.customer)
            user_id = customer.metadata.get("user_id")
        
        if not user_id:
            logger.warning(f"No user ID found for subscription {subscription.id}")
            return
        
        # Update user's subscription status
        await notify_subscription_update(user_id, subscription, is_deleted=True)
    
    except Exception as e:
        logger.error(f"Error handling subscription.deleted: {str(e)}")
    logger.info(f"[DEBUG] Exiting handle_subscription_deleted")

async def handle_invoice_payment_succeeded(invoice):
    logger.info(f"[DEBUG] Entered handle_invoice_payment_succeeded for invoice: {invoice}")
    """Handle invoice.payment_succeeded event"""
    logger.info(f"Processing invoice.payment_succeeded: {invoice.id}")
    
    try:
        # If this was a subscription invoice, check subscription status
        if invoice.subscription:
            subscription = stripe.Subscription.retrieve(invoice.subscription)
            
            # Get user ID from metadata
            user_id = subscription.metadata.get("user_id")
            if not user_id:
                # Try to get it from the customer
                customer = stripe.Customer.retrieve(invoice.customer)
                user_id = customer.metadata.get("user_id")
            
            if not user_id:
                logger.warning(f"No user ID found for subscription {subscription.id}")
                return
            
            # Update user's subscription status
            await notify_subscription_update(user_id, subscription)
    
    except Exception as e:
        logger.error(f"Error handling invoice.payment_succeeded: {str(e)}")
    logger.info(f"[DEBUG] Exiting handle_invoice_payment_succeeded")

async def handle_invoice_payment_failed(invoice):
    logger.info(f"[DEBUG] Entered handle_invoice_payment_failed for invoice: {invoice}")
    """Handle invoice.payment_failed event"""
    logger.info(f"Processing invoice.payment_failed: {invoice.id}")
    
    try:
        # If this was a subscription invoice, check subscription status
        if invoice.subscription:
            subscription = stripe.Subscription.retrieve(invoice.subscription)
            
            # Get user ID from metadata
            user_id = subscription.metadata.get("user_id")
            if not user_id:
                # Try to get it from the customer
                customer = stripe.Customer.retrieve(invoice.customer)
                user_id = customer.metadata.get("user_id")
            
            if not user_id:
                logger.warning(f"No user ID found for subscription {subscription.id}")
                return
            
            # Update user's subscription status
            await notify_subscription_update(user_id, subscription, is_payment_failed=True)
    
    except Exception as e:
        logger.error(f"Error handling invoice.payment_failed: {str(e)}")
    logger.info(f"[DEBUG] Exiting handle_invoice_payment_failed")

async def notify_subscription_update(user_id, subscription, is_deleted=False, is_payment_failed=False):
    print(f"🔥 NOTIFY SUBSCRIPTION UPDATE: user_id={user_id}, plan_id={subscription.metadata.get('plan_id')}")
    logger.info(f"[DEBUG] Entered notify_subscription_update with user_id={user_id}, subscription={subscription}, is_deleted={is_deleted}, is_payment_failed={is_payment_failed}")
    try:
        plan_id = subscription.metadata.get("plan_id", "basic")
        logger.info(f"notify_subscription_update called for user_id={user_id}, plan_id={plan_id}")
        print(f"🔥 NOTIFY: Extracted plan_id: {plan_id}")
        print(f"🔥 NOTIFY: Subscription metadata: {subscription.metadata}")
        # Map plan_id to subscription_type
        if plan_id in [os.getenv("MONTHLY_PLAN_PRICE_ID")]:
            subscription_type = "monthly"
        elif plan_id in [os.getenv("ANNUAL_PLAN_PRICE_ID")]:
            subscription_type = "annual"
        else:
            subscription_type = "free"
        print(f"🔥 NOTIFY: Mapped subscription_type: {subscription_type}")
        # Determine subscription status
        status = "canceled" if is_deleted else subscription.status
        if is_payment_failed and status == "active":
            status = "past_due"
        print(f"🔥 NOTIFY: Final status: {status}")
        # Extract next_credit_reset from Stripe subscription (current_period_end)
        next_credit_reset = None
        if hasattr(subscription, "current_period_end"):
            try:
                next_credit_reset = datetime.utcfromtimestamp(subscription.current_period_end)
            except Exception:
                next_credit_reset = None
        # Create notification payload for user service
        user_service_url = os.getenv("USER_SERVICE_URL", "https://api-gw-production.up.railway.app")
        update_credits_url = f"{user_service_url}/api/user/subscription/update"
        payload = {
            "user_id": user_id,
            "subscription_type": subscription_type
        }
        if next_credit_reset:
            payload["next_credit_reset"] = next_credit_reset.isoformat()
        logger.info(f"Sending credit update to user service: {update_credits_url} with payload: {payload}")
        print(f"🔥 NOTIFY: Sending credit update to: {update_credits_url} with payload: {payload}")
        # Call user service to update credits
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Content-Type": "application/json"}
            try:
                response = await client.post(update_credits_url, json=payload, headers=headers)
                logger.info(f"User service response: {response.status_code} {response.text}")
                print(f"🔥 NOTIFY: User service response: {response.status_code} {response.text}")
                if response.status_code != 200:
                    logger.warning(f"Failed to update user credits: {response.status_code} {response.text}")
                    print(f"🔥 NOTIFY: Failed to update user credits: {response.status_code} {response.text}")
            except Exception as e:
                logger.warning(f"Error updating user credits: {str(e)}")
                print(f"🔥 NOTIFY: Error updating user credits: {str(e)}")
        # (Optional) Still notify Auth Service if needed
        auth_service_url = f"{settings.AUTH_SERVICE_URL}/api/users/{user_id}/subscription"
        print(f"🔥 NOTIFY: Notifying Auth Service at: {auth_service_url} with payload: {payload}")
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Content-Type": "application/json"}
            try:
                response = await client.post(auth_service_url, json=payload, headers=headers)
                if response.status_code != 200:
                    logger.warning(f"Failed to notify Auth Service: {response.status_code} {response.text}")
                    print(f"🔥 NOTIFY: Failed to notify Auth Service: {response.status_code} {response.text}")
            except Exception as e:
                logger.warning(f"Error notifying Auth Service: {str(e)}")
                print(f"🔥 NOTIFY: Error notifying Auth Service: {str(e)}")
        logger.info(f"Subscription update notification sent for user {user_id} - status: {status}")
        logger.info(f"User credits update notification sent for user {user_id} - subscription_type: {subscription_type}")
        print(f"🔥 NOTIFY: Notification sent for user {user_id} - status: {status}, subscription_type: {subscription_type}")
    except Exception as e:
        logger.error(f"Error in notify_subscription_update: {str(e)}")
        print(f"🔥 NOTIFY: Error in notify_subscription_update: {str(e)}")
    logger.info(f"[DEBUG] Exiting notify_subscription_update")
    print(f"🔥 NOTIFY: Exiting notify_subscription_update") 