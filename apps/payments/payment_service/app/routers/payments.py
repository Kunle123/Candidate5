from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import logging
import stripe
import json
from app.config import settings
from fastapi import Depends
from jose import jwt, JWTError

# Configure logger
logger = logging.getLogger("payment_service")

# Initialize router
router = APIRouter(prefix="/api/payments")

# Set up OAuth2 with Bearer token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Initialize Stripe
stripe.api_key = settings.STRIPE_API_KEY

# Pydantic models
class PaymentMethod(BaseModel):
    id: str
    type: str
    card_last4: Optional[str] = None
    card_brand: Optional[str] = None
    card_exp_month: Optional[int] = None
    card_exp_year: Optional[int] = None
    is_default: bool = False

class PaymentHistory(BaseModel):
    id: str
    amount: int
    currency: str
    status: str
    description: str
    created: datetime
    invoice_url: Optional[str] = None
    receipt_url: Optional[str] = None
    payment_method: Optional[PaymentMethod] = None

class UserPaymentProfile(BaseModel):
    user_id: str
    payment_methods: List[PaymentMethod] = []
    default_payment_method_id: Optional[str] = None
    has_payment_method: bool = False

@router.get("/methods/{user_id}", response_model=List[PaymentMethod])
async def get_payment_methods(user_id: str, token: str = Depends(oauth2_scheme)):
    """Get all payment methods for a user"""
    try:
        # First, check if the user has a customer ID in Stripe
        customers = stripe.Customer.list(email=user_id, limit=1)
        
        if not customers.data:
            return []
        
        customer_id = customers.data[0].id
        
        # Get payment methods for the customer
        payment_methods = stripe.PaymentMethod.list(
            customer=customer_id,
            type="card"
        )
        
        # Get the default payment method
        customer = stripe.Customer.retrieve(customer_id)
        default_payment_method_id = customer.get("invoice_settings", {}).get("default_payment_method")
        
        result = []
        for pm in payment_methods.data:
            if pm.type == "card":
                result.append(PaymentMethod(
                    id=pm.id,
                    type=pm.type,
                    card_last4=pm.card.last4,
                    card_brand=pm.card.brand,
                    card_exp_month=pm.card.exp_month,
                    card_exp_year=pm.card.exp_year,
                    is_default=(pm.id == default_payment_method_id)
                ))
        
        return result
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error in get_payment_methods: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error retrieving payment methods: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error in get_payment_methods: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )

@router.get("/history/{user_id}", response_model=List[PaymentHistory])
async def get_payment_history(user_id: str, token: str = Depends(oauth2_scheme)):
    """Get payment history for a user"""
    try:
        # First, check if the user has a customer ID in Stripe
        customers = stripe.Customer.list(email=user_id, limit=1)
        
        if not customers.data:
            return []
        
        customer_id = customers.data[0].id
        
        # Get payment intents for the customer
        payment_intents = stripe.PaymentIntent.list(
            customer=customer_id,
            limit=100
        )
        
        # Get invoices
        invoices = stripe.Invoice.list(
            customer=customer_id,
            limit=100,
            status="paid"
        )
        
        # Process payment intents
        payment_history = []
        for pi in payment_intents.data:
            if pi.status == "succeeded":
                # Try to find payment method details
                payment_method = None
                if pi.payment_method:
                    try:
                        pm = stripe.PaymentMethod.retrieve(pi.payment_method)
                        if pm.type == "card":
                            payment_method = PaymentMethod(
                                id=pm.id,
                                type=pm.type,
                                card_last4=pm.card.last4,
                                card_brand=pm.card.brand,
                                card_exp_month=pm.card.exp_month,
                                card_exp_year=pm.card.exp_year
                            )
                    except Exception as e:
                        logger.warning(f"Error retrieving payment method {pi.payment_method}: {str(e)}")
                
                # Find related invoice
                invoice_url = None
                for inv in invoices.data:
                    if inv.payment_intent == pi.id:
                        invoice_url = inv.hosted_invoice_url
                        break
                
                payment_history.append(PaymentHistory(
                    id=pi.id,
                    amount=pi.amount,
                    currency=pi.currency,
                    status=pi.status,
                    description=pi.description or "Payment",
                    created=datetime.fromtimestamp(pi.created),
                    invoice_url=invoice_url,
                    receipt_url=pi.charges.data[0].receipt_url if pi.charges.data else None,
                    payment_method=payment_method
                ))
        
        # Sort by most recent first
        payment_history.sort(key=lambda x: x.created, reverse=True)
        
        return payment_history
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error in get_payment_history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error retrieving payment history: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error in get_payment_history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )

@router.post("/methods/add")
async def add_payment_method(
    user_id: str,
    return_url: str,
    token: str = Depends(oauth2_scheme)
):
    """Create a Stripe SetupIntent for adding a payment method"""
    try:
        # First, get or create a customer in Stripe
        customers = stripe.Customer.list(email=user_id, limit=1)
        
        customer_id = None
        if customers.data:
            customer_id = customers.data[0].id
        else:
            # Create a new customer
            customer = stripe.Customer.create(
                email=user_id,  # user_id should be the UUID
                metadata={"user_id": user_id}  # Always use UUID here
            )
            customer_id = customer.id
        
        # Create a SetupIntent
        setup_intent = stripe.SetupIntent.create(
            customer=customer_id,
            payment_method_types=["card"],
            usage="off_session",
            metadata={"user_id": user_id}
        )
        
        # Create a Checkout session for setup
        # If this is a top-up/one-off payment, add plan_id to metadata
        # (Assume you have a way to pass the top-up price_id; if not, add a placeholder for future use)
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="setup",
            customer=customer_id,
            setup_intent_data={
                "metadata": {
                    "user_id": user_id,  # Always use UUID here
                    # "plan_id": topup_price_id  # Uncomment and set if you have a top-up price_id
                }
            },
            metadata={
                "user_id": user_id,
                # "plan_id": topup_price_id  # Uncomment and set if you have a top-up price_id
            },
            success_url=f"{return_url}?success=true&setup_intent_id={setup_intent.id}",
            cancel_url=f"{return_url}?canceled=true",
        )
        
        return {
            "setup_intent_id": setup_intent.id,
            "client_secret": setup_intent.client_secret,
            "checkout_url": checkout_session.url
        }
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error in add_payment_method: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating setup intent: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error in add_payment_method: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )

@router.delete("/methods/{payment_method_id}")
async def delete_payment_method(
    payment_method_id: str,
    token: str = Depends(oauth2_scheme)
):
    """Delete a payment method"""
    try:
        # Delete the payment method
        payment_method = stripe.PaymentMethod.detach(payment_method_id)
        
        return {"status": "success", "message": "Payment method removed successfully"}
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error in delete_payment_method: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error deleting payment method: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error in delete_payment_method: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )

@router.post("/methods/{payment_method_id}/default")
async def set_default_payment_method(
    payment_method_id: str,
    user_id: str,
    token: str = Depends(oauth2_scheme)
):
    """Set a payment method as default"""
    try:
        # First, get the customer in Stripe
        customers = stripe.Customer.list(email=user_id, limit=1)
        
        if not customers.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )
        
        customer_id = customers.data[0].id
        
        # Update the customer's default payment method
        stripe.Customer.modify(
            customer_id,
            invoice_settings={
                "default_payment_method": payment_method_id
            }
        )
        
        return {"status": "success", "message": "Default payment method updated successfully"}
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error in set_default_payment_method: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error setting default payment method: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error in set_default_payment_method: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        ) 

@router.post("/customer-portal")
async def create_customer_portal(token: str = Depends(oauth2_scheme)):
    """Create a Stripe Customer Portal session for the authenticated user and return the portal URL."""
    try:
        # Decode the JWT to get the user's email
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            user_email = payload.get("email")
            if not user_email:
                raise HTTPException(status_code=400, detail="User email not found in token.")
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid authentication token.")

        # Find the Stripe customer by email
        customers = stripe.Customer.list(email=user_email, limit=1)
        if not customers.data:
            raise HTTPException(status_code=404, detail="Stripe customer not found for user.")
        customer_id = customers.data[0].id

        # Create the billing portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url="https://candidate5.co.uk/account"
        )
        return {"url": portal_session.url}
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error in create_customer_portal: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error creating customer portal: {str(e)}")
    except Exception as e:
        logger.error(f"Error in create_customer_portal: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred") 