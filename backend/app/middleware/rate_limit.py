import time
import uuid
from typing import Optional

from fastapi import Request, status
from fastapi.responses import ORJSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.redis_client import redis_client
from app.utils.request import get_client_ip

settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # Determine limits based on path
        limit = None
        window_sec = 60
        quota_type = "general"
        
        if path.startswith("/api/v1/ai"):
            limit = settings.RATE_LIMIT_AI_PER_MINUTE
            quota_type = "ai"
        elif path.startswith("/api/v1/auth"):
            limit = settings.RATE_LIMIT_LOGIN_PER_MINUTE
            quota_type = "auth"
        elif path.startswith("/api/v1/documents/upload"):
            limit = settings.RATE_LIMIT_UPLOAD_PER_HOUR
            window_sec = 3600
            quota_type = "upload"
            
        if limit:
            # Identifier: IP by default
            identifier = get_client_ip(request)
            
            # If user is authenticated, use user ID as part of identifier
            auth_header = request.headers.get("Authorization", "")
            session_cookie = request.cookies.get(settings.SESSION_COOKIE_NAME, "")
            token = None
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
            elif session_cookie:
                token = session_cookie
                
            if token:
                try:
                    from app.redis_client import RedisKeys
                    session_data = await redis_client.hgetall(RedisKeys.session(token))
                    if session_data and "user_id" in session_data:
                        identifier = session_data["user_id"]
                except Exception:
                    pass
            
            # Redis Sliding Window Rate Limit
            key = f"ratelimit:{quota_type}:{identifier}"
            current_time = time.time()
            window_start = current_time - window_sec
            
            try:
                # Use a pipeline for atomicity
                async with redis_client.pipeline() as pipe:
                    # Remove older timestamps
                    pipe.zremrangebyscore(key, 0, window_start)
                    # Count existing timestamps in window
                    pipe.zcard(key)
                    # Add current timestamp
                    pipe.zadd(key, {str(uuid.uuid4()): current_time})
                    # Set expiry to prevent key buildup
                    pipe.expire(key, window_sec)
                    
                    results = await pipe.execute()
                    
                    request_count = results[1]
                    
                    if request_count >= limit:
                        return ORJSONResponse(
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            content={
                                "detail": "Rate limit exceeded.",
                                "retry_after": window_sec
                            }
                        )
            except Exception as e:
                # If Redis fails, fail open to not block traffic, but log the error
                from app.main import logger
                logger.error(f"RateLimiter Redis Error: {e}")

        # Continue request
        return await call_next(request)
