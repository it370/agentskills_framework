# Changelog - User Management System

## Version 2.0.0 - User Management Update (2026-01-14)

### Major Changes

#### New Features
- **User Authentication System**: Complete JWT-based authentication with registration, login, and logout
- **Password Management**: Secure password storage with bcrypt hashing and email-based password reset
- **User Tracking**: All workflow runs and logs now associated with user_id
- **Access Control**: Users can only access their own runs; admins can access all runs
- **Admin Privileges**: Admin users can view system-wide data
- **Email Integration**: Password reset emails with secure tokens

#### Database Changes
- **New Tables**:
  - `users` - User accounts with encrypted passwords
  - `password_reset_tokens` - Password reset token management
  - `user_sessions` - Active JWT session tracking
  
- **Modified Tables**:
  - `run_metadata` - Added `user_id` column
  - `thread_logs` - Added `user_id` column support

#### API Changes
- **New Endpoints**:
  - `POST /auth/register` - User registration
  - `POST /auth/login` - User login
  - `POST /auth/logout` - User logout
  - `GET /auth/me` - Get current user profile
  - `POST /auth/password-reset-request` - Request password reset
  - `POST /auth/password-reset` - Reset password with token
  - `POST /auth/verify-token` - Verify JWT token

- **Modified Endpoints** (now require authentication):
  - `POST /start` - Start workflow (requires auth token)
  - `GET /status/{thread_id}` - Get workflow status (requires auth + ownership)
  - `POST /approve/{thread_id}` - Approve HITL step (requires auth + ownership)
  - `GET /admin/runs` - List runs (filtered by user, or all for admins)
  - `GET /admin/runs/{thread_id}` - Get run details (requires ownership)
  - `GET /admin/runs/{thread_id}/logs` - Get logs (requires ownership)
  - `GET /admin/runs/{thread_id}/metadata` - Get metadata (requires ownership)
  - `POST /rerun/{thread_id}` - Rerun workflow (requires ownership)

#### New Dependencies
- `bcrypt` - Password hashing
- `pyjwt[crypto]` - JWT token generation and validation

#### New Configuration
- `JWT_SECRET` (required) - Secret key for JWT signing
- `JWT_EXPIRY_HOURS` (optional, default 24) - JWT token expiration time
- `SMTP_HOST` (optional) - SMTP server for password reset emails
- `SMTP_PORT` (optional) - SMTP port
- `SMTP_USERNAME` (optional) - SMTP username
- `SMTP_PASSWORD` (optional) - SMTP password
- `SMTP_FROM_EMAIL` (optional) - From email address
- `SMTP_FROM_NAME` (optional) - From name
- `APP_URL` (optional) - Application URL for email links

### Breaking Changes

#### Authentication Required
All API endpoints now require authentication via JWT token. Previously, endpoints used a global `DEFAULT_USER_ID` from environment variables.

**Migration Path**:
1. Apply database migrations: `python db/apply_user_schema.py`
2. Set `JWT_SECRET` in `.env`
3. Register users via `/auth/register`
4. Update API clients to include `Authorization: Bearer <token>` header
5. Optionally assign existing runs to users:
   ```sql
   UPDATE run_metadata 
   SET user_id = (SELECT id FROM users WHERE username = 'system')
   WHERE user_id IS NULL;
   ```

#### Deprecated Configuration
- `DEFAULT_USER_ID` - No longer used (use JWT authentication)
- `DEFAULT_USER_ADMIN` - No longer used (use database `is_admin` flag)

### New Files

#### Database Scripts
- `db/users_schema.sql` - User management schema
- `db/add_user_tracking_migration.sql` - Migration for user tracking
- `db/apply_user_schema.py` - Migration script

#### Services
- `services/user_service.py` - User management business logic
- `services/email_service.py` - Email sending service
- `services/auth_middleware.py` - FastAPI authentication middleware

#### API
- `api/auth_api.py` - Authentication API endpoints

#### Documentation
- `documentations/USER_MANAGEMENT.md` - Complete user management guide
- `documentations/USER_MANAGEMENT_SUMMARY.md` - Implementation summary
- `QUICKSTART_USER_MANAGEMENT.md` - Quick start guide
- `env.example` - Environment variables template

### Modified Files

#### Core Application
- `api/main.py` - Added authentication to all endpoints, user tracking
- `requirements.txt` - Added bcrypt and pyjwt dependencies

### Security Improvements
- **Password Security**: Bcrypt hashing with automatic salting (replaces plain text)
- **Token Security**: JWT with HS256 signing algorithm
- **Session Management**: Token revocation on logout
- **Access Control**: Row-level security for workflow runs
- **Audit Trail**: User tracking for all actions

### Performance Impact
- Minimal overhead from authentication checks
- Efficient JWT validation without database lookups
- Indexed user_id columns for fast filtering
- Session tracking for audit purposes

### Backward Compatibility
- Existing workflows continue to work
- API structure remains the same (added auth requirement)
- Database schema extends existing tables (no data loss)
- Default 'system' user created for backward compatibility

### Upgrade Instructions

1. **Backup Database**:
   ```bash
   pg_dump agentskills > backup_before_user_mgmt.sql
   ```

2. **Install Dependencies**:
   ```bash
   conda activate clearstar
   pip install bcrypt pyjwt[crypto]
   ```

3. **Apply Database Migrations**:
   ```bash
   python db/apply_user_schema.py
   ```
   
   Save the default 'system' user password!

4. **Configure Environment**:
   ```bash
   # Generate JWT secret
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   
   # Add to .env
   echo "JWT_SECRET=<generated_secret>" >> .env
   ```

5. **Restart Application**:
   ```bash
   python main.py
   ```

6. **Register Users**:
   ```bash
   curl -X POST http://localhost:8000/auth/register \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","email":"admin@example.com","password":"AdminPass123"}'
   ```

7. **Update Frontend** (if applicable):
   - Add login/register forms
   - Store JWT token
   - Include Authorization header in all requests
   - Handle 401 errors (redirect to login)

### Testing

Run the migration script with test database:
```bash
export DATABASE_URL=postgresql://user:pass@localhost/test_db
python db/apply_user_schema.py
```

Test authentication:
```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"TestPass123"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"TestPass123"}'

# Use token
TOKEN="<token_from_login>"
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### Known Issues
None at this time.

### Future Enhancements
- Email verification for new accounts
- Two-factor authentication (2FA)
- OAuth integration (Google, GitHub, etc.)
- Rate limiting for login attempts
- Account lockout after failed attempts
- Refresh token support
- User management admin UI
- Role-based access control (RBAC)
- API key authentication for service accounts
- Session management UI

### Contributors
- Implementation: AI Assistant
- Review: Pending

### References
- [USER_MANAGEMENT.md](documentations/USER_MANAGEMENT.md) - Full documentation
- [QUICKSTART_USER_MANAGEMENT.md](QUICKSTART_USER_MANAGEMENT.md) - Quick start guide
- [JWT RFC](https://datatracker.ietf.org/doc/html/rfc7519) - JWT specification
- [OWASP](https://owasp.org/www-project-web-security-testing-guide/) - Security best practices

---

## Version 1.x (Previous)

Previous versions used a simple DEFAULT_USER_ID environment variable for user identification without authentication.
