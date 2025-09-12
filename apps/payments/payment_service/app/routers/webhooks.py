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

@router.post("/stripe")
async def stripe_webhook(request: Request):
    print("🔥 WEBHOOK DEBUG: Handler called")
    body = await request.body()
    sig_header = request.headers.get("stripe-signature")
    print(f"🔥 WEBHOOK DEBUG: Body length: {len(body)}")
    print(f"🔥 WEBHOOK DEBUG: Signature: {sig_header}")
    print(f"🔥 WEBHOOK DEBUG: Secret configured: {bool(STRIPE_WEBHOOK_SECRET)}")
    if not sig_header:
        print("🔥 WEBHOOK DEBUG: Missing signature header")
        return {"detail": "Missing Stripe signature header"}
    # Test signature verification
    try:
        print("🔥 WEBHOOK DEBUG: About to verify signature...")
        event = stripe.Webhook.construct_event(
            body,
            sig_header,
            STRIPE_WEBHOOK_SECRET
        )
        print("🔥 WEBHOOK DEBUG: ✅ Signature verification SUCCESS!")
        print(f"🔥 WEBHOOK DEBUG: Event type: {event.get('type')}")
        return {"status": "success", "event_type": event.get('type')}
    except stripe.error.SignatureVerificationError as e:
        print(f"🔥 WEBHOOK DEBUG: ❌ Signature verification FAILED: {str(e)}")
        return {"status": "error", "message": f"Invalid signature: {str(e)}"}
    except Exception as e:
        print(f"🔥 WEBHOOK DEBUG: ❌ Unexpected error: {str(e)}")
        return {"status": "error", "message": f"Error: {str(e)}"}

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
    logger.info(f"[DEBUG] Entered notify_subscription_update with user_id={user_id}, subscription={subscription}, is_deleted={is_deleted}, is_payment_failed={is_payment_failed}")
    """Notify other services about subscription changes and update user credits"""
    try:
        plan_id = subscription.metadata.get("plan_id", "basic")
        logger.info(f"notify_subscription_update called for user_id={user_id}, plan_id={plan_id}")
        # Map plan_id to subscription_type
        if plan_id in [os.getenv("MONTHLY_PLAN_PRICE_ID")]:
            subscription_type = "monthly"
        elif plan_id in [os.getenv("ANNUAL_PLAN_PRICE_ID")]:
            subscription_type = "annual"
        else:
            subscription_type = "free"
        # Determine subscription status
        status = "canceled" if is_deleted else subscription.status
        if is_payment_failed and status == "active":
            status = "past_due"
        # Create notification payload for user service
        user_service_url = os.getenv("USER_SERVICE_URL", "https://api-gw-production.up.railway.app")
        update_credits_url = f"{user_service_url}/api/user/subscription/update"
        payload = {
            "user_id": user_id,
            "subscription_type": subscription_type
        }
        logger.info(f"Sending credit update to user service: {update_credits_url} with payload: {payload}")
        # Call user service to update credits
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Content-Type": "application/json"}
            try:
                response = await client.post(update_credits_url, json=payload, headers=headers)
                logger.info(f"User service response: {response.status_code} {response.text}")
                if response.status_code != 200:
                    logger.warning(f"Failed to update user credits: {response.status_code} {response.text}")
            except Exception as e:
                logger.warning(f"Error updating user credits: {str(e)}")
        # (Optional) Still notify Auth Service if needed
        auth_service_url = f"{settings.AUTH_SERVICE_URL}/api/users/{user_id}/subscription"
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Content-Type": "application/json"}
            try:
                response = await client.post(auth_service_url, json=payload, headers=headers)
                if response.status_code != 200:
                    logger.warning(f"Failed to notify Auth Service: {response.status_code} {response.text}")
            except Exception as e:
                logger.warning(f"Error notifying Auth Service: {str(e)}")
        
        logger.info(f"Subscription update notification sent for user {user_id} - status: {status}")
        logger.info(f"User credits update notification sent for user {user_id} - subscription_type: {subscription_type}")
    except Exception as e:
        logger.error(f"Error in notify_subscription_update: {str(e)}") 
    logger.info(f"[DEBUG] Exiting notify_subscription_update") 