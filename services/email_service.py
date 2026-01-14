"""
Email service for sending notifications and password reset links.

Supports:
- SMTP configuration via environment variables
- Password reset emails
- Welcome emails
- Async email sending
"""

import os
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from datetime import datetime


class EmailService:
    """Service for sending emails"""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        from_email: str,
        from_name: str = "AgentSkills Framework"
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.from_name = from_name
    
    def _send_email_sync(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ):
        """Send email synchronously"""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{self.from_name} <{self.from_email}>"
        msg['To'] = to_email
        
        # Add text version if provided
        if text_body:
            part1 = MIMEText(text_body, 'plain')
            msg.attach(part1)
        
        # Add HTML version
        part2 = MIMEText(html_body, 'html')
        msg.attach(part2)
        
        # Send email
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ):
        """Send email asynchronously"""
        await asyncio.to_thread(
            self._send_email_sync,
            to_email,
            subject,
            html_body,
            text_body
        )
    
    async def send_password_reset_email(
        self,
        to_email: str,
        username: str,
        reset_token: str,
        reset_url_base: str
    ):
        """
        Send password reset email
        
        Args:
            to_email: Recipient email
            username: Username
            reset_token: Reset token
            reset_url_base: Base URL for reset link (e.g., https://app.example.com/reset-password)
        """
        reset_url = f"{reset_url_base}?token={reset_token}"
        
        subject = "Password Reset Request - AgentSkills Framework"
        
        text_body = f"""
Hello {username},

You requested a password reset for your AgentSkills Framework account.

Click the link below to reset your password:
{reset_url}

This link will expire in 1 hour.

If you did not request this reset, please ignore this email.

Best regards,
AgentSkills Framework Team
        """.strip()
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            background-color: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            margin: 20px 0;
        }}
        .footer {{
            margin-top: 30px;
            font-size: 12px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Password Reset Request</h2>
        <p>Hello <strong>{username}</strong>,</p>
        <p>You requested a password reset for your AgentSkills Framework account.</p>
        <p>Click the button below to reset your password:</p>
        <a href="{reset_url}" class="button">Reset Password</a>
        <p>Or copy this link into your browser:</p>
        <p style="word-break: break-all; color: #007bff;">{reset_url}</p>
        <p><strong>This link will expire in 1 hour.</strong></p>
        <p>If you did not request this reset, please ignore this email.</p>
        <div class="footer">
            <p>Best regards,<br>AgentSkills Framework Team</p>
        </div>
    </div>
</body>
</html>
        """.strip()
        
        await self.send_email(to_email, subject, html_body, text_body)
    
    async def send_welcome_email(
        self,
        to_email: str,
        username: str,
        login_url: str
    ):
        """
        Send welcome email to new user
        
        Args:
            to_email: Recipient email
            username: Username
            login_url: URL for login page
        """
        subject = "Welcome to AgentSkills Framework!"
        
        text_body = f"""
Hello {username},

Welcome to AgentSkills Framework!

Your account has been successfully created. You can now log in and start using the platform.

Login here: {login_url}

Best regards,
AgentSkills Framework Team
        """.strip()
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            background-color: #28a745;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            margin: 20px 0;
        }}
        .footer {{
            margin-top: 30px;
            font-size: 12px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Welcome to AgentSkills Framework!</h2>
        <p>Hello <strong>{username}</strong>,</p>
        <p>Your account has been successfully created. You can now log in and start using the platform.</p>
        <a href="{login_url}" class="button">Log In</a>
        <p>We're excited to have you on board!</p>
        <div class="footer">
            <p>Best regards,<br>AgentSkills Framework Team</p>
        </div>
    </div>
</body>
</html>
        """.strip()
        
        await self.send_email(to_email, subject, html_body, text_body)


# Global email service instance
_email_service: Optional[EmailService] = None


def get_email_service() -> Optional[EmailService]:
    """
    Get global email service instance
    
    Returns None if SMTP is not configured
    """
    global _email_service
    if _email_service is None:
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = os.getenv("SMTP_PORT", "587")
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        from_email = os.getenv("SMTP_FROM_EMAIL")
        from_name = os.getenv("SMTP_FROM_NAME", "AgentSkills Framework")
        
        # Return None if SMTP is not configured
        if not all([smtp_host, smtp_username, smtp_password, from_email]):
            return None
        
        _email_service = EmailService(
            smtp_host=smtp_host,
            smtp_port=int(smtp_port),
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            from_email=from_email,
            from_name=from_name
        )
    
    return _email_service
