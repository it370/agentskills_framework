# User Management Quick Start Guide

This guide will help you quickly set up and use the new user management system.

## Prerequisites

- PostgreSQL database running
- Python environment with conda (clearstar environment)
- SMTP server access (optional, for password reset)

## Step 1: Install Dependencies

```bash
# Activate conda environment
conda activate clearstar

# Install new dependencies
pip install bcrypt pyjwt[crypto]
```

## Step 2: Configure Environment

1. Copy `env.example` to `.env`:
```bash
cp env.example .env
```

2. Edit `.env` and set:

```env
# Required: Database URL
DATABASE_URL=postgresql://user:password@localhost:5432/agentskills

# Required: Generate a secure JWT secret
JWT_SECRET=<run command below>
```

Generate JWT secret:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

3. (Optional) Configure SMTP for password reset:

**For Brevo** (recommended):
```env
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=your_brevo_email@example.com
SMTP_PASSWORD=your_brevo_smtp_key
SMTP_FROM_EMAIL=noreply@yourdomain.com
```

Get your SMTP key: https://app.brevo.com/settings/keys/smtp

**For Gmail** (alternative):
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_16_char_app_password
SMTP_FROM_EMAIL=noreply@yourdomain.com
```

Get Gmail App Password: https://myaccount.google.com/apppasswords

## Step 3: Apply Database Schema

```bash
python db/apply_user_schema.py
```

**IMPORTANT**: Save the default 'system' user password shown in output!

## Step 4: Start the Application

```bash
python main.py
```

## Step 5: Register a User

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "email": "john@example.com",
    "password": "SecurePass123"
  }'
```

Response includes JWT token:
```json
{
  "access_token": "eyJ0eXAiOiJKV1...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "johndoe",
    ...
  }
}
```

## Step 6: Use the Token

Include the token in all API requests:

```bash
# Save token
TOKEN="eyJ0eXAiOiJKV1..."

# Start a workflow
curl -X POST http://localhost:8000/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "thread_123",
    "sop": "Process customer order",
    "initial_data": {"order_id": "12345"}
  }'

# Check status
curl -X GET http://localhost:8000/status/thread_123 \
  -H "Authorization: Bearer $TOKEN"

# List your runs
curl -X GET http://localhost:8000/admin/runs \
  -H "Authorization: Bearer $TOKEN"
```

## Common Commands

### Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"johndoe","password":"SecurePass123"}'
```

### Get User Profile
```bash
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### Logout
```bash
curl -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

### Request Password Reset
```bash
curl -X POST http://localhost:8000/auth/password-reset-request \
  -H "Content-Type: application/json" \
  -d '{"email":"john@example.com"}'
```

## Password Requirements

- Minimum 8 characters
- At least one uppercase letter (A-Z)
- At least one lowercase letter (a-z)
- At least one digit (0-9)

Examples:
- ✅ "SecurePass123"
- ✅ "MyPassword1"
- ❌ "password" (no uppercase, no digit)
- ❌ "PASSWORD123" (no lowercase)
- ❌ "Pass1" (too short)

## Making Users Admin

Connect to your database and run:

```sql
UPDATE users SET is_admin = TRUE WHERE username = 'johndoe';
```

## Troubleshooting

### "JWT_SECRET not set"
- Make sure you set `JWT_SECRET` in your `.env` file
- The secret must be at least 32 characters

### "Invalid username or password"
- Check username and password are correct
- Passwords are case-sensitive
- Make sure user account is active

### "Not authorized to access this run"
- You can only access your own runs
- Or make your user an admin to see all runs

### "Email service not configured"
- Password reset requires SMTP configuration
- Set all SMTP_* variables in `.env`
- Or skip password reset functionality

### Token expired
- JWT tokens expire after 24 hours (configurable)
- Login again to get a new token

## API Documentation

Visit http://localhost:8000/docs for interactive API documentation with all endpoints.

## Next Steps

1. **Frontend Integration**: Update your frontend to use the authentication API
2. **Email Setup**: Configure SMTP for password reset emails
3. **Admin Users**: Promote users to admin as needed
4. **Security**: Enable HTTPS in production
5. **Monitoring**: Monitor user sessions and authentication logs

## Full Documentation

For complete documentation, see:
- `documentations/USER_MANAGEMENT.md` - Complete user management guide
- `documentations/USER_MANAGEMENT_SUMMARY.md` - Implementation summary

## Support

If you encounter issues:
1. Check application logs for errors
2. Verify database connection
3. Confirm JWT_SECRET is set
4. Check that database migrations were applied
5. Review the full documentation
