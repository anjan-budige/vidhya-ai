import hmac
import secrets
from fastapi import Request, status
from fastapi.responses import ORJSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings

settings = get_settings()

class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Skip CSRF for non-state-changing requests
        if request.method in ("GET", "HEAD", "OPTIONS"):
            response = await call_next(request)
            # Inject a CSRF cookie if it doesn't exist
            if "csrf_token" not in request.cookies:
                already_set = any(
                    "csrf_token=" in value
                    for value in response.headers.getlist("set-cookie")
                )
                if not already_set:
                    csrf_token = secrets.token_urlsafe(32)
                    response.set_cookie(
                        key="csrf_token",
                        value=csrf_token,
                        httponly=False,  # Must be readable by frontend JS
                        secure=settings.SESSION_COOKIE_SECURE,
                        samesite=settings.SESSION_COOKIE_SAMESITE,
                        max_age=86400 * 7
                    )
            return response
            
        # 2. Header-based credentials are immune to CSRF
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") or request.headers.get("X-API-Key"):
            return await call_next(request)

        # 2.5 Bypass CSRF for specific endpoints (like login) where no session exists yet
        exempt_paths = [
            "/api/v1/auth/admin/login",
            "/api/v1/auth/admin/totp/verify",
            "/api/v1/auth/admin/forgot-password",
            "/api/v1/auth/admin/reset-password",
            "/api/v1/auth/register",
            "/api/v1/auth/verify-email",
            "/api/v1/auth/resend-otp",
            "/api/v1/auth/login",
            "/api/v1/auth/login/verify-otp",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
        ]
        if request.url.path in exempt_paths:
            # These cookie-issuing endpoints cannot require a pre-existing CSRF
            # token, so reject cross-site browser origins explicitly.
            origin = request.headers.get("origin")
            if origin:
                forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
                host = request.headers.get("host", request.url.netloc)
                allowed = set(settings.CORS_ORIGINS)
                allowed.add(settings.APP_URL.rstrip("/"))
                allowed.add(f"{forwarded_proto}://{host}")
                if origin.rstrip("/") not in allowed:
                    return ORJSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "Origin is not allowed."},
                    )
            return await call_next(request)

        if (
            request.url.path.startswith("/api/v1/payments/webhook/")
            or request.url.path.startswith("/api/v1/payments/return/")
        ):
            return await call_next(request)
            
        # 3. For state-changing requests using Cookies, enforce CSRF
        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("X-CSRF-Token")
        
        # If no cookie is present at all, but they are trying to do a POST, 
        # they might be unauthenticated, which will be caught by auth middleware anyway,
        # but strict CSRF requires the token to match.
        if not csrf_cookie or not csrf_header:
            # We allow login endpoints to bypass CSRF if they don't have a cookie yet
            # Actually, standard Double-Submit requires it everywhere, but for APIs,
            # we can strictly enforce it.
            return ORJSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "CSRF token missing from request or cookie."}
            )
            
        # 4. Compare tokens (timing-attack safe)
        if not hmac.compare_digest(csrf_cookie, csrf_header):
            return ORJSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "CSRF token validation failed."}
            )
            
        return await call_next(request)
