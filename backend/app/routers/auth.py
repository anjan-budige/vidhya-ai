import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import base64
import secrets
from io import BytesIO

from app.utils.request import get_client_ip
import redis.asyncio as aioredis
import qrcode
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import (
    get_db,
    get_redis_client,
    get_current_admin,
    require_superadmin,
    require_admin_or_above
)
from app.redis_client import RedisKeys
from app.services.auth import AdminAuthService
from app.schemas.auth import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminTOTPVerify,
    CurrentAdmin,
    AdminForgotPasswordRequest,
    AdminResetPasswordRequest,
    AdminUpdatePasswordRequest,
    AdminUpdateEmailRequest
)
from app.models.audit_log import AuditLog
from app.utils.email import send_reset_password_email

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/csrf", status_code=status.HTTP_200_OK)
async def csrf_token(request: Request, response: Response):
    """Return the CSRF token and make sure the double-submit cookie exists."""
    token = request.cookies.get("csrf_token") or secrets.token_urlsafe(32)
    response.set_cookie(
        key="csrf_token",
        value=token,
        httponly=False,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        max_age=86400 * 7,
        path="/",
    )
    return {"csrf_token": token}


@router.post("/admin/login", response_model=AdminLoginResponse, status_code=status.HTTP_200_OK)
async def admin_login(
    payload: AdminLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Authenticate admin with credentials.
    Enforces lockout thresholds. If 2FA is active, returns pre-auth status.
    """
    ip_address = get_client_ip(request)
    
    admin, session_token, requires_totp, expires_at = await AdminAuthService.authenticate_admin(
        username=payload.username,
        password=payload.password,
        db=db,
        redis=redis,
        ip_address=ip_address
    )
    
    # If TOTP not required, set active session cookie
    if not requires_totp:
        response.set_cookie(
            key="vidhya_admin_session",
            value=session_token,
            expires=expires_at,
            path="/",
            secure=settings.SESSION_COOKIE_SECURE,
            httponly=True,
            samesite="Strict"
        )
        
        db.add(AuditLog(
            admin_id=admin.id,
            action="admin.login",
            resource_type="admin",
            resource_id=admin.id,
            details={"ip_address": ip_address},
            ip_address=ip_address
        ))
        
    await db.commit()
    
    return AdminLoginResponse(
        admin_id=admin.id,
        session_token=session_token,
        role=admin.role,
        requires_totp=requires_totp,
        expires_at=expires_at
    )


@router.post("/admin/totp/verify", response_model=AdminLoginResponse, status_code=status.HTTP_200_OK)
async def admin_totp_verify(
    payload: AdminTOTPVerify,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Verify TOTP code using temporary session token.
    Promotes session to active state and sets HttpOnly cookie.
    """
    admin, new_token, expires_at = await AdminAuthService.verify_totp(
        session_token=payload.session_token,
        totp_code=payload.totp_code,
        db=db,
        redis=redis
    )
    
    response.set_cookie(
        key="vidhya_admin_session",
        value=new_token,
        expires=expires_at,
        path="/",
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="Strict"
    )
    
    db.add(AuditLog(
        admin_id=admin.id,
        action="admin.login_totp",
        resource_type="admin",
        resource_id=admin.id,
        details={"totp_verified": True}
    ))
    
    await db.commit()
    
    return AdminLoginResponse(
        admin_id=admin.id,
        session_token=new_token,
        role=admin.role,
        requires_totp=False,
        expires_at=expires_at
    )


@router.post("/admin/totp/provision", status_code=status.HTTP_200_OK)
async def admin_totp_provision(
    current_admin: CurrentAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Provision a new TOTP secret for the active admin.
    Returns the secret and provisioning URI (for QR code generation).
    Does NOT enable TOTP until verified.
    """
    secret, provisioning_uri = await AdminAuthService.provision_totp(
        admin_id=current_admin.id,
        db=db
    )
    await db.commit()
    return {
        "secret": secret,
        "provisioning_uri": provisioning_uri
    }


@router.get("/admin/totp/setup", status_code=status.HTTP_200_OK)
async def admin_totp_setup(
    current_admin: CurrentAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a new TOTP secret and QR code for the admin to scan in their Authenticator app.
    Does not activate 2FA until confirmed.
    """
    secret, uri = await AdminAuthService.provision_totp(
        admin_id=current_admin.id,
        db=db
    )
    await db.commit()
    
    qr = qrcode.make(uri)
    buffered = BytesIO()
    qr.save(buffered)
    qr_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    return {
        "secret": secret,
        "qr_code_base64": qr_base64
    }


class TOTPConfirmRequest(BaseModel):
    code: str

@router.post("/admin/totp/confirm", status_code=status.HTTP_200_OK)
async def admin_totp_confirm(
    payload: TOTPConfirmRequest,
    current_admin: CurrentAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify the first TOTP passcode to officially activate 2FA.
    """
    code = payload.code
    if not code or len(code) != 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid 6-digit TOTP code required."
        )
        
    success = await AdminAuthService.confirm_totp(
        admin_id=current_admin.id,
        code=code,
        db=db
    )
    db.add(AuditLog(
        admin_id=current_admin.id,
        action="admin.totp_enabled",
        resource_type="admin",
        resource_id=current_admin.id,
        details={"success": success}
    ))
    await db.commit()
    return {"success": success, "detail": "Two-factor authentication successfully enabled."}


class TOTPDisableRequest(BaseModel):
    admin_id: str

@router.post("/admin/totp/disable", status_code=status.HTTP_200_OK)
async def admin_totp_disable(
    payload: TOTPDisableRequest,
    current_admin: CurrentAdmin = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db)
):
    """
    Disable 2FA security for a specified admin account (Superadmin only).
    """
    target_admin_str = payload.admin_id
    if not target_admin_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin ID parameter is required."
        )
        
    try:
        target_admin_id = uuid.UUID(target_admin_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Admin ID format."
        )
        
    success = await AdminAuthService.disable_totp(
        admin_id=target_admin_id,
        db=db
    )
    db.add(AuditLog(
        admin_id=current_admin.id,
        action="admin.totp_disabled",
        resource_type="admin",
        resource_id=target_admin_id,
        details={"target_admin_id": str(target_admin_id), "disabled_by": str(current_admin.id)}
    ))
    await db.commit()
    return {"success": success, "detail": "Two-factor authentication successfully disabled."}


@router.get("/admin/me", status_code=status.HTTP_200_OK)
async def get_admin_profile(
    current_admin: CurrentAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import select
    from app.models.admin import Admin
    
    result = await db.execute(select(Admin).where(Admin.id == current_admin.id))
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
        
    return {
        "id": admin.id,
        "username": admin.username,
        "role": admin.role,
        "email": admin.email,
        "totp_enabled": admin.totp_enabled
    }


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    vidhya_session: Optional[str] = Cookie(default=None),
    vidhya_admin_session: Optional[str] = Cookie(default=None),
    redis: aioredis.Redis = Depends(get_redis_client),
    db: AsyncSession = Depends(get_db)
):
    """
    Evict user and admin sessions from Redis and delete active cookies.
    """
    if vidhya_session:
        session_key = RedisKeys.session(vidhya_session)
        await redis.delete(session_key)
        response.delete_cookie(key=settings.SESSION_COOKIE_NAME, path="/")
        
    if vidhya_admin_session:
        admin_session_key = RedisKeys.admin_session(vidhya_admin_session)
        try:
            from app.dependencies import get_current_admin_from_token
            admin_data = await redis.get(admin_session_key)
            if admin_data:
                import json as _json
                data = _json.loads(admin_data)
                admin_id = data.get("admin_id")
                ip_address = get_client_ip(request)
                if admin_id:
                    db.add(AuditLog(
                        admin_id=admin_id,
                        action="admin.logout",
                        resource_type="admin",
                        resource_id=admin_id,
                        details={},
                        ip_address=ip_address
                    ))
                    await db.commit()
        except Exception:
            pass
        await redis.delete(admin_session_key)
        response.delete_cookie(key="vidhya_admin_session", path="/")
        
    return {"detail": "Successfully logged out."}

@router.post("/admin/forgot-password", status_code=status.HTTP_200_OK)
async def admin_forgot_password(
    payload: AdminForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Request a password reset link.
    """
    token = await AdminAuthService.generate_password_reset_token(
        email=payload.email,
        db=db,
        redis=redis
    )
    
    if token:
        reset_link = f"{settings.APP_URL}/admin/reset-password?token={token}"
        await send_reset_password_email(payload.email, reset_link)
        
    return {"status": "success", "message": "If the email exists, a reset link has been sent."}

@router.post("/admin/reset-password", status_code=status.HTTP_200_OK)
async def admin_reset_password(
    payload: AdminResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client)
):
    """
    Reset password using token.
    """
    ip_address = get_client_ip(request)
    await AdminAuthService.reset_password(
        token=payload.token,
        new_password=payload.new_password,
        db=db,
        redis=redis
    )
    # Log password reset (no admin_id since user is unauthenticated at this point)
    db.add(AuditLog(
        admin_id=None,
        action="admin.password_reset",
        resource_type="admin",
        resource_id=None,
        details={"method": "reset_token"},
        ip_address=ip_address
    ))
    await db.commit()
    return {"status": "success", "message": "Password successfully reset."}

@router.post("/admin/update-password", status_code=status.HTTP_200_OK)
async def admin_update_password(
    payload: AdminUpdatePasswordRequest,
    request: Request,
    current_admin: CurrentAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
):
    """
    Update password for an authenticated admin.
    """
    ip_address = get_client_ip(request)
    await AdminAuthService.update_password(
        admin_id=current_admin.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
        db=db,
        redis=redis,
    )
    db.add(AuditLog(
        admin_id=current_admin.id,
        action="admin.password_changed",
        resource_type="admin",
        resource_id=current_admin.id,
        details={"changed_by": str(current_admin.id)},
        ip_address=ip_address
    ))
    await db.commit()
    return {"status": "success", "message": "Password successfully updated."}

@router.post("/admin/update-email", status_code=status.HTTP_200_OK)
async def admin_update_email(
    payload: AdminUpdateEmailRequest,
    request: Request,
    current_admin: CurrentAdmin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Update email for an authenticated admin.
    """
    from sqlalchemy import select
    from app.models.admin import Admin
    
    ip_address = get_client_ip(request)
    
    result = await db.execute(select(Admin).where(Admin.id == current_admin.id))
    admin = result.scalar_one_or_none()
    
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")
        
    old_email = admin.email
    admin.email = payload.email
    db.add(AuditLog(
        admin_id=current_admin.id,
        action="admin.email_changed",
        resource_type="admin",
        resource_id=current_admin.id,
        details={"old_email": old_email, "new_email": payload.email},
        ip_address=ip_address
    ))
    await db.commit()
    return {"status": "success", "message": "Email successfully updated."}
