from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import logging
import stripe
import json
import httpx
from app.config import settings
from app.routers.payments import get_email_for_user_id, USER_SERVICE_URL
import traceback

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("payment_service")
logger.setLevel(logging.INFO)

# Initialize router
router = APIRouter(prefix="/api/subscriptions")

# Set up OAuth2 with Bearer token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Initialize Stripe
stripe.api_key = settings.STRIPE_API_KEY

# Pydantic models for request and response
class SubscriptionPlan(BaseModel):
    id: str
    name: str
    amount: int
    currency: str = "usd"
    interval: str

class SubscriptionRequest(BaseModel):
    plan_id: str
    user_id: str
    email: str
    return_url: str

class SubscriptionResponse(BaseModel):
    session_id: str
    checkout_url: str

class UserSubscription(BaseModel):
    id: str
    plan_name: str
    plan: SubscriptionPlan
    status: str
    renewal_date: str  # ISO format string
    current_period_end: str  # ISO format string

    class Config:
        from_attributes = True  # Updated from orm_mode
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# Subscription plans
SUBSCRIPTION_PLANS = [
    SubscriptionPlan(
        id="dominator",
        name="Career Dominator",
        amount=2999,  # £29.99
        currency="usd",
        interval="month"
    ),
    SubscriptionPlan(
        id="accelerator",
        name="Career Accelerator",
        amount=1999,  # £19.99
        currency="usd",
        interval="month"
    ),
    SubscriptionPlan(
        id="starter",
        name="Career Starter",
        amount=1499,  # £14.99
        currency="usd",
        interval="month"
    )
]

@router.get("/plans", response_model=List[SubscriptionPlan])
async def get_subscription_plans(token: str = Depends(oauth2_scheme)):
    """Get all available subscription plans"""
    return SUBSCRIPTION_PLANS

@router.get("/plans/{plan_id}", response_model=SubscriptionPlan)
async def get_subscription_plan(plan_id: str, token: str = Depends(oauth2_scheme)):
    """Get details for a specific subscription plan"""
    for plan in SUBSCRIPTION_PLANS:
        if plan.id == plan_id:
            return plan
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Subscription plan with ID {plan_id} not found"
    )

@router.post("/checkout", response_model=SubscriptionResponse)
async def create_checkout_session(
    request: SubscriptionRequest,
    token: str = Depends(oauth2_scheme)
):
    """Create a Stripe Checkout session for subscription purchase"""
    try:
        # Find the plan by ID
        plan = None
        for p in SUBSCRIPTION_PLANS:
            if p.id == request.plan_id:
                plan = p
                break
        
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscription plan with ID {request.plan_id} not found"
            )
        
        # Create a Stripe Checkout session
        checkout_session = stripe.checkout.Session.create(
            customer_email=request.email,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": plan.id,
                    "quantity": 1,
                },
            ],
            metadata={
                "user_id": request.user_id,
                "plan_id": plan.id
            },
            mode="subscription",
            success_url=f"{request.return_url}?success=true&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{request.return_url}?canceled=true",
        )
        
        return SubscriptionResponse(
            session_id=checkout_session.id,
            checkout_url=checkout_session.url
        )
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error in create_checkout_session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating checkout session: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error in create_checkout_session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )

@router.get("/user/{user_id}", response_model=Optional[UserSubscription])
async def get_user_subscription(user_id: str, request: Request, token: str = Depends(oauth2_scheme)):
    print(f"DEBUG: get_user_subscription called for user_id={user_id}")
    try:
        logger.info(f"Getting subscription for user {user_id}")
        logger.info(f"Request headers: {dict(request.headers)}")
        
        # Validate UUID format
        import uuid
        try:
            uuid_obj = uuid.UUID(user_id)
            if str(uuid_obj) != user_id:
                logger.error(f"Invalid UUID format for user_id: {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid UUID format"
                )
        except ValueError as e:
            logger.error(f"Invalid UUID format for user_id: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid UUID format"
            )
        
        try:
            # Get user's email
            try:
                logger.info(f"Attempting to get email for user {user_id}")
                email = await get_email_for_user_id(user_id, token)
                logger.info(f"Found email for user {user_id}: {email}")
            except HTTPException as e:
                logger.error(f"HTTP error getting email for user {user_id}: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error getting email for user {user_id}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error getting user email: {str(e)}"
                )
            
            # Get subscriptions for the user from Stripe
            try:
                logger.info(f"Searching for Stripe customer with email: {email}")
                customers = stripe.Customer.list(email=email, limit=1)
                logger.info(f"Stripe customer list response: {json.dumps(customers.data, default=str)}")
                
                if not customers.data:
                    logger.info(f"No Stripe customer found for user {user_id} with email {email}")
                    return None
                    
                customer_id = customers.data[0].id
                logger.info(f"Found Stripe customer {customer_id} for user {user_id}")
            except stripe.error.StripeError as e:
                logger.error(f"Stripe error getting customer for user {user_id}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error getting Stripe customer: {str(e)}"
                )
            
            # Get active subscriptions
            try:
                logger.info(f"Searching for active subscriptions for customer {customer_id}")
                subscriptions = stripe.Subscription.list(
                    limit=1,  # Typically a user would have only one active subscription
                    status="active",
                    expand=["data.default_payment_method"],
                    customer=customer_id
                )
                logger.info(f"Stripe subscription list response: {json.dumps(subscriptions.data, default=str)}")
                
                if not subscriptions.data:
                    logger.info(f"No active subscriptions found for user {user_id}")
                    return None
                    
                subscription = subscriptions.data[0]
                logger.info(f"Found subscription {subscription.id} for user {user_id}")
            except stripe.error.StripeError as e:
                logger.error(f"Stripe error getting subscriptions for user {user_id}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error getting subscriptions: {str(e)}"
                )
            
            # Get the plan details
            try:
                plan_id = subscription.metadata.get("plan_id", "basic")  # Default to basic if not specified
                logger.info(f"Plan ID from subscription metadata: {plan_id}")
                
                plan = None
                for p in SUBSCRIPTION_PLANS:
                    if p.id == plan_id:
                        plan = p
                        break
                if not plan:
                    plan = SUBSCRIPTION_PLANS[0]  # Default to first plan
                    logger.info(f"Using default plan for user {user_id}")
            except Exception as e:
                logger.error(f"Error getting plan details for user {user_id}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error getting plan details: {str(e)}"
                )
                
            # Create the response
            try:
                current_period_end = datetime.fromtimestamp(subscription.current_period_end)
                logger.info(f"Current period end: {current_period_end}")
                
                # Map Stripe status to frontend expected status
                status_map = {
                    "active": "Active",
                    "canceled": "Canceled",
                    "past_due": "Past Due",
                    "trialing": "Trialing"
                }
                status = status_map.get(subscription.status, subscription.status.capitalize())
                
                # Convert datetime to ISO format string
                current_period_end_iso = current_period_end.isoformat()
                
                subscription_response = UserSubscription(
                    id=subscription.id,
                    plan_name=plan.name,
                    plan=SubscriptionPlan(
                        id=plan.id,
                        name=plan.name,
                        amount=plan.amount,
                        currency=plan.currency,
                        interval=plan.interval
                    ),
                    status=status,
                    renewal_date=current_period_end_iso,
                    current_period_end=current_period_end_iso
                )
                logger.info(f"Successfully created subscription response for user {user_id}")
                logger.info(f"Response: {subscription_response.json()}")
                return subscription_response
            except Exception as e:
                logger.error(f"Error creating subscription response for user {user_id}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error creating response: {str(e)}"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            print(f"DEBUG: Exception in get_user_subscription: {e}")
            logger.error(f"Exception in get_user_subscription: {str(e)}\n{traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {str(e)}"
            )
    except Exception as e:
        print(f"DEBUG: Exception in get_user_subscription: {e}")
        logger.error(f"Exception in get_user_subscription: {str(e)}\n{traceback.format_exc()}")
        raise

@router.post("/cancel/{subscription_id}")
async def cancel_subscription(
    subscription_id: str,
    token: str = Depends(oauth2_scheme)
):
    """Cancel a user's subscription"""
    try:
        # Cancel the subscription at the end of the current billing period
        subscription = stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True
        )
        
        return {
            "status": "success",
            "message": "Subscription scheduled for cancellation at the end of the billing period",
            "cancel_at": datetime.fromtimestamp(subscription.cancel_at).isoformat() if subscription.cancel_at else None
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error in cancel_subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error canceling subscription: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error in cancel_subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        ) the change
        