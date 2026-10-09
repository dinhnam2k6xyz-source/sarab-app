import time
from collections import defaultdict
from typing import Dict, List
from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    """In-memory sliding window rate limiter per client IP."""
    def __init__(self):
        # Key: (endpoint_category, ip) -> list of timestamps
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def check_rate_limit(self, key: str, max_requests: int, window_seconds: int = 60):
        now = time.time()
        window_start = now - window_seconds

        # Prune old timestamps
        timestamps = self._requests[key]
        self._requests[key] = [t for t in timestamps if t > window_start]

        if len(self._requests[key]) >= max_requests:
            retry_after = int(self._requests[key][0] + window_seconds - now) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau {retry_after} giây.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        self._requests[key].append(now)


rate_limiter = SlidingWindowRateLimiter()


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def rate_limit_analyze(request: Request):
    ip = get_client_ip(request)
    rate_limiter.check_rate_limit(f"analyze:{ip}", max_requests=25, window_seconds=60)


def rate_limit_translate(request: Request):
    ip = get_client_ip(request)
    rate_limiter.check_rate_limit(f"translate:{ip}", max_requests=60, window_seconds=60)


def rate_limit_crawl(request: Request):
    ip = get_client_ip(request)
    rate_limiter.check_rate_limit(f"crawl:{ip}", max_requests=30, window_seconds=60)
