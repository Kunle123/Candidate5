# User Signup API Documentation

## Important: Use the API Gateway for All Auth Requests
All authentication and user-related API requests must be made via the API Gateway, not directly to the Auth service.

- **Gateway Base URL (current):** `https://api-gw-production.up.railway.app`
- **Use this placeholder in examples:** `<GATEWAY_URL>`
- **Example full endpoint:** `POST <GATEWAY_URL>/api/auth/register`

---

## 1. Signup (Register) Endpoint

### Endpoint
```
POST <GATEWAY_URL>/api/auth/register
```

### Description
Creates a new user account with the provided credentials.

### Request Body
```json
{
  "email": "user@example.com",
  "password": "yourPassword123",
  "name": "John Doe" // (optional, if your backend supports it)
}
```

- **email**: User's email address (must be unique)
- **password**: User's password (should meet security requirements, e.g., min 8 chars)
- **name**: (Optional) User's full name

### Response (Success)
- **Status:** `201 Created`
```json
{
  "message": "User registered successfully",
  "user": {
    "id": "user_id",
    "email": "user@example.com"
  }
}
```

### Response (Error)
- **Status:** `400 Bad Request`
```json
{
  "error": "Email already exists"
}
```
- **Status:** `422 Unprocessable Entity`
```json
{
  "error": "Password must be at least 8 characters"
}
```

---

## 2. Login Endpoint

### Endpoint
```
POST <GATEWAY_URL>/api/auth/login
```

### Description
Authenticates a user and returns a JWT or session token.

### Request Body
```json
{
  "email": "user@example.com",
  "password": "yourPassword123"
}
```

### Response (Success)
- **Status:** `200 OK`
```json
{
  "token": "jwt_token_here",
  "user": {
    "id": "user_id",
    "email": "user@example.com"
  }
}
```

### Response (Error)
- **Status:** `401 Unauthorized`
```json
{
  "error": "Invalid email or password"
}
```

---

## 3. Get Current User (Session Check)

### Endpoint
```
GET <GATEWAY_URL>/api/auth/me
```

### Description
Returns the currently authenticated user's information.  
**Requires Authorization header with Bearer token.**

### Headers
```
Authorization: Bearer <jwt_token_here>
```

### Response (Success)
- **Status:** `200 OK`
```json
{
  "id": "user_id",
  "email": "user@example.com"
}
```

### Response (Error)
- **Status:** `401 Unauthorized`
```json
{
  "error": "Not authenticated"
}
```

---

## 4. Logout Endpoint

### Endpoint
```
POST <GATEWAY_URL>/api/auth/logout
```

### Description
Logs out the user (for stateless JWT, this is usually handled on the client by deleting the token).

### Headers
```
Authorization: Bearer <jwt_token_here>
```

### Response
- **Status:** `200 OK`
```json
{
  "message": "Logged out successfully"
}
```

---

## 5. Social Signup/Login Endpoints

### Overview
These endpoints allow users to sign up or log in using their LinkedIn, Facebook, or Google accounts. The frontend should redirect users to the appropriate OAuth provider, then handle the callback to complete authentication.

### a. Google
- **Start OAuth:**
  ```
  GET <GATEWAY_URL>/api/auth/google
  ```
  Redirects the user to Google's OAuth consent screen.

- **OAuth Callback:**
  ```
  GET <GATEWAY_URL>/api/auth/google/callback?code=...
  ```
  The backend handles the callback, exchanges the code for user info, and issues a JWT/session.

- **Response (Success):**
  - Redirects to frontend with a token (e.g., `/auth/callback?token=...`), or returns JSON:
    ```json
    {
      "token": "jwt_token_here",
      "user": {
        "id": "user_id",
        "email": "user@example.com"
      }
    }
    ```

### b. Facebook
- **Start OAuth:**
  ```
  GET <GATEWAY_URL>/api/auth/facebook
  ```
  Redirects the user to Facebook's OAuth consent screen.

- **OAuth Callback:**
  ```
  GET <GATEWAY_URL>/api/auth/facebook/callback?code=...
  ```
  The backend handles the callback, exchanges the code for user info, and issues a JWT/session.

### c. LinkedIn
- **Start OAuth:**
  ```
  GET <GATEWAY_URL>/api/auth/linkedin
  ```
  Redirects the user to LinkedIn's OAuth consent screen.

- **OAuth Callback:**
  ```
  GET <GATEWAY_URL>/api/auth/linkedin/callback?code=...
  ```
  The backend handles the callback, exchanges the code for user info, and issues a JWT/session.

- **Response (Success):**
  - Same as Google above.

#### **Frontend Usage Notes**
- The frontend should provide buttons for each social provider.
- On click, redirect the user to the `/api/auth/{provider}` endpoint.
- After successful authentication, the backend should redirect the user back to the frontend with a token (e.g., `/auth/callback?token=...`), or the frontend should fetch the token from the backend.
- The frontend should store the token and use it for authenticated requests as with email/password login.

---

## Frontend Usage Requirements

- **All requests should be made with `Content-Type: application/json` header.**
- **For protected endpoints (`/me`, `/logout`), include the `Authorization: Bearer <token>` header.**
- **Store the JWT token securely (e.g., in memory, or httpOnly cookie if using sessions).**
- **Handle error responses and display appropriate messages to the user.**

---

## Example Signup Flow (Frontend)

1. **User fills out registration form.**
2. **Frontend sends POST request to `/api/auth/register` with email and password.**
3. **On success, optionally auto-login the user or redirect to login page.**
4. **On error, display error message (e.g., "Email already exists").**

---

## Security Notes

- Passwords must be sent over HTTPS only.
- Never log or expose raw passwords.
- Use strong password validation on both frontend and backend.
- Consider rate limiting and CAPTCHA to prevent abuse.

---

## 6. Password Reset & Forgot Password

### a. Request Password Reset (Forgot Password)
- **Endpoint:**
  ```
  POST <GATEWAY_URL>/api/auth/forgot-password
  ```
- **Description:**
  Sends a password reset email to the user with a reset link or token.
- **Request Body:**
  ```json
  {
    "email": "user@example.com"
  }
  ```
- **Response (Success):**
  - **Status:** `200 OK`
    ```json
    {
      "message": "Password reset email sent"
    }
    ```
- **Response (Error):**
  - **Status:** `404 Not Found`
    ```json
    {
      "error": "Email not found"
    }
    ```

### b. Reset Password
- **Endpoint:**
  ```
  POST <GATEWAY_URL>/api/auth/reset-password
  ```
- **Description:**
  Resets the user's password using a token from the reset email.
- **Request Body:**
  ```json
  {
    "token": "reset_token_from_email",
    "password": "newPassword123"
  }
  ```
- **Response (Success):**
  - **Status:** `200 OK`
    ```json
    {
      "message": "Password reset successful"
    }
    ```
- **Response (Error):**
  - **Status:** `400 Bad Request`
    ```json
    {
      "error": "Invalid or expired token"
    }
    ```

---

## 7. Email Verification

### a. Send Verification Email
- **Endpoint:**
  ```
  POST <GATEWAY_URL>/api/auth/send-verification
  ```
- **Description:**
  Sends a verification email to the user.
- **Request Body:**
  ```json
  {
    "email": "user@example.com"
  }
  ```
- **Response (Success):**
  - **Status:** `200 OK`
    ```json
    {
      "message": "Verification email sent"
    }
    ```

### b. Verify Email
- **Endpoint:**
  ```
  GET <GATEWAY_URL>/api/auth/verify-email?token=...
  ```
- **Description:**
  Verifies the user's email using a token from the verification email.
- **Response (Success):**
  - **Status:** `200 OK`
    ```json
    {
      "message": "Email verified successfully"
    }
    ```
- **Response (Error):**
  - **Status:** `400 Bad Request`
    ```json
    {
      "error": "Invalid or expired token"
    }
    ```

---

## 8. Account Update & Deletion

### a. Update Account
- **Endpoint:**
  ```
  PATCH <GATEWAY_URL>/api/auth/update
  ```
- **Description:**
  Updates user profile information. Requires authentication.
- **Headers:**
  ```
  Authorization: Bearer <jwt_token_here>
  ```
- **Request Body (example):**
  ```json
  {
    "name": "New Name",
    "email": "newemail@example.com"
  }
  ```
- **Response (Success):**
  - **Status:** `200 OK`
    ```json
    {
      "message": "Account updated successfully",
      "user": {
        "id": "user_id",
        "email": "newemail@example.com",
        "name": "New Name"
      }
    }
    ```

### b. Delete Account
- **Endpoint:**
  ```
  DELETE <GATEWAY_URL>/api/auth/delete
  ```
- **Description:**
  Deletes the user's account. Requires authentication.
- **Headers:**
  ```
  Authorization: Bearer <jwt_token_here>
  ```
- **Response (Success):**
  - **Status:** `200 OK`
    ```json
    {
      "message": "Account deleted successfully"
    }
    ```

---

## 9. Token Refresh (if using refresh tokens)

### Endpoint
```
POST <GATEWAY_URL>/api/auth/refresh-token
```

### Description
Exchanges a valid refresh token for a new access token.

### Request Body
```json
{
  "refreshToken": "refresh_token_here"
}
```

### Response (Success)
- **Status:** `200 OK`
```json
{
  "token": "new_jwt_token_here",
  "refreshToken": "new_refresh_token_here"
}
```

### Response (Error)
- **Status:** `401 Unauthorized`
```json
{
  "error": "Invalid or expired refresh token"
}
```

--- 