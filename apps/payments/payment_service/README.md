# CandidateV Payment Service

This service handles payment processing, subscription management, and billing for the CandidateV platform.

## Features

- Subscription plan management
- Payment processing using Stripe
- Billing and payment history
- Webhook handling for Stripe events

## Prerequisites

- Python 3.10+
- [Stripe](https://stripe.com/) account with API keys
- PostgreSQL database (shared with other services)

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```
# Core settings
PORT=8005
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256

# CORS settings
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,https://candidatev.vercel.app

# Stripe API settings
STRIPE_API_KEY=sk_test_your_stripe_test_key
STRIPE_WEBHOOK_SECRET=whsec_your_stripe_webhook_secret

# Stripe pricing IDs
BASIC_PLAN_PRICE_ID=price_basic
PRO_PLAN_PRICE_ID=price_pro
ENTERPRISE_PLAN_PRICE_ID=price_enterprise

# Service URLs
AUTH_SERVICE_URL=http://localhost:8000
CV_SERVICE_URL=http://localhost:8002
```

## Installation

1. Create and activate a virtual environment:

```bash
python -m venv env
source env/bin/activate  # On Windows: .\env\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the Service

```bash
uvicorn main:app --reload --port 8005
```

Or use the provided PowerShell script:

```powershell
.\run_payment_service.ps1
```

## API Endpoints

### Health Check

- `GET /api/health`: Check service health and Stripe connectivity

### Subscription Management

- `GET /api/subscriptions/plans`: Get all available subscription plans
- `GET /api/subscriptions/plans/{plan_id}`: Get details for a specific plan
- `POST /api/subscriptions/checkout`: Create a checkout session for subscription
- `GET /api/subscriptions/user/{user_id}`: Get a user's current subscription
- `POST /api/subscriptions/cancel/{subscription_id}`: Cancel a subscription

### Payment Management

- `GET /api/payments/methods/{user_id}`: Get a user's payment methods
- `POST /api/payments/methods/add`: Add a new payment method
- `DELETE /api/payments/methods/{payment_method_id}`: Delete a payment method
- `POST /api/payments/methods/{payment_method_id}/default`: Set a default payment method
- `GET /api/payments/history/{user_id}`: Get a user's payment history

### Webhooks

- `POST /api/webhooks/stripe`: Handle Stripe webhook events

## Testing

To test the endpoints, use the provided test script:

```powershell
.\test_payment_service.ps1
```

## Stripe Setup

1. Create a Stripe account at [stripe.com](https://stripe.com/)
2. Get your API keys from the Stripe Dashboard
3. Set up webhook endpoints in Stripe to receive events
4. Create products and pricing plans in Stripe

## Docker

Build and run the service using Docker:

```bash
docker build -t candidatev-payment-service .
docker run -p 8005:8005 -e STRIPE_API_KEY=sk_test_your_key candidatev-payment-service
```

Or use Docker Compose:

```bash
docker-compose up payment-service
``` 