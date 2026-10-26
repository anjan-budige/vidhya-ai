from fastapi import Request

def get_client_ip(request: Request) -> str:
    """
    Return the client address set by the trusted reverse proxy.

    Nginx overwrites X-Real-IP with $remote_addr. X-Forwarded-For is deliberately
    not trusted because clients can prepend arbitrary addresses to it.
    """
    real_ip = request.headers.get("X-Real-IP", "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"
