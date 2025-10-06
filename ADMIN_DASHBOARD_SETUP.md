# Admin Dashboard - Quick Start Guide

## 🚀 For Frontend Developers

### Step 1: Verify Backend is Ready

Test that the admin service is running:

```bash
curl https://adminservice-production-551a.up.railway.app/health
# Expected: {"status":"ok","service":"admin"}
```

### Step 2: Get Your Admin Credentials

**⚠️ IMPORTANT:** You need a super admin account to log in. Ask the backend team to create one for you using the `create_super_admin.py` script.

The backend team will provide:
- Email: `your-email@candidate5.co.uk`
- Password: `(temporary password)`

### Step 3: Test Login API

```bash
curl -X POST https://api-gw-production.up.railway.app/api/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your-email@candidate5.co.uk","password":"your-password"}'
```

**Expected Response:**
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "admin": {
    "id": "...",
    "email": "your-email@candidate5.co.uk",
    "name": "Your Name",
    "role": "super_admin",
    "is_active": true
  }
}
```

### Step 4: API Endpoints

All admin endpoints are accessible through the API Gateway:

**Base URL:** `https://api-gw-production.up.railway.app/api/admin`

**Available Endpoints:**

#### Authentication
- `POST /api/admin/auth/login` - Login
- `POST /api/admin/auth/logout` - Logout
- `GET /api/admin/auth/me` - Get current admin user

#### User Management
- `GET /api/admin/users/` - List all users (with pagination & search)
- `GET /api/admin/users/{user_id}` - Get user details
- `POST /api/admin/users/{user_id}/credits` - Adjust user credits
- `GET /api/admin/users/{user_id}/credits/history` - Credit transaction history
- `GET /api/admin/users/{user_id}/profile` - View user's career arc
- `GET /api/admin/users/{user_id}/activity` - View user's CVs and applications

#### Analytics
- `GET /api/admin/analytics/summary` - Dashboard analytics

### Step 5: Authentication Headers

All authenticated requests must include:

```
Authorization: Bearer {access_token}
```

Example:
```typescript
const token = localStorage.getItem('admin_token');
const response = await axios.get('/api/admin/users/', {
  headers: {
    Authorization: `Bearer ${token}`
  }
});
```

---

## 📖 Full Documentation

For detailed integration guide, API schemas, and React examples, see:
- **[ADMIN_DASHBOARD_FRONTEND_GUIDE.md](./ADMIN_DASHBOARD_FRONTEND_GUIDE.md)** - Complete frontend integration guide

---

## 🎨 UI/UX Recommendations

### Pages to Build (in order):

1. **Login Page** (`/admin/login`)
   - Simple email/password form
   - Error handling
   - Redirect to dashboard on success

2. **Dashboard** (`/admin/dashboard`)
   - Analytics cards (total users, active users, CVs generated, etc.)
   - Recent activity feed
   - Quick actions

3. **Users List** (`/admin/users`)
   - Table with: Email, Name, Credits, Subscription Type, Created Date
   - Search bar (searches name and email)
   - Pagination (50 users per page)
   - Click row to view details

4. **User Detail** (`/admin/users/:id`)
   - User info card
   - Credit adjustment form
   - Credit history table
   - Buttons: View Profile, View Activity

5. **Career Arc Viewer** (`/admin/users/:id/profile`)
   - Display user's complete profile (work experience, education, skills)
   - Read-only view

6. **User Activity** (`/admin/users/:id/activity`)
   - List of CVs generated
   - List of applications submitted

---

## 🔒 Security Notes

1. **JWT Token Expiration:** Tokens expire after 8 hours. Handle 401 errors by redirecting to login.
2. **Role-Based Access:** Check `admin.role` for permissions (some actions may be restricted to `super_admin`).
3. **HTTPS Only:** All API calls must use HTTPS.
4. **Token Storage:** Store tokens in `localStorage` or secure cookies.

---

## 🐛 Troubleshooting

### "Application not found" Error
- Make sure you're using the **API Gateway URL**: `https://api-gw-production.up.railway.app`
- Not the direct admin service URL

### 401 Unauthorized
- Token expired (login again)
- Token not included in headers
- Invalid token format (should be `Bearer {token}`)

### 404 Not Found
- Check endpoint path is correct
- Ensure `/api/admin` prefix is included

### CORS Errors
- The backend is configured to allow your frontend domains
- Contact backend team if you need to add a new domain

---

## 🎯 Next Steps

1. ✅ Backend is deployed and ready
2. ⏳ Create super admin account (backend team)
3. ⏳ Build login page
4. ⏳ Build dashboard
5. ⏳ Build user management pages

**Questions?** Contact the backend team or refer to the full guide: [ADMIN_DASHBOARD_FRONTEND_GUIDE.md](./ADMIN_DASHBOARD_FRONTEND_GUIDE.md)

