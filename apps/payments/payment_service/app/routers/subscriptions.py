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

# Configure logger
logger = logging.getLogger("payment_service")

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
    description: str
    price_id: str
    amount: int
    currency: str = "usd"
    interval: str
    features: List[str]

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
    status: str
    current_period_end: datetime
    plan: SubscriptionPlan
    is_active: bool

# Subscription plans
SUBSCRIPTION_PLANS = [
    SubscriptionPlan(
        id="dominator",
        name="Career Dominator",
        description="All features for career domination",
        price_id="price_1RIwjO3N6Cy1dIMXoND5K4zc",
        amount=2999,  # £29.99
        interval="month",
        features=[
            "All Pro features",
            "Priority support",
            "Interview coaching",
            "LinkedIn profile optimization",
            "Career strategy session"
        ]
    ),
    SubscriptionPlan(
        id="accelerator",
        name="Career Accelerator",
        description="Advanced tools for career acceleration",
        price_id="price_1RIwjO3N6Cy1dIMXfkNuOMaT",
        amount=1999,  # £19.99
        interval="month",
        features=[
            "Create and store unlimited CVs",
            "Advanced AI optimization",
            "Detailed job match analysis",
            "Keyword optimization",
            "Cover letter generator"
        ]
    ),
    SubscriptionPlan(
        id="starter",
        name="Career Starter",
        description="Essential tools for starting your career",
        price_id="price_1RIwjP3N6Cy1dIMXvOLBf1bi",
        amount=1499,  # £14.99
        interval="month",
        features=[
            "Create and store up to 3 CVs",
            "Basic AI optimization suggestions",
            "Limited job match analysis"
        ]
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
                    "price": plan.price_id,
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

# Helper function to get user email from user_id (placeholder, to be replaced with real implementation)
def get_user_email_from_id(user_id: str) -> str:
    USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user_service:8000")
    try:
        resp = httpx.get(f"{USER_SERVICE_URL}/api/user/{user_id}", timeout=5)
        if resp.status_code == 200:
            user = resp.json()
            return user.get("email", "")
        else:
            logger.error(f"User service returned status {resp.status_code} for user_id {user_id}")
    except Exception as e:
        logger.error(f"Error fetching user email from user service: {e}")
    return ""

@router.get("/user/{user_id}", response_model=Optional[UserSubscription])
async def get_user_subscription(user_id: str, token: str = Depends(oauth2_scheme)):
    try:
        user_email = get_user_email_from_id(user_id)
        if not user_email:
            logger.info(f"No user email found for user_id {user_id}, returning None.")
            return None
        customers = stripe.Customer.list(email=user_email, limit=1)
        if not customers.data:
            logger.info(f"No Stripe customer found for email {user_email}, returning None.")
            return None
        customer_id = customers.data[0].id

        subscriptions = stripe.Subscription.list(
            customer=customer_id,
            status="active",
            limit=1,
            expand=["data.default_payment_method"]
        )

        if not subscriptions.data:
            logger.info(f"No active Stripe subscription found for customer {customer_id}, returning None.")
            return None

        subscription = subscriptions.data[0]

        # 3. Get the plan details (as before)
        plan_id = subscription.metadata.get("plan_id", "basic") if hasattr(subscription, "metadata") else "basic"
        plan = None
        for p in SUBSCRIPTION_PLANS:
            if p.id == plan_id:
                plan = p
                break
        if not plan:
            plan = SUBSCRIPTION_PLANS[0]  # Default to first plan

        # Create the response
        return UserSubscription(
            id=subscription.id,
            status=subscription.status,
            current_period_end=datetime.fromtimestamp(subscription.current_period_end),
            plan=plan,
            is_active=subscription.status == "active"
        )

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error in get_user_subscription: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error in get_user_subscription: {str(e)}")
        return None

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
        ) 