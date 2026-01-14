# User Authentication & Management - Complete Guide

**Status**: ✅ Production Ready  
**Version**: 1.0  
**Last Updated**: 2026-01-14

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Setup & Configuration](#setup--configuration)
5. [API Reference](#api-reference)
6. [Frontend Integration](#frontend-integration)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)
9. [Security](#security)

---

## Quick Start

### 1. Setup Database
```bash
conda activate clearstar
python db/apply_user_schema.py
# Note the generated system admin password
```

### 2. Configure Environment
```bash
# Required in .env
JWT_SECRET=your-secret-key-minimum-32-characters
JWT_EXPIRY_HOURS=24

# Optional (for password reset)
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=your-email@domain.com
SMTP_PASSWORD=your-smtp-key
SMTP_FROM_EMAIL=noreply@yourdomain.com
```

### 3. Start Services
```bash
# Backend
python main.py          # → http://localhost:8000

# Frontend (new terminal)
cd admin-ui
npm run dev            # → http://localhost:3000
```

### 4. Access Application
Open http://localhost:3000 → Auto-redirects to `/login` → Register or use system user

---

## Features

### Implemented
- ✅ User registration (username, email, password)
- ✅ User login with JWT tokens
- ✅ Password hashing with bcrypt
- ✅ Session management with tracking
- ✅ Protected API endpoints
- ✅ User ownership for workflows
- ✅ Admin role support
- ✅ Modern login/registration UI
- ✅ Auto-redirect for protected routes
- ✅ Email service (ready for password reset)

### Coming Soon
- Password reset via email (backend ready)
- User profile management
- Session timeout warnings
- Admin user management UI
- Multi-factor authentication

---

## Architecture

```
┌─────────────────────────────────────────┐
│     Browser (Next.js @ :3000)           │
│  • AuthContext (state)                  │
│  • ProtectedRoute (guard)               │
│  • Login/Register pages                 │
└───────────────┬─────────────────────────┘
                │ JWT in Authorization header
                ▼
┌─────────────────────────────────────────┐
│     FastAPI Backend @ :8000             │
│  • Auth Middleware (JWT verify)         │
│  • User Service (business logic)        │
│  • Email Service (password reset)       │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│     PostgreSQL Database                 │
│  • users                                │
│  • user_sessions                        │
│  • password_reset_tokens                │
│  • run_metadata (+ user_id)             │
│  • logs (+ user_id)                     │
└─────────────────────────────────────────┘
```

---

## Setup & Configuration

### Database Schema

**Apply the schema:**
```bash
python db/apply_user_schema.py
```

**Tables created:**
- `users` - User accounts with bcrypt passwords
- `user_sessions` - JWT session tracking
- `password_reset_tokens` - Password reset tokens
- Updates: `run_metadata` and `logs` get `user_id` column

### Environment Variables

**Required:**
```env
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
JWT_SECRET=generate-with-secrets-token-urlsafe-32
JWT_EXPIRY_HOURS=24
```

**Optional (Email):**
```env
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=your-email@example.com
SMTP_PASSWORD=your-smtp-key
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=AgentSkills
```

**Generate JWT Secret:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## API Reference

### Authentication Endpoints

#### Register
```http
POST /auth/register
Content-Type: application/json

{
  "username": "newuser",
  "email": "user@example.com",
  "password": "StrongPass123"
}

Response: 201 Created
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "newuser",
    "email": "user@example.com",
    "is_active": true,
    "is_admin": false
  }
}
```

#### Login
```http
POST /auth/login
Content-Type: application/json

{
  "username": "newuser",
  "password": "StrongPass123"
}

Response: 200 OK
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": { ... }
}
```

#### Logout
```http
POST /auth/logout
Authorization: Bearer <token>

Response: 200 OK
{
  "message": "Logged out successfully"
}
```

#### Get Current User
```http
GET /auth/me
Authorization: Bearer <token>

Response: 200 OK
{
  "id": 1,
  "username": "newuser",
  "email": "user@example.com",
  "is_active": true,
  "is_admin": false
}
```

#### Verify Token
```http
GET /auth/verify-token
Authorization: Bearer <token>

Response: 200 OK
{
  "valid": true
}
```

#### Password Reset Request
```http
POST /auth/password-reset-request
Content-Type: application/json

{
  "email": "user@example.com"
}

Response: 200 OK
{
  "message": "Password reset email sent"
}
```

#### Reset Password
```http
POST /auth/password-reset
Content-Type: application/json

{
  "token": "reset-token-from-email",
  "new_password": "NewStrongPass123"
}

Response: 200 OK
{
  "message": "Password reset successful"
}
```

### Protected Endpoints

All workflow and admin endpoints now require authentication:

```http
GET /admin/runs
Authorization: Bearer <token>

GET /admin/runs/{thread_id}
Authorization: Bearer <token>

POST /approve/{thread_id}
Authorization: Bearer <token>

POST /rerun/{thread_id}
Authorization: Bearer <token>

GET /admin/skills
Authorization: Bearer <token>
```

### Password Requirements
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- Example: `MyPass123`

### Username Requirements
- 3-255 characters
- Alphanumeric with optional `_` or `-`

---

## Frontend Integration

### File Structure

```
admin-ui/src/
├── lib/
│   ├── auth.ts              # Token storage utilities
│   └── api.ts               # API client (updated)
├── contexts/
│   └── AuthContext.tsx      # Auth state management
├── components/
│   ├── ProtectedRoute.tsx   # Route guard
│   └── DashboardLayout.tsx  # User menu + logout
└── app/
    ├── layout.tsx           # AuthProvider wrapper
    ├── login/page.tsx       # Login page
    ├── register/page.tsx    # Registration page
    └── page.tsx             # Protected dashboard
```

### Using Authentication

**Protect a page:**
```tsx
import ProtectedRoute from "@/components/ProtectedRoute";
import DashboardLayout from "@/components/DashboardLayout";

export default function MyPage() {
  return (
    <ProtectedRoute>
      <DashboardLayout>
        {/* Your content */}
      </DashboardLayout>
    </ProtectedRoute>
  );
}
```

**Access user info:**
```tsx
import { useAuth } from "@/contexts/AuthContext";

export default function MyComponent() {
  const { user, logout } = useAuth();
  
  return (
    <div>
      <p>Welcome {user?.username}</p>
      {user?.is_admin && <p>Admin features</p>}
      <button onClick={logout}>Logout</button>
    </div>
  );
}
```

**Make authenticated API calls:**
```tsx
import { getAuthHeaders } from "@/lib/auth";

const response = await fetch(`${API_BASE}/api/endpoint`, {
  headers: {
    "Content-Type": "application/json",
    ...getAuthHeaders(),
  },
});
```

---

## Testing

### Backend Tests

**Full test suite:**
```bash
python db/test_user_management.py
```

Expected output:
```
✓ Database schema valid
✓ User service tests passed
✓ Email service configured
✓ API endpoints working
Tests passed: 4/4
```

**Quick registration test:**
```bash
python testscripts/test_register_quick.py
```

**Email service test:**
```bash
python testscripts/test_email_service.py
```

### Frontend Tests

**Build check:**
```bash
cd admin-ui
npm run build
```

**Manual UI testing:**
1. Register new user → Auto-login → Dashboard
2. Logout → Login again → Success
3. Access `/skills` without auth → Redirect to login
4. Refresh page while logged in → Stay logged in

---

## Troubleshooting

### Common Issues

#### Cannot Login
```bash
# Check backend is running
curl http://localhost:8000/health

# Check database connection
psql -d your_db -c "SELECT * FROM users;"

# Verify JWT_SECRET is set
echo $JWT_SECRET
```

#### Token Expired / 401 Errors
- Tokens expire after 24 hours (configurable)
- Logout and login again
- Check JWT_EXPIRY_HOURS in .env
- Verify JWT_SECRET matches between services

#### Frontend Shows "[object Object]" Error
- **Fixed in latest version** - Error handling updated
- Clear browser cache and refresh
- Check browser console for actual error

#### Registration Returns 422
- Password must meet requirements (8+ chars, upper, lower, digit)
- Username must be alphanumeric with optional `_` or `-`
- Email must be valid format
- Check Network tab in DevTools for detailed error

#### Cannot Access Protected Routes
```javascript
// In browser console:
localStorage.clear()
// Then try logging in again
```

#### Port Already in Use
```powershell
# Find process on port 8000
netstat -ano | findstr :8000

# Kill process (replace PID)
taskkill /F /PID <PID>

# Restart backend
python main.py
```

### Debug Commands

```bash
# Check users in database
psql -d your_db -c "SELECT id, username, email, is_admin FROM users;"

# Check active sessions
psql -d your_db -c "SELECT * FROM user_sessions WHERE expires_at > NOW();"

# Test login via curl
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"TestPass123"}'

# Check token in browser
localStorage.getItem('auth_token')
```

---

## Security

### Implemented Security Features

**Password Security:**
- Bcrypt hashing with work factor 12
- Minimum 8 characters
- Complexity requirements enforced
- Never logged or transmitted in plain text

**Token Security:**
- JWT with HS256 or RS256 signing
- Configurable expiry (default 24 hours)
- Session tracking in database
- Logout invalidates token server-side
- Verified on every API request

**API Security:**
- All admin endpoints require authentication
- User ownership checked for workflows
- Admin-only endpoints protected
- CORS configured for allowed origins

**Session Management:**
- IP address and user agent tracked
- Multiple sessions per user supported
- Token expiration enforced
- Auto-logout on token expiry

### Best Practices

1. **Use strong JWT_SECRET** - Minimum 32 characters, randomly generated
2. **Enable HTTPS** - In production, always use SSL/TLS
3. **Configure CORS** - Set specific allowed origins, not `*`
4. **Regular token rotation** - Adjust JWT_EXPIRY_HOURS based on security needs
5. **Monitor sessions** - Check user_sessions table for suspicious activity
6. **Backup database** - Regular backups of user data

---

## File Reference

### Backend Files
```
db/
├── users_schema.sql                    # User tables
├── add_user_tracking_migration.sql     # Migration
├── apply_user_schema.py                # Setup script
└── test_user_management.py             # Test suite

services/
├── user_service.py                     # User logic
├── email_service.py                    # Email sending
└── auth_middleware.py                  # JWT verification

api/
├── auth_api.py                         # Auth endpoints
└── main.py                             # API integration

testscripts/
├── test_email_service.py               # Email tests
└── test_register_quick.py              # Quick registration test
```

### Frontend Files
```
admin-ui/src/
├── lib/
│   ├── auth.ts                         # Auth utilities
│   └── api.ts                          # API client
├── contexts/
│   └── AuthContext.tsx                 # Auth state
├── components/
│   ├── ProtectedRoute.tsx              # Route guard
│   └── DashboardLayout.tsx             # User menu
└── app/
    ├── layout.tsx                      # AuthProvider
    ├── login/page.tsx                  # Login
    └── register/page.tsx               # Registration
```

---

## Database Schema Reference

### users
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_admin BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP
);
```

### user_sessions
```sql
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    jti VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### password_reset_tokens
```sql
CREATE TABLE password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Quick Reference

### Essential Commands
```bash
# Setup
python db/apply_user_schema.py
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Start
python main.py
cd admin-ui && npm run dev

# Test
python db/test_user_management.py
python testscripts/test_register_quick.py

# Debug
netstat -ano | findstr :8000
psql -d your_db -c "SELECT * FROM users;"
```

### Essential URLs
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Login: http://localhost:3000/login
- API Docs: http://localhost:8000/docs

### Essential Environment Variables
```env
DATABASE_URL=postgresql://...
JWT_SECRET=your-secret-key
JWT_EXPIRY_HOURS=24
```

---

## Support & Resources

### Documentation
- This guide (AUTHENTICATION_GUIDE.md) - Complete reference
- BREVO_SMTP_SETUP.md - Email configuration
- QUICKSTART_USER_MANAGEMENT.md - Quick setup guide

### Database Management
```sql
-- Make user admin
UPDATE users SET is_admin = true WHERE username = 'myuser';

-- Deactivate user
UPDATE users SET is_active = false WHERE username = 'myuser';

-- Delete user
DELETE FROM users WHERE username = 'testuser';

-- View active sessions
SELECT u.username, us.* 
FROM user_sessions us
JOIN users u ON us.user_id = u.id
WHERE us.expires_at > NOW();
```

### Health Checks
```bash
# Backend health
curl http://localhost:8000/health

# Test registration
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"Test123"}'

# Frontend accessibility
curl http://localhost:3000
```

---

## Migration Guide

### For Existing Installations

1. **Backup database:**
   ```bash
   pg_dump your_database > backup_before_auth.sql
   ```

2. **Apply user schema:**
   ```bash
   python db/apply_user_schema.py
   ```

3. **Update .env:**
   ```env
   JWT_SECRET=<generate-new-secret>
   JWT_EXPIRY_HOURS=24
   ```

4. **Restart services:**
   ```bash
   python main.py
   cd admin-ui && npm run dev
   ```

5. **Test:**
   ```bash
   python db/test_user_management.py
   ```

6. **Create admin user** (if needed):
   ```sql
   UPDATE users SET is_admin = true WHERE username = 'system';
   ```

---

**Last Updated:** 2026-01-14  
**Version:** 1.0.0  
**Status:** ✅ Production Ready
