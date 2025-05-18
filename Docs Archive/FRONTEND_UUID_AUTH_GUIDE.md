# Frontend Developer Guide: Using UUIDs and JWTs for Authentication

## 1. Expect UUIDs for User IDs
- All user IDs in the system are UUIDs (e.g., `a1b2c3d4-5678-90ab-cdef-1234567890ab`), not integers.
- When handling user data (e.g., profile, CVs, payments), always treat user IDs as strings.
- Never assume user IDs are numbers or can be incremented.

## 2. JWT Authentication
- The backend expects a JWT (JSON Web Token) for all authenticated API requests.
- The JWT will contain the user's UUID as the `id` or `user_id` field in its payload.
- Store the JWT securely (e.g., in memory, HTTP-only cookies, or secure storage).

## 3. Sending Authenticated Requests
- Always include the JWT in the `Authorization` header for API requests:
  ```http
  Authorization: Bearer <jwt_token>
  ```
- This applies to all endpoints that require authentication (CV, AI, payments, etc.).

## 4. Handling User Data
- When decoding the JWT (e.g., for displaying user info), extract the UUID from the `id` or `user_id` field.
- Use this UUID for all user-specific API calls and UI logic.
- Example (using JavaScript):
  ```js
  // Decode JWT (using a library like jwt-decode)
  const payload = jwt_decode(token);
  const userId = payload.id || payload.user_id;
  ```

## 5. Testing and Debugging
- Use real UUIDs in all test data and mock responses.
- If you see errors about user ID types, check that you are passing UUID strings, not numbers.
- If you get 401 Unauthorized, ensure the JWT is present, valid, and not expired.

---

### Example: Making an Authenticated API Request
```js
const token = localStorage.getItem('jwt');
const response = await fetch('/api/cv', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  },
});
```

---

**Summary:**
- Always use UUIDs for user IDs (as strings).
- Always send the JWT in the Authorization header.
- Extract the user ID from the JWT payload for user-specific logic.
- Test with real UUIDs and valid JWTs. 