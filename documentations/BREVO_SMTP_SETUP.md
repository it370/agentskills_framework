# Brevo (Sendinblue) SMTP Setup Guide

This guide shows you how to configure Brevo for sending password reset emails.

## Why Brevo?

Brevo (formerly Sendinblue) is recommended for the AgentSkills Framework because:

- ✅ **Generous Free Tier**: 300 emails per day (9,000 per month)
- ✅ **Excellent Deliverability**: Professional email infrastructure
- ✅ **Easy Setup**: No domain verification required to start
- ✅ **Reliable**: Used by thousands of businesses worldwide
- ✅ **No Credit Card**: Free tier doesn't require payment info

## Step-by-Step Setup

### 1. Create Brevo Account

1. Go to: https://app.brevo.com/account/register
2. Sign up with your email address
3. Verify your email address
4. Complete the onboarding (skip optional steps)

### 2. Get SMTP Credentials

1. Log in to your Brevo account
2. Go to: **Settings** → **SMTP & API** → **SMTP**
   - Direct link: https://app.brevo.com/settings/keys/smtp
3. You'll see your SMTP credentials:
   - **SMTP Server**: `smtp-relay.brevo.com`
   - **Port**: `587` (recommended) or `25`, `465`, `2525`
   - **Login**: Your Brevo login email
   - **SMTP Key**: Click "Generate a new SMTP key" if you don't have one

### 3. Configure AgentSkills Framework

Add these settings to your `.env` file:

```env
# Brevo SMTP Configuration
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=your-brevo-login-email@example.com
SMTP_PASSWORD=your-brevo-smtp-key-here
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=AgentSkills Framework
```

**Important**: 
- `SMTP_USERNAME` is your Brevo login email
- `SMTP_PASSWORD` is your SMTP key (NOT your account password)
- `SMTP_FROM_EMAIL` can be any email (domain verification optional)

### 4. Test Email Sending

Run the test script:

```bash
python db/test_user_management.py
```

Or test manually:

```bash
# Register a user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "your-real-email@example.com",
    "password": "TestPass123"
  }'

# Request password reset
curl -X POST http://localhost:8000/auth/password-reset-request \
  -H "Content-Type: application/json" \
  -d '{"email": "your-real-email@example.com"}'
```

Check your email inbox for the password reset email!

## Verify Your Domain (Optional but Recommended)

For better deliverability and to remove "via brevo.com" from sender:

### 1. Add Your Domain

1. Go to: **Settings** → **Senders & IP**
   - Direct link: https://app.brevo.com/settings/senders
2. Click "Add a domain or subdomain"
3. Enter your domain (e.g., `yourdomain.com`)

### 2. Add DNS Records

Brevo will provide DNS records to add:

**SPF Record** (TXT):
```
Host: @
Value: v=spf1 include:spf.brevo.com ~all
```

**DKIM Record** (TXT):
```
Host: mail._domainkey
Value: [provided by Brevo]
```

**DMARC Record** (TXT) - Optional:
```
Host: _dmarc
Value: v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com
```

### 3. Verify Domain

1. Add the DNS records to your domain registrar (GoDaddy, Namecheap, Cloudflare, etc.)
2. Wait 24-48 hours for DNS propagation
3. Click "Verify" in Brevo dashboard

## Email Templates

The AgentSkills Framework includes pre-built email templates:

### Password Reset Email

Professional HTML email with:
- Clear reset button
- Clickable link fallback
- Expiration notice (1 hour)
- Security warning

### Welcome Email

Sent after successful registration with:
- Welcome message
- Login link
- Professional branding

## Monitoring & Analytics

Brevo provides detailed analytics:

1. Go to: **Statistics** → **Email**
   - Track delivery rates
   - Monitor opens and clicks
   - View bounce rates

2. Go to: **Logs** → **Email logs**
   - View all sent emails
   - Debug delivery issues
   - Check spam complaints

## Troubleshooting

### Email Not Sending

1. **Check SMTP credentials**:
   ```bash
   # Test connection
   telnet smtp-relay.brevo.com 587
   ```

2. **Verify SMTP key is active**:
   - Go to: https://app.brevo.com/settings/keys/smtp
   - Check key status
   - Regenerate if needed

3. **Check application logs**:
   ```bash
   # Look for email errors
   python main.py
   ```

### Email Goes to Spam

1. **Verify your domain** (see above)
2. **Use a professional sender name**:
   ```env
   SMTP_FROM_EMAIL=noreply@yourdomain.com
   SMTP_FROM_NAME=Your Company Name
   ```
3. **Check Brevo reputation**: Go to Dashboard → Sender reputation

### Rate Limit Reached

Free tier allows 300 emails/day:

1. **Monitor usage**:
   - Go to: Dashboard → Email statistics
   
2. **Upgrade if needed**:
   - Go to: Settings → Plan & Billing
   - Plans start at $25/month for 20,000 emails/month

### Invalid Sender Email

If you see "Invalid sender" error:

1. **Add sender email**:
   - Go to: Settings → Senders & IP
   - Add and verify sender email

2. **Use verified sender**:
   ```env
   SMTP_FROM_EMAIL=verified-email@yourdomain.com
   ```

## Best Practices

### 1. Use Professional Email Addresses

❌ Bad:
```env
SMTP_FROM_EMAIL=noreply@gmail.com
```

✅ Good:
```env
SMTP_FROM_EMAIL=noreply@yourdomain.com
```

### 2. Set Descriptive Sender Name

❌ Bad:
```env
SMTP_FROM_NAME=System
```

✅ Good:
```env
SMTP_FROM_NAME=Your Company Support
```

### 3. Monitor Email Delivery

- Check Brevo dashboard regularly
- Watch for bounce rates > 5%
- Monitor spam complaints

### 4. Test Before Production

- Test with real email addresses
- Check emails in spam folder
- Test on different email providers (Gmail, Outlook, etc.)

### 5. Keep SMTP Key Secure

- Never commit `.env` to git
- Rotate SMTP keys periodically
- Use different keys for dev/prod

## Brevo Free Tier Limits

| Feature | Free Tier | Notes |
|---------|-----------|-------|
| Emails/day | 300 | Resets at midnight UTC |
| Emails/month | ~9,000 | 300 × 30 days |
| Sender addresses | Unlimited | Verification optional |
| Contact list | Unlimited | For marketing emails |
| API calls | Unlimited | For SMTP sending |
| Support | Email only | Upgrade for priority support |

## Upgrading Brevo

If you need more emails:

### Lite Plan - $25/month
- 20,000 emails/month
- No daily limit
- Remove Brevo logo
- Priority support

### Essential Plan - $39/month
- 50,000 emails/month
- Advanced statistics
- A/B testing
- Send time optimization

### Premium Plan - $69/month
- 100,000 emails/month
- Marketing automation
- Landing pages
- Phone support

## Alternative: Brevo API

For higher volume, you can use the Brevo API instead of SMTP:

```python
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

configuration = sib_api_v3_sdk.Configuration()
configuration.api_key['api-key'] = 'your-brevo-api-key'

api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
    to=[{"email": "recipient@example.com"}],
    sender={"email": "noreply@yourdomain.com", "name": "Your Company"},
    subject="Password Reset",
    html_content="<html><body>Reset link: ...</body></html>"
)

try:
    api_response = api_instance.send_transac_email(send_smtp_email)
    print(api_response)
except ApiException as e:
    print("Exception: %s\n" % e)
```

## Support Resources

- **Brevo Help Center**: https://help.brevo.com/
- **SMTP Documentation**: https://developers.brevo.com/docs/send-emails-via-smtp
- **API Documentation**: https://developers.brevo.com/docs
- **Community Forum**: https://community.brevo.com/
- **Status Page**: https://status.brevo.com/

## Quick Reference

### SMTP Settings
```env
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=your-brevo-email@example.com
SMTP_PASSWORD=your-brevo-smtp-key
```

### Test Email Command
```bash
curl -X POST http://localhost:8000/auth/password-reset-request \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
```

### Check SMTP Connection
```bash
telnet smtp-relay.brevo.com 587
```

### View Logs
```bash
# Brevo dashboard
https://app.brevo.com/logs/transactional

# Application logs
tail -f /var/log/agentskills.log
```

## Conclusion

Brevo provides a reliable, free, and easy-to-use SMTP service perfect for the AgentSkills Framework password reset functionality. The generous free tier of 300 emails/day is more than sufficient for most applications.

For production use with higher volume, consider upgrading to a paid plan or implementing the Brevo API for better control and monitoring.
