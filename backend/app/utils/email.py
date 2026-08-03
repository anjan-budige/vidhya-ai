import httpx
import logging
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

async def send_reset_password_email(to_email: str, reset_link: str) -> bool:
    """
    Sends a password reset email using Mailtrap's HTTP API.
    Returns True if successful, False otherwise.
    """
    if not settings.MAILTRAP_TOKEN or settings.MAILTRAP_TOKEN == "your_mailtrap_token":
        logger.warning("Mailtrap token not configured. Skipping email send.")
        return False

    url = "https://send.api.mailtrap.io/api/send"
    
    headers = {
        "Authorization": f"Bearer {settings.MAILTRAP_TOKEN}",
        "Content-Type": "application/json"
    }

    html_content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px;">
        <h2 style="color: #1e293b; text-align: center;">Vidhya Admin Password Reset</h2>
        <p style="color: #475569; font-size: 16px;">Hello,</p>
        <p style="color: #475569; font-size: 16px;">We received a request to reset your Vidhya Admin password. Click the button below to set a new password:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_link}" style="background-color: #4f46e5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px;">Reset Password</a>
        </div>
        <p style="color: #475569; font-size: 14px;">If you did not request this, please ignore this email. This link will expire in 15 minutes.</p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 30px 0;">
        <p style="color: #94a3b8; font-size: 12px; text-align: center;">© 2026 Vidhya Platform</p>
    </div>
    """

    payload = {
        "from": {
            "email": settings.MAILTRAP_SENDER_EMAIL,
            "name": "Vidhya Admin"
        },
        "to": [
            {
                "email": to_email
            }
        ],
        "subject": "Reset Your Vidhya Admin Password",
        "html": html_content,
        "category": "Password Reset"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=10.0)
            response.raise_for_status()
            logger.info(f"Password reset email sent successfully to {to_email}")
            return True
    except httpx.HTTPStatusError as e:
        logger.error(f"Mailtrap API error: {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return False

async def send_deployment_welcome_email(to_email: str, username: str, raw_password: str) -> bool:
    """
    Sends a welcome email upon successful deployment.
    """
    if not settings.MAILTRAP_TOKEN or settings.MAILTRAP_TOKEN == "your_mailtrap_token":
        logger.warning("Mailtrap token not configured. Skipping welcome email.")
        return False

    url = "https://send.api.mailtrap.io/api/send"
    
    headers = {
        "Authorization": f"Bearer {settings.MAILTRAP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    login_url = f"{settings.APP_URL}/admin/login"
    bot_url = f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}"

    html_content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px;">
        <h2 style="color: #1e293b; text-align: center;">Welcome to Vidhya Platform</h2>
        <p style="color: #475569; font-size: 16px;">Hello,</p>
        <p style="color: #475569; font-size: 16px;">Your Vidhya Bot platform has been successfully deployed and initialized!</p>
        
        <div style="background-color: #f8fafc; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <h3 style="margin-top: 0; color: #334155;">Admin Credentials</h3>
            <p style="margin: 5px 0;"><strong>Username:</strong> {username}</p>
            <p style="margin: 5px 0;"><strong>Password:</strong> {raw_password}</p>
        </div>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{login_url}" style="background-color: #4f46e5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px; margin-right: 10px;">Admin Dashboard</a>
            <a href="{bot_url}" style="background-color: #0284c7; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 16px;">Open Telegram Bot</a>
        </div>
        
        <h3 style="color: #334155;">Core Features Activated:</h3>
        <ul style="color: #475569; font-size: 15px;">
            <li>🤖 AI Chat powered by Ollama</li>
            <li>📚 Document RAG & PDF Analysis</li>
            <li>💳 PhonePe Payments Integration</li>
            <li>🔐 2FA Secure Admin Portal</li>
        </ul>
        
        <p style="color: #475569; font-size: 14px; margin-top: 30px;">For your security, please log in and change your password and enable 2FA immediately.</p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 30px 0;">
        <p style="color: #94a3b8; font-size: 12px; text-align: center;">© 2026 Vidhya Platform</p>
    </div>
    """

    payload = {
        "from": {
            "email": settings.MAILTRAP_SENDER_EMAIL,
            "name": "Vidhya Deployment"
        },
        "to": [
            {
                "email": to_email
            }
        ],
        "subject": "Vidhya Platform Successfully Deployed 🚀",
        "html": html_content,
        "category": "Deployment Welcome"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=10.0)
            response.raise_for_status()
            logger.info(f"Deployment welcome email sent successfully to {to_email}")
            return True
    except httpx.HTTPStatusError as e:
        logger.error(f"Mailtrap API error: {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"Failed to send welcome email to {to_email}: {str(e)}")
        return False
