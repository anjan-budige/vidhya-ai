"""
Vidhya AI — transactional email.

All platform email goes through Resend (https://resend.com).
Set RESEND_API_KEY, RESEND_FROM_EMAIL and a verified sending domain.
"""

import html
import logging

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def _sender() -> str:
    name = (settings.RESEND_FROM_NAME or "").strip().strip('"')
    address = (settings.RESEND_FROM_EMAIL or "").strip()
    return f"{name} <{address}>" if name else address


def _is_configured() -> bool:
    key = (settings.RESEND_API_KEY or "").strip()
    if not key or not settings.RESEND_FROM_EMAIL:
        return False
    return not key.startswith(("re_xxx", "re_YOUR_"))


def _support_email() -> str:
    return (settings.RESEND_REPLY_TO or settings.SUPERADMIN_EMAIL or "").strip()


def _button(label: str, url: str) -> str:
    return (
        f'<a href="{html.escape(url, quote=True)}" '
        'style="display:inline-block;background:#4680FF;color:#ffffff;'
        'padding:14px 30px;border-radius:9px;text-decoration:none;'
        'font-weight:600;font-size:15px;line-height:1.2;">'
        f"{html.escape(label)}</a>"
    )


def _shell(inner: str, preheader: str = "") -> str:
    """Responsive, table-based email shell with the Vidhya brand."""
    logo = f"{settings.APP_URL.rstrip('/')}/vidhya_logo_horizontal.png"
    support = _support_email()
    support_line = (
        f'<a href="mailto:{html.escape(support)}" style="color:#4680FF;text-decoration:none;">'
        f"{html.escape(support)}</a>"
        if support
        else "reply to this email"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vidhya AI</title>
</head>
<body style="margin:0;padding:0;background:#f4f6fb;">
<div style="display:none;font-size:1px;color:#f4f6fb;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">
  {html.escape(preheader)}
</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f4f6fb;">
  <tr>
    <td align="center" style="padding:32px 16px;">
      <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0"
             style="width:100%;max-width:600px;background:#ffffff;border:1px solid #e6ebf1;border-radius:16px;overflow:hidden;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
        <tr><td style="height:4px;background:#4680FF;font-size:0;line-height:0;">&nbsp;</td></tr>
        <tr>
          <td align="center" style="padding:28px 32px 8px;">
            <img src="{html.escape(logo, quote=True)}" alt="Vidhya AI" width="168"
                 style="display:block;width:168px;max-width:70%;height:auto;border:0;">
          </td>
        </tr>
        <tr>
          <td style="padding:20px 36px 8px;color:#1d2630;font-size:15px;line-height:1.65;">
            {inner}
          </td>
        </tr>
        <tr><td style="padding:8px 36px 0;"><div style="height:1px;background:#e6ebf1;font-size:0;line-height:0;">&nbsp;</div></td></tr>
        <tr>
          <td align="center" style="padding:20px 36px 8px;color:#5b6b79;font-size:12px;line-height:1.6;">
            Vidhya AI · AI-powered learning for your documents<br>
            Need help? {support_line}
          </td>
        </tr>
        <tr>
          <td align="center" style="padding:0 36px 26px;color:#8996a4;font-size:11px;line-height:1.5;">
            This is a transactional message about your account. Please do not share
            password-reset links with anyone.
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str | None = None,
) -> bool:
    """Send one transactional email through Resend."""
    if not _is_configured():
        logger.warning(
            "Resend is not configured (RESEND_API_KEY / RESEND_FROM_EMAIL). "
            "Skipping email to %s.",
            to_email,
        )
        return False

    payload = {
        "from": _sender(),
        "to": [to_email],
        "subject": subject,
        "html": html_content,
    }
    if text_content:
        payload["text"] = text_content
    if settings.RESEND_REPLY_TO:
        payload["reply_to"] = settings.RESEND_REPLY_TO

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY.strip()}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except Exception as e:
        logger.error("Resend request failed for %s: %s", to_email, e)
        return False

    if response.status_code >= 400:
        logger.error(
            "Resend API error %s for %s: %s",
            response.status_code,
            to_email,
            response.text,
        )
        return False

    email_id = ""
    try:
        email_id = response.json().get("id", "")
    except Exception:
        pass
    logger.info("Email sent via Resend to %s (id=%s)", to_email, email_id)
    return True


async def send_reset_password_email(to_email: str, reset_link: str) -> bool:
    """Admin password reset link."""
    safe_link = html.escape(reset_link, quote=True)
    inner = f"""
        <h1 style="margin:0 0 8px;font-size:22px;line-height:1.3;color:#1d2630;">Reset your admin password</h1>
        <p style="margin:0 0 18px;color:#5b6b79;font-size:14px;line-height:1.65;">
          We received a request to reset the password for your Vidhya AI admin account.
        </p>
        <div style="text-align:center;margin:26px 0;">{_button("Reset password", reset_link)}</div>
        <p style="margin:0 0 10px;color:#5b6b79;font-size:13px;line-height:1.65;">
          This link expires in 15 minutes. If you did not request it, ignore this email — your password will not change.
        </p>
        <p style="margin:0;color:#8996a4;font-size:12px;line-height:1.6;word-break:break-all;">
          Button not working? <a href="{safe_link}" style="color:#4680FF;text-decoration:none;">Open the reset link</a>.
        </p>
    """
    text_content = (
        "Reset your Vidhya AI admin password (valid for 15 minutes):\n"
        f"{reset_link}\n\nIf you did not request this, ignore this email."
    )
    return await send_email(
        to_email=to_email,
        subject="Reset your Vidhya AI admin password",
        html_content=_shell(inner, "Reset your Vidhya AI admin password."),
        text_content=text_content,
    )


async def send_otp_email(
    to_email: str, name: str, code: str, purpose: str = "verify_email"
) -> bool:
    safe_name = html.escape(name or "there")
    safe_code = html.escape(code)
    subject = "Your sign-in code" if purpose == "login" else "Verify your email"
    heading = "Sign in to Vidhya AI" if purpose == "login" else "Verify your email"
    lead = (
        "Use this code to finish signing in."
        if purpose == "login"
        else "Use this code to verify your email and activate your account."
    )
    inner = f"""
        <h1 style="margin:0 0 8px;font-size:22px;line-height:1.3;color:#1d2630;">{heading}</h1>
        <p style="margin:0 0 20px;color:#5b6b79;font-size:14px;line-height:1.65;">
          Hi {safe_name}, {lead}
        </p>
        <div style="text-align:center;margin:26px 0;">
          <span style="display:inline-block;background:#e9f0ff;color:#2050ff;font-size:30px;letter-spacing:8px;font-weight:700;padding:14px 22px;border-radius:10px;">{safe_code}</span>
        </div>
        <p style="margin:0;color:#5b6b79;font-size:13px;line-height:1.65;">
          This code expires in 10 minutes. If you did not request it, ignore this email.
        </p>
    """
    text = f"{heading}\n\nHi {name}, {lead}\n\nCode: {code}\n\nExpires in 10 minutes."
    return await send_email(
        to_email,
        subject,
        _shell(inner, f"Your Vidhya AI code: {code}"),
        text,
    )


async def send_user_reset_password_email(
    to_email: str, name: str, reset_link: str
) -> bool:
    safe_name = html.escape(name or "there")
    safe_link = html.escape(reset_link, quote=True)
    inner = f"""
        <h1 style="margin:0 0 8px;font-size:22px;line-height:1.3;color:#1d2630;">Choose a new password</h1>
        <p style="margin:0 0 8px;color:#5b6b79;font-size:14px;line-height:1.65;">
          Hi {safe_name}, we received a request to reset the password for your Vidhya AI account.
        </p>
        <p style="margin:0 0 18px;color:#5b6b79;font-size:14px;line-height:1.65;">
          Click the button below to choose a new password. You will use it the next time you sign in.
        </p>
        <div style="text-align:center;margin:28px 0;">{_button("Choose a new password", reset_link)}</div>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
               style="background:#f8f9fa;border:1px solid #e6ebf1;border-radius:10px;margin:0 0 18px;">
          <tr>
            <td style="padding:14px 16px;color:#5b6b79;font-size:13px;line-height:1.6;">
              <strong style="color:#1d2630;">Link expires in 15 minutes.</strong><br>
              For your security, this link can be used once. Vidhya AI will never ask you
              to share your password or this link.
            </td>
          </tr>
        </table>
        <p style="margin:0 0 10px;color:#5b6b79;font-size:13px;line-height:1.65;">
          If you did not request a password reset, you can safely ignore this email —
          your current password will stay the same.
        </p>
        <p style="margin:0;color:#8996a4;font-size:12px;line-height:1.6;word-break:break-all;">
          Button not working? <a href="{safe_link}" style="color:#4680FF;text-decoration:none;">Open the reset link</a>.
        </p>
    """
    text = (
        f"Hi {name},\n\n"
        "We received a request to reset your Vidhya AI password.\n"
        f"Choose a new password (valid for 15 minutes): {reset_link}\n\n"
        "This link can be used once. If you did not request it, ignore this email — "
        "your current password will stay the same.\n"
    )
    return await send_email(
        to_email,
        "Reset your Vidhya AI password",
        _shell(inner, "Choose a new password for your Vidhya AI account."),
        text,
    )


async def send_account_created_email(
    to_email: str, name: str, username: str, setup_link: str
) -> bool:
    safe_name = html.escape(name or "there")
    safe_username = html.escape(username)
    safe_link = html.escape(setup_link, quote=True)
    inner = f"""
        <h1 style="margin:0 0 8px;font-size:22px;line-height:1.3;color:#1d2630;">Your account is ready</h1>
        <p style="margin:0 0 8px;color:#5b6b79;font-size:14px;line-height:1.65;">
          Hi {safe_name}, an account has been created for you on Vidhya AI.
        </p>
        <p style="margin:0 0 18px;color:#5b6b79;font-size:14px;line-height:1.65;">
          Set your password to sign in to the dashboard and start using the assistant.
        </p>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
               style="background:#f8f9fa;border:1px solid #e6ebf1;border-radius:10px;margin:0 0 22px;">
          <tr>
            <td style="padding:14px 16px;">
              <p style="margin:0 0 4px;color:#5b6b79;font-size:12px;">Username</p>
              <p style="margin:0;color:#1d2630;font-size:16px;font-weight:600;">{safe_username}</p>
            </td>
          </tr>
        </table>
        <div style="text-align:center;margin:26px 0;">{_button("Set your password", setup_link)}</div>
        <p style="margin:0 0 10px;color:#5b6b79;font-size:13px;line-height:1.65;">
          This link expires in 24 hours. If you were not expecting an account, you can ignore this email.
        </p>
        <p style="margin:0;color:#8996a4;font-size:12px;line-height:1.6;word-break:break-all;">
          Button not working? <a href="{safe_link}" style="color:#4680FF;text-decoration:none;">Open the setup link</a>.
        </p>
    """
    text = (
        f"Hi {name},\n\nYour Vidhya AI account is ready.\n\n"
        f"Username: {username}\nSet your password: {setup_link}\n\n"
        "This link expires in 24 hours. If you were not expecting an account, ignore this email."
    )
    return await send_email(
        to_email,
        "Your Vidhya AI account is ready",
        _shell(inner, "Set your Vidhya AI password."),
        text,
    )


async def send_deployment_welcome_email(
    to_email: str, username: str, raw_password: str
) -> bool:
    """First-start email with the seeded admin credentials."""
    safe_username = html.escape(username)
    safe_password = html.escape(raw_password)

    login_url = f"{settings.APP_URL}/admin/login"
    bot_url = f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}"
    inner = f"""
        <h1 style="margin:0 0 8px;font-size:22px;line-height:1.3;color:#1d2630;">Welcome to Vidhya AI</h1>
        <p style="margin:0 0 18px;color:#5b6b79;font-size:14px;line-height:1.65;">
          Your platform is deployed and initialized. These are your admin credentials:
        </p>
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
               style="background:#f8f9fa;border:1px solid #e6ebf1;border-radius:10px;margin:0 0 20px;">
          <tr>
            <td style="padding:16px;">
              <p style="margin:0 0 8px;color:#5b6b79;font-size:13px;"><strong style="color:#1d2630;">Username:</strong> {safe_username}</p>
              <p style="margin:0;color:#5b6b79;font-size:13px;"><strong style="color:#1d2630;">Password:</strong> {safe_password}</p>
            </td>
          </tr>
        </table>
        <div style="text-align:center;margin:24px 0;">{_button("Open the admin dashboard", login_url)}</div>
        <p style="margin:0 0 10px;color:#5b6b79;font-size:13px;line-height:1.65;">
          For your security, change this password and enable two-factor authentication
          immediately after your first sign-in.
        </p>
        <p style="margin:0;color:#8996a4;font-size:12px;line-height:1.6;">
          Telegram bot: <a href="{html.escape(bot_url, quote=True)}" style="color:#4680FF;text-decoration:none;">{html.escape(bot_url)}</a>
        </p>
    """
    text_content = (
        "Your Vidhya AI platform is ready.\n\n"
        f"Admin username: {username}\n"
        f"Admin password: {raw_password}\n\n"
        f"Admin dashboard: {login_url}\n"
        f"Telegram bot: {bot_url}\n\n"
        "Change the password and enable 2FA after your first login."
    )

    return await send_email(
        to_email=to_email,
        subject="Vidhya AI — platform ready",
        html_content=_shell(inner, "Your Vidhya AI admin account is ready."),
        text_content=text_content,
    )
