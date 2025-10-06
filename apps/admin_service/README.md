# Admin Dashboard Service

Admin panel for managing users, credits, and viewing analytics for the CandidateV platform.

## Features

### Phase 1 (MVP) ✅
- ✅ Admin authentication (login/logout)
- ✅ User management (list, view details, search)
- ✅ Credit management (add/remove credits with reason)
- ✅ Credit transaction history
- ✅ Career arc viewer (view user profiles)
- ✅ User activity tracking (CVs, applications)
- ✅ Basic analytics dashboard
- ✅ Audit logs for all admin actions
- ✅ Role-based access control (super_admin, admin, support)

### Phase 2 (Planned)
- [ ] Advanced analytics with charts
- [ ] Support ticket system
- [ ] System configuration (pricing, feature flags)
- [ ] Promotional code management
- [ ] User impersonation for debugging
- [ ] Bulk operations

## API Endpoints

### Authentication
- `POST /admin/auth/login` - Admin login
- `POST /admin/auth/logout` - Admin logout
- `GET /admin/auth/me` - Get current admin info
- `POST /admin/auth/create` - Create new admin (super admin only)

### User Management
- `GET /admin/users/` - List all users (with pagination & search)
- `GET /admin/users/{user_id}` - Get user details
- `GET /admin/users/{user_id}/profile` - View user career arc
- `POST /admin/users/{user_id}/credits` - Adjust user credits
- `GET /admin/users/{user_id}/credits/history` - View credit history
- `GET /admin/users/{user_id}/activity` - View user activity (CVs, applications)

### Analytics
- `GET /admin/analytics/summary` - Get analytics summary

## Setup

### 1. Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Admin JWT Secret
ADMIN_JWT_SECRET=your-secret-key-here

# External Services
USER_SERVICE_URL=http://user-service:8080
ARC_SERVICE_URL=http://arc-service:8080
CV_SERVICE_URL=http://cv-service:8080
```

### 2. Create Super Admin

After deploying the service, create the first super admin:

```bash
python create_super_admin.py
```

This will prompt you for:
- Email
- Name
- Password

### 3. Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
uvicorn app.main:app --reload --port 8080
```

### 4. Run with Docker

```bash
docker build -t admin-service .
docker run -p 8080:8080 \
  -e DATABASE_URL=your_db_url \
  -e ADMIN_JWT_SECRET=your_secret \
  admin-service
```

## Security

### Admin Roles

1. **super_admin**: Full access, can create other admins
2. **admin**: Can view and edit users, credits, view analytics
3. **support**: Read-only access to user data (not yet implemented)

### Authentication

- JWT tokens with 8-hour expiration
- Bcrypt password hashing
- All admin actions are logged in audit trail

### Audit Trail

All admin actions are logged with:
- Admin ID and email
- Action performed
- Resource affected
- Timestamp
- IP address
- Additional details (JSON)

## Credit Management

### Adjust Credits

```json
POST /admin/users/{user_id}/credits
{
  "amount": 10,  // Positive to add, negative to deduct
  "reason": "Refund",  // Refund, Promo, Support, Correction, Violation
  "notes": "Refund for technical issue"  // Optional
}
```

### Reason Codes

- **Refund**: Customer refund for service issues
- **Promo**: Promotional credit bonus
- **Support**: Support ticket resolution
- **Correction**: Admin correction for errors
- **Violation**: Deduction for policy violations

## Integration with Other Services

The admin service integrates with:

1. **User Service**: Fetch user data, adjust credits
2. **ARC Service**: View user career profiles
3. **CV Service**: View CVs, applications, activity

## Database Schema

### Tables

1. **admins**: Admin user accounts
2. **credit_transactions**: Credit adjustment history
3. **admin_audit_logs**: Audit trail for all admin actions

## API Documentation

Once the service is running, visit:
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`

## Development

### Adding New Admin Endpoints

1. Create a new router in `app/routers/`
2. Add audit logging for sensitive actions
3. Use `Depends(get_current_admin)` for authentication
4. Use `Depends(require_super_admin)` for super admin-only actions
5. Register the router in `app/main.py`

### Testing

```bash
# Test admin login
curl -X POST http://localhost:8080/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "your_password"}'

# Test user list (with token)
curl -X GET http://localhost:8080/admin/users/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Deployment

### Railway

1. Add admin service to Railway
2. Set environment variables
3. Connect to the same database as other services
4. Deploy
5. Run `create_super_admin.py` to create first admin

### Environment Variables in Railway

```
DATABASE_URL=postgresql://...
ADMIN_JWT_SECRET=random_secret_key_here
USER_SERVICE_URL=https://user-service.railway.app
ARC_SERVICE_URL=https://arc-service.railway.app
CV_SERVICE_URL=https://cv-service.railway.app
```

## Support

For issues or questions, contact the development team.

