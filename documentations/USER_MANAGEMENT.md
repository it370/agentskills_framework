# User Management System

The AgentSkills Framework now includes a comprehensive user management system with authentication, authorization, and password management.

## Features

1. **User Registration**: Basic registration with username, email, and password
2. **User Login**: JWT-based authentication with session tracking
3. **Password Reset**: Email-based password reset with secure tokens
4. **Password Encryption**: All passwords stored as bcrypt hashes
5. **User Tracking**: All system actions logged against user_id
6. **Access Control**: Users can only access their own workflow runs
7. **Admin Privileges**: Admin users can view all runs

## Setup

### 1. Install Dependencies

```bash
# Activate conda environment
conda activate clearstar

# Install new dependencies
pip install bcrypt pyjwt[crypto]
```

### 2. Apply Database Schema

```bash
python db/apply_user_schema.py
```

This will:
- Create users, password_reset_tokens, and user_sessions tables
- Add user_id column to run_metadata and logs tables
- Create a default 'system' admin user with a random password

**IMPORTANT**: The script will output a default password for the system user. Save this and change it immediately!

### 3. Configure Environment Variables

Add to your `.env` file:

```env
# JWT Configuration (REQUIRED)
JWT_SECRET=your_secure_random_secret_here_min_32_chars
JWT_EXPIRY_HOURS=24  # Optional, defaults to 24

# SMTP Configuration (OPTIONAL - for password reset emails)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=AgentSkills Framework

# Application URL (for email links)
APP_URL=http://localhost:3000
```

To generate a secure JWT secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 4. Restart the Application

```bash
python main.py
```

## API Endpoints

### Authentication Endpoints

#### Register a New User

```http
POST /auth/register
Content-Type: application/json

{
  "username": "johndoe",
  "email": "john@example.com",
  "password": "SecurePass123"
}
```

**Password Requirements**:
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit

**Response**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "johndoe",
    "email": "john@example.com",
    "is_active": true,
    "is_admin": false,
    "created_at": "2026-01-14T10:30:00Z",
    "last_login_at": "2026-01-14T10:30:00Z"
  }
}
```

#### Login

```http
POST /auth/login
Content-Type: application/json

{
  "username": "johndoe",
  "password": "SecurePass123"
}
```

**Response**: Same as registration

#### Get Current User Profile

```http
GET /auth/me
Authorization: Bearer eyJ0eXAiOiJKV1...
```

**Response**:
```json
{
  "id": 1,
  "username": "johndoe",
  "email": "john@example.com",
  "is_active": true,
  "is_admin": false,
  "created_at": "2026-01-14T10:30:00Z",
  "last_login_at": "2026-01-14T10:30:00Z"
}
```

#### Logout

```http
POST /auth/logout
Authorization: Bearer eyJ0eXAiOiJKV1...
```

**Response**:
```json
{
  "message": "Logged out successfully"
}
```

#### Request Password Reset

```http
POST /auth/password-reset-request
Content-Type: application/json

{
  "email": "john@example.com"
}
```

**Response**:
```json
{
  "message": "If the email exists, a password reset link has been sent."
}
```

**Note**: For security, the response is always the same regardless of whether the email exists.

#### Reset Password

```http
POST /auth/password-reset
Content-Type: application/json

{
  "token": "token_from_email",
  "new_password": "NewSecurePass456"
}
```

**Response**:
```json
{
  "message": "Password reset successfully. Please log in with your new password."
}
```

#### Verify Token

```http
POST /auth/verify-token
Authorization: Bearer eyJ0eXAiOiJKV1...
```

Returns user info if token is valid, 401 if invalid.

### Workflow Endpoints (Now Authenticated)

All workflow endpoints now require authentication. Include the JWT token in the Authorization header:

```http
Authorization: Bearer eyJ0eXAiOiJKV1...
```

#### Start Workflow

```http
POST /start
Authorization: Bearer eyJ0eXAiOiJKV1...
Content-Type: application/json

{
  "thread_id": "thread_abc123",
  "sop": "Process customer order",
  "initial_data": {
    "order_id": "12345"
  },
  "run_name": "Customer Order Processing"
}
```

#### Get Status

```http
GET /status/thread_abc123
Authorization: Bearer eyJ0eXAiOiJKV1...
```

**Access Control**: Users can only view their own runs. Admins can view all runs.

#### Approve HITL Step

```http
POST /approve/thread_abc123
Authorization: Bearer eyJ0eXAiOiJKV1...
Content-Type: application/json

{
  "approved": true
}
```

#### List Runs

```http
GET /admin/runs?limit=50
Authorization: Bearer eyJ0eXAiOiJKV1...
```

**Access Control**: Returns only the user's runs. Admins see all runs.

#### Rerun Workflow

```http
POST /rerun/thread_abc123
Authorization: Bearer eyJ0eXAiOiJKV1...
```

**Access Control**: Can only rerun your own workflows.

## Database Schema

### users

Stores user accounts:

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| username | VARCHAR(255) | Unique username |
| email | VARCHAR(255) | Unique email |
| password_hash | VARCHAR(255) | Bcrypt hashed password |
| is_active | BOOLEAN | Account active status |
| is_admin | BOOLEAN | Admin privileges |
| created_at | TIMESTAMP | Account creation time |
| updated_at | TIMESTAMP | Last update time |
| last_login_at | TIMESTAMP | Last successful login |
| metadata | JSONB | Additional metadata |

### password_reset_tokens

Stores password reset tokens:

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| user_id | BIGINT | User reference |
| token | VARCHAR(255) | Unique reset token |
| expires_at | TIMESTAMP | Token expiration (1 hour) |
| used | BOOLEAN | Whether token has been used |
| created_at | TIMESTAMP | Token creation time |

### user_sessions

Tracks active JWT sessions:

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| user_id | BIGINT | User reference |
| token_jti | VARCHAR(255) | JWT ID (for revocation) |
| expires_at | TIMESTAMP | Session expiration |
| created_at | TIMESTAMP | Session creation time |
| last_used_at | TIMESTAMP | Last activity time |
| ip_address | VARCHAR(45) | Client IP address |
| user_agent | TEXT | Client user agent |

### run_metadata (Updated)

Now includes user tracking:

| Column | Type | Description |
|--------|------|-------------|
| user_id | BIGINT | User who started the run |
| ... | ... | (existing columns) |

### thread_logs (Updated)

Now includes user tracking:

| Column | Type | Description |
|--------|------|-------------|
| user_id | BIGINT | User who owns the thread |
| ... | ... | (existing columns) |

## Security Features

### Password Security

- **Bcrypt Hashing**: All passwords are hashed using bcrypt with automatic salting
- **Strong Password Requirements**: Enforced at registration and password reset
- **Password History**: Old password hashes are permanently replaced on change

### JWT Token Security

- **HS256 Algorithm**: Industry-standard JWT signing
- **Expiration**: Tokens expire after configurable time (default 24 hours)
- **JTI Tracking**: Each token has a unique ID for revocation
- **Session Tracking**: All active sessions are stored for auditing

### Session Management

- **Automatic Cleanup**: Expired sessions and reset tokens are cleaned up
- **Token Revocation**: Logout invalidates the JWT token immediately
- **Force Logout**: Password reset invalidates all user sessions

### Access Control

- **User Isolation**: Users can only access their own workflow runs
- **Admin Override**: Admin users can access all runs
- **Ownership Checks**: All endpoints verify ownership before allowing access

## Admin Features

### Creating Admin Users

Admin users can be created in two ways:

1. **During Registration** (requires database update):
```sql
UPDATE users SET is_admin = TRUE WHERE username = 'johndoe';
```

2. **Via Environment** (for system user):
The default 'system' user is created as admin.

### Admin Privileges

Admin users can:
- View all workflow runs from all users
- Access logs for any run
- Monitor system-wide statistics

## Password Reset Email Configuration

### Brevo (Recommended)

**Brevo** (formerly Sendinblue) is a professional email service provider with excellent deliverability and a generous free tier.

#### Setup Steps:

1. **Create Brevo Account**: Sign up at https://app.brevo.com/account/register

2. **Get SMTP Credentials**:
   - Go to: https://app.brevo.com/settings/keys/smtp
   - Copy your SMTP key (this is your SMTP password)
   - Your username is your Brevo login email

3. **Configure in .env**:
```env
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=your-email@example.com
SMTP_PASSWORD=your-brevo-smtp-key
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=AgentSkills Framework
```

#### Verify Sender Domain (Optional but Recommended)

For better deliverability, verify your domain:
1. Go to: https://app.brevo.com/settings/senders
2. Add your domain
3. Add the provided DNS records (SPF, DKIM)

#### Brevo Free Tier

- 300 emails/day (9,000/month)
- Perfect for password reset emails
- Excellent deliverability
- No credit card required

### Gmail Configuration

For Gmail, you'll need an **App Password**:

1. Enable 2-Factor Authentication on your Google account
2. Go to: https://myaccount.google.com/apppasswords
3. Generate an app password for "Mail"
4. Use this password in `SMTP_PASSWORD` (not your regular password)

Example configuration:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=AgentSkills Framework
```

### Other Email Providers

#### Brevo (Formerly Sendinblue) - Recommended

Brevo offers reliable SMTP with excellent deliverability:

```env
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=your-brevo-email@example.com
SMTP_PASSWORD=your-brevo-smtp-key
SMTP_FROM_EMAIL=noreply@yourdomain.com
```

**Free Tier**: 300 emails/day  
**Get SMTP Key**: https://app.brevo.com/settings/keys/smtp

#### SendGrid

Use SMTP relay with API key:

```env
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=your-sendgrid-api-key
SMTP_FROM_EMAIL=noreply@yourdomain.com
```

**Free Tier**: 100 emails/day  
**Get API Key**: https://app.sendgrid.com/settings/api_keys

#### AWS SES

Use SES SMTP credentials:

```env
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USERNAME=your-ses-smtp-username
SMTP_PASSWORD=your-ses-smtp-password
SMTP_FROM_EMAIL=noreply@yourdomain.com
```

**Pricing**: $0.10 per 1,000 emails  
**Setup**: https://docs.aws.amazon.com/ses/latest/dg/smtp-credentials.html

#### Mailgun

Use Mailgun SMTP server:

```env
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USERNAME=postmaster@your-domain.mailgun.org
SMTP_PASSWORD=your-mailgun-smtp-password
SMTP_FROM_EMAIL=noreply@yourdomain.com
```

**Free Tier**: First month free (then pay-as-you-go)  
**Setup**: https://app.mailgun.com/app/sending/domains

#### Office 365

Use Office 365 SMTP:

```env
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USERNAME=your-email@company.com
SMTP_PASSWORD=your-office365-password
SMTP_FROM_EMAIL=noreply@company.com
```

**Note**: May require app-specific password if 2FA is enabled

### SMTP Provider Comparison

| Provider | Free Tier | Reliability | Setup Difficulty | Best For |
|----------|-----------|-------------|------------------|----------|
| **Brevo** | 300/day | Excellent | Easy | Small-medium apps |
| Gmail | Limited | Good | Medium (App Password) | Development only |
| SendGrid | 100/day | Excellent | Easy | Production apps |
| AWS SES | Pay-as-you-go | Excellent | Medium | AWS infrastructure |
| Mailgun | Free trial | Excellent | Medium | Developer-focused |
| Office 365 | Included | Good | Easy | Enterprise |

### Recommendation

For production use, we recommend **Brevo** (formerly Sendinblue) because:
- ✅ Generous free tier (300 emails/day)
- ✅ Excellent deliverability
- ✅ Easy setup (no domain verification required to start)
- ✅ Professional email service
- ✅ Good documentation and support

## Troubleshooting

### "JWT_SECRET not set"

Set the JWT_SECRET in your `.env` file:

```env
JWT_SECRET=your_secure_random_secret_here
```

### "Email service not configured"

Password reset requires SMTP configuration. If not configured, password reset will return a 503 error.

### "Invalid or expired token"

- Token may have expired (default 24 hours)
- User may have logged out
- Password may have been changed (invalidates all sessions)

### "Not authorized to access this run"

Users can only access their own runs. Either:
- Use the correct user token
- Make the user an admin
- Check ownership in the database

## Migration from Old System

The old system used a global DEFAULT_USER_ID. To migrate:

1. Apply the new schema using `db/apply_user_schema.py`
2. Update existing runs to assign to system user:

```sql
-- Assign all existing runs to system user
UPDATE run_metadata 
SET user_id = (SELECT id FROM users WHERE username = 'system')
WHERE user_id IS NULL;
```

3. Update frontend to use authentication:
   - Add login/register forms
   - Store JWT token in localStorage
   - Include token in all API requests
   - Handle 401 errors (redirect to login)

## Frontend Integration Example

### Login Flow

```typescript
// Login
const response = await fetch('/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username, password })
});

const data = await response.json();
if (response.ok) {
  // Store token
  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('user', JSON.stringify(data.user));
}
```

### Authenticated Requests

```typescript
// Make authenticated request
const token = localStorage.getItem('access_token');
const response = await fetch('/start', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify(workflowData)
});

if (response.status === 401) {
  // Token expired, redirect to login
  localStorage.clear();
  window.location.href = '/login';
}
```

### Logout

```typescript
// Logout
const token = localStorage.getItem('access_token');
await fetch('/auth/logout', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

localStorage.clear();
window.location.href = '/login';
```

## Best Practices

1. **Always use HTTPS in production** to protect JWT tokens in transit
2. **Set a strong JWT_SECRET** (minimum 32 characters, random)
3. **Configure JWT_EXPIRY_HOURS** appropriately (24 hours is reasonable)
4. **Enable SMTP** for password reset functionality
5. **Regularly clean up expired sessions** (the system does this automatically)
6. **Monitor user sessions** for suspicious activity
7. **Use environment-specific secrets** (different JWT_SECRET per environment)
8. **Implement rate limiting** for login and password reset endpoints
9. **Log authentication events** for security auditing
10. **Regularly backup the users table** (contains critical authentication data)

## Security Considerations

- JWT tokens contain user claims but are not encrypted (only signed)
- Store JWT_SECRET securely (never commit to version control)
- Implement additional rate limiting for production
- Consider adding 2FA for admin accounts
- Monitor failed login attempts
- Implement account lockout after N failed attempts
- Add email verification for new registrations
- Consider implementing refresh tokens for long-lived sessions
