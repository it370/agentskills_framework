# Brevo SMTP - Quick Reference Card

## 🚀 5-Minute Setup

### 1. Get Brevo Account
- Sign up: https://app.brevo.com/account/register
- Verify your email
- Skip onboarding (optional steps)

### 2. Get SMTP Credentials
- Go to: https://app.brevo.com/settings/keys/smtp
- Click "Generate a new SMTP key"
- Copy your SMTP key

### 3. Configure .env
```env
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=your-brevo-login-email@example.com
SMTP_PASSWORD=your-brevo-smtp-key
SMTP_FROM_EMAIL=noreply@yourdomain.com
SMTP_FROM_NAME=AgentSkills Framework
```

### 4. Test
```bash
python db/test_user_management.py
```

## ✅ What You Get (Free Tier)

- ✅ **300 emails/day** (9,000/month)
- ✅ **Excellent deliverability**
- ✅ **Professional email templates**
- ✅ **Detailed analytics**
- ✅ **No credit card required**
- ✅ **No domain verification needed** (to start)

## 📧 SMTP Settings

| Setting | Value |
|---------|-------|
| Host | `smtp-relay.brevo.com` |
| Port | `587` (TLS/STARTTLS) |
| Username | Your Brevo login email |
| Password | Your SMTP key (not account password!) |
| From Email | Any email (your@domain.com recommended) |

## 🧪 Test Email

```bash
# Request password reset (sends email)
curl -X POST http://localhost:8000/auth/password-reset-request \
  -H "Content-Type: application/json" \
  -d '{"email": "your-real-email@example.com"}'
```

Check your inbox!

## 🔍 Troubleshooting

### Email not sending?

1. **Check credentials**: https://app.brevo.com/settings/keys/smtp
2. **Check logs**: Look for "Email service configured" in terminal
3. **Test SMTP**: `telnet smtp-relay.brevo.com 587`

### Email goes to spam?

1. **Verify domain**: https://app.brevo.com/settings/senders
2. **Use real domain**: Change `SMTP_FROM_EMAIL` to your domain
3. **Add SPF/DKIM**: Follow Brevo's DNS setup guide

### Rate limit?

- Free tier: 300 emails/day
- Check usage: https://app.brevo.com/statistics/email
- Upgrade if needed: Starting at $25/month

## 📊 Monitor Email Delivery

- **Dashboard**: https://app.brevo.com/dashboard
- **Email Logs**: https://app.brevo.com/logs/transactional
- **Statistics**: https://app.brevo.com/statistics/email

## 💡 Pro Tips

1. **Use your domain**: `noreply@yourdomain.com` instead of `noreply@gmail.com`
2. **Verify domain** (optional): Better deliverability, removes "via brevo.com"
3. **Test first**: Send to your own email before production
4. **Monitor stats**: Check bounce rates weekly
5. **Keep key secure**: Never commit `.env` to git

## 🆚 Brevo vs Others

| Provider | Free Tier | Best For |
|----------|-----------|----------|
| **Brevo** | 300/day | ✅ Recommended - Easy setup |
| Gmail | Limited | Development only |
| SendGrid | 100/day | Alternative option |
| AWS SES | Pay-as-you-go | AWS users |

## 📚 Resources

- **Setup Guide**: `documentations/BREVO_SMTP_SETUP.md`
- **Brevo Help**: https://help.brevo.com/
- **SMTP Docs**: https://developers.brevo.com/docs/send-emails-via-smtp
- **Get SMTP Key**: https://app.brevo.com/settings/keys/smtp

## 🎯 Common Use Cases

### Password Reset (Default)
```bash
# User requests reset
POST /auth/password-reset-request
{"email": "user@example.com"}

# Email sent with reset link
# Link expires in 1 hour
```

### Welcome Email (Optional)
```python
# Sent automatically after registration
# Can be customized in services/email_service.py
```

## 🔐 Security

- ✅ SMTP key != Account password
- ✅ Regenerate keys periodically
- ✅ Use different keys for dev/prod
- ✅ Monitor for suspicious activity
- ✅ Enable 2FA on Brevo account

## 📞 Support

- **Email**: contact@brevo.com
- **Help Center**: https://help.brevo.com/
- **Community**: https://community.brevo.com/
- **Status**: https://status.brevo.com/

---

**Need Help?** Check the full guide: `documentations/BREVO_SMTP_SETUP.md`
