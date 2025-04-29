# Auth Service Developer Guide: Using UUIDs for User IDs and JWTs

## 1. Use UUIDs for User IDs
- The users table (and any related tables) should use UUIDs as the primary key for users, not integers.
- When creating a new user, generate a UUID (e.g., using Python's `uuid.uuid4()` or the equivalent in your stack).

## 2. Issue JWTs with UUID User IDs
- When generating JWTs (for login, registration, etc.), include the user's UUID in the payload.
- The field should be named `id` or `user_id` (ideally both for compatibility, but at least one).
  - Example payload:
    ```json
    {
      "id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
      "email": "user@example.com",
      "iat": 1745879761,
      "exp": 1745881561
    }
    ```
- Do **not** use integer IDs in the JWT payload.

## 3. Consistency Across Services
- Ensure that all services (auth, CV, AI, payments, etc.) expect and use UUIDs for user identification.
- If you have existing users with integer IDs, migrate them to UUIDs and update all references.

## 4. Token Verification
- Make sure the JWT is signed with the correct secret and algorithm (`HS256` by default, or as configured in your environment).
- The CV service will accept either `id` or `user_id` in the JWT payload, but you should standardize on one for long-term consistency.

## 5. Testing
- Provide a way to generate test JWTs with UUID user IDs for integration testing.
- Confirm that a user can register, log in, and receive a JWT with a UUID as their user ID.

---

### Optional: Example Code Snippet (Python)
```python
import uuid
import jwt
from datetime import datetime, timedelta

user_id = str(uuid.uuid4())
payload = {
    "id": user_id,
    "email": "user@example.com",
    "iat": int(datetime.utcnow().timestamp()),
    "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
}
token = jwt.encode(payload, "your_jwt_secret", algorithm="HS256")
```

---

**Summary:**
- Use UUIDs for user IDs everywhere.
- JWTs must include the user's UUID as `id` or `user_id`.
- No integer user IDs in tokens or DB.
- Test with real UUIDs. 