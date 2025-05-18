# Account & Subscription API Reference

All endpoints are accessible via the API Gateway: `https://api-gw-production.up.railway.app`
All endpoints require `Authorization: Bearer <token>` in the headers unless otherwise noted.

---

## 1. Profile Section

### a. Get Current User Profile
- **Endpoint:** `GET /users/me`
- **Description:** Fetch the logged-in user's profile info.
- **Headers:**
  - `Authorization: Bearer <token>`
- **Response:**
```json
{
  "id": "user_id",
  "email": "user@example.com",
  "name": "John Doe",
  ...
}
```

### b. Update User Profile
- **Endpoint:** `PATCH /api/users/profile`
- **Description:** Update the user's name, email, or phone.
- **Headers:**
  - `Authorization: Bearer <token>`
- **Request Body:**
```json
{
  "name": "New Name",
  "email": "new@email.com"
}
```
- **Response:**
```json
{
  "success": true,
  "profile": { ...updated profile... }
}
```

### c. Send Verification Email
- **Endpoint:** `POST /api/auth/send-verification`
- **Description:** Send a verification email to the user.
- **Headers:**
  - `Authorization: Bearer <token>`
- **Response:**
```json
{
  "success": true,
  "message": "Verification email sent."
}
```

### d. Change Password
- **Endpoint:** `POST /api/auth/change-password`
- **Description:** Change the user's password.
- **Headers:**
  - `Authorization: Bearer <token>`
- **Request Body:**
```json
{
  "old_password": "oldpass",
  "new_password": "newpass"
}
```
- **Response:**
```json
{
  "success": true,
  "message": "Password changed."
}
```

---

## 2. Subscription & Billing Section

### a. Get Subscription Info
- **Endpoint:** `GET /api/subscriptions/user/{userId}`
- **Description:** Fetch the user's current subscription plan and status.
- **Headers:**
  - `Authorization: Bearer <token>`

### b. Cancel Subscription
- **Endpoint:** `POST /api/subscriptions/cancel/{subscriptionId}`
- **Description:** Cancel the user's subscription.
- **Headers:**
  - `Authorization: Bearer <token>`

### c. Get Billing History
- **Endpoint:** `GET /api/payments/history/{userId}`
- **Description:** Fetch the user's billing/invoice history.
- **Headers:**
  - `Authorization: Bearer <token>`

### d. Get Payment Methods
- **Endpoint:** `GET /api/payments/methods/{userId}`
- **Description:** List the user's saved payment methods.
- **Headers:**
  - `Authorization: Bearer <token>`

### e. Add Payment Method
- **Endpoint:** `POST /api/payments/methods/add`
- **Description:** Add a new payment method (may redirect to payment provider).
- **Headers:**
  - `Authorization: Bearer <token>`

### f. Delete Payment Method
- **Endpoint:** `DELETE /api/payments/methods/{paymentMethodId}`
- **Description:** Remove a payment method.
- **Headers:**
  - `Authorization: Bearer <token>`

### g. Set Default Payment Method
- **Endpoint:** `POST /api/payments/methods/{paymentMethodId}/default`
- **Description:** Set a payment method as default.
- **Headers:**
  - `Authorization: Bearer <token>`

---

## 3. Authentication
- All endpoints require a valid JWT token in the `Authorization` header.
- On 401/403, redirect to login.

---

**For questions or updates, coordinate with the backend team to avoid breaking changes.** 