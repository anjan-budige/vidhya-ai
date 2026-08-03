from fastapi import Request

def get_client_ip(request: Request) -> str:
    """
    Safely extract the real client IP address when running behind a reverse proxy (like Nginx).
    Nginx MUST be configured to set X-Real-IP or X-Forwarded-For headers.
    Falls back to the direct client host if headers are missing.
    """
    if "X-Forwarded-For" in request.headers:
        # X-Forwarded-For can contain a comma-separated list of IPs.
        # The first IP is the original client.
        forwarded_for = request.headers["X-Forwarded-For"]
        return forwarded_for.split(",")[0].strip()
        
    if "X-Real-IP" in request.headers:
        return request.headers["X-Real-IP"]
        
    return request.client.host if request.client else "unknown"
