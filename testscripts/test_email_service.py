"""
Test script for email service

This script sends a test password reset email to verify your SMTP configuration.
Run this after configuring SMTP settings in .env
"""

import os
import sys
import asyncio
from pathlib import Path

import os
import sys
import asyncio
from pathlib import Path

# Add parent directory to path BEFORE importing env_loader
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from env_loader import load_env_once

# Load environment using centralized env loader
load_env_once(project_root)


async def test_email_configuration():
    """Test email service configuration"""
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║                Email Service Test Script                    ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")
    
    # Check if SMTP is configured
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from_email = os.getenv("SMTP_FROM_EMAIL")
    
    if not all([smtp_host, smtp_port, smtp_username, smtp_password, smtp_from_email]):
        print("❌ SMTP not fully configured!")
        print("\nMissing environment variables:")
        if not smtp_host: print("  - SMTP_HOST")
        if not smtp_port: print("  - SMTP_PORT")
        if not smtp_username: print("  - SMTP_USERNAME")
        if not smtp_password: print("  - SMTP_PASSWORD")
        if not smtp_from_email: print("  - SMTP_FROM_EMAIL")
        print("\nPlease configure SMTP settings in .env file")
        print("\nFor Brevo:")
        print("  SMTP_HOST=smtp-relay.brevo.com")
        print("  SMTP_PORT=587")
        print("  SMTP_USERNAME=your-brevo-email@example.com")
        print("  SMTP_PASSWORD=your-brevo-smtp-key")
        print("  SMTP_FROM_EMAIL=noreply@yourdomain.com")
        return False
    
    print("✓ SMTP configuration found\n")
    print(f"  Host: {smtp_host}")
    print(f"  Port: {smtp_port}")
    print(f"  Username: {smtp_username}")
    print(f"  From: {smtp_from_email}")
    print()
    
    # Get email service
    from services.email_service import get_email_service
    
    email_service = get_email_service()
    
    if not email_service:
        print("❌ Email service could not be initialized")
        return False
    
    print("✓ Email service initialized\n")
    
    # Get recipient email
    recipient = input("Enter your email address to receive test email: ").strip()
    
    if not recipient or '@' not in recipient:
        print("❌ Invalid email address")
        return False
    
    print(f"\nSending test email to: {recipient}")
    print("Please wait...\n")
    
    # Send test password reset email
    try:
        await email_service.send_password_reset_email(
            to_email=recipient,
            username="testuser",
            reset_token="test_token_123abc",
            reset_url_base="http://localhost:3000/reset-password"
        )
        
        print("✓ Email sent successfully!\n")
        print("=" * 60)
        print("Check your inbox for:")
        print("  Subject: Password Reset Request - AgentSkills Framework")
        print(f"  To: {recipient}")
        print(f"  From: {smtp_from_email}")
        print("=" * 60)
        print("\nIf you don't see it:")
        print("  1. Check your spam/junk folder")
        print("  2. Verify the email address is correct")
        print("  3. Check Brevo dashboard for delivery status:")
        print("     https://app.brevo.com/logs/transactional")
        print()
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}\n")
        print("Troubleshooting:")
        print("  1. Check your SMTP credentials are correct")
        print("  2. For Brevo, get SMTP key from:")
        print("     https://app.brevo.com/settings/keys/smtp")
        print("  3. Verify SMTP_PASSWORD is your SMTP key (not account password)")
        print("  4. Check Brevo account is active and verified")
        print()
        return False


async def test_welcome_email():
    """Test welcome email"""
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║                Welcome Email Test                           ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")
    
    from services.email_service import get_email_service
    
    email_service = get_email_service()
    
    if not email_service:
        print("❌ Email service not configured")
        return False
    
    recipient = input("Enter your email address to receive welcome email: ").strip()
    
    if not recipient or '@' not in recipient:
        print("❌ Invalid email address")
        return False
    
    print(f"\nSending welcome email to: {recipient}")
    print("Please wait...\n")
    
    try:
        await email_service.send_welcome_email(
            to_email=recipient,
            username="testuser",
            login_url="http://localhost:3000/login"
        )
        
        print("✓ Welcome email sent successfully!\n")
        print("Check your inbox for the welcome message.")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send welcome email: {e}")
        return False


async def test_smtp_connection():
    """Test SMTP connection without sending email"""
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║                SMTP Connection Test                         ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")
    
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if not all([smtp_host, smtp_username, smtp_password]):
        print("❌ SMTP not configured")
        return False
    
    print(f"Testing connection to {smtp_host}:{smtp_port}...")
    
    try:
        import smtplib
        
        # Try to connect
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        server.starttls()
        
        print("✓ Connection established")
        print("✓ TLS enabled")
        
        # Try to login
        server.login(smtp_username, smtp_password)
        print("✓ Authentication successful")
        
        server.quit()
        print("\n✓ SMTP connection test passed!\n")
        return True
        
    except smtplib.SMTPAuthenticationError:
        print("\n❌ Authentication failed!")
        print("\nTroubleshooting:")
        print("  1. Check SMTP_USERNAME is correct")
        print("  2. Check SMTP_PASSWORD is your SMTP key (not account password)")
        print("  3. For Brevo, regenerate SMTP key if needed:")
        print("     https://app.brevo.com/settings/keys/smtp")
        return False
        
    except smtplib.SMTPException as e:
        print(f"\n❌ SMTP error: {e}")
        return False
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Check SMTP_HOST is correct")
        print("  2. Check SMTP_PORT is correct (usually 587)")
        print("  3. Check your internet connection")
        print("  4. Check firewall settings")
        return False


async def main():
    """Run email tests"""
    print("\n" + "="*60)
    print("Email Service Test Suite")
    print("="*60)
    
    # Test 1: Check configuration
    config_ok = await test_email_configuration()
    
    if not config_ok:
        print("\n❌ Please configure SMTP settings first")
        return 1
    
    # Test 2: Connection test
    print("\n" + "="*60)
    connection_ok = await test_smtp_connection()
    
    if not connection_ok:
        print("\n❌ SMTP connection test failed")
        print("Fix the connection issues before sending emails")
        return 1
    
    # Test 3: Welcome email (optional)
    print("\n" + "="*60)
    choice = input("\nDo you want to test the welcome email too? (y/n): ").strip().lower()
    
    if choice == 'y':
        await test_welcome_email()
    
    print("\n" + "="*60)
    print("Email Test Summary")
    print("="*60)
    print("✓ SMTP configuration: OK")
    print("✓ SMTP connection: OK")
    print("✓ Password reset email: Sent")
    if choice == 'y':
        print("✓ Welcome email: Sent")
    print("="*60)
    print("\nNext steps:")
    print("1. Check your email inbox")
    print("2. Check spam folder if not in inbox")
    print("3. Verify email formatting looks good")
    print("4. Test the reset link works (http://localhost:3000/reset-password?token=...)")
    print("\n✓ Email service is working!")
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user")
        sys.exit(1)
