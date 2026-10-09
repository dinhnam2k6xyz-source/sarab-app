import json
import logging
import re
import sys
import time
from typing import Any, Dict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import uuid

# Logger instance
logger = logging.getLogger("novel_translator")
logger.setLevel(logging.INFO)

# Console handler with formatting
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


SECRET_PATTERNS = [
    re.compile(r"(api[-_]?key\s*[:=]\s*['\"]?)([^'\"\s&]+)(['\"]?)", re.IGNORECASE),
    re.compile(r"(secret[-_]?key\s*[:=]\s*['\"]?)([^'\"\s&]+)(['\"]?)", re.IGNORECASE),
    re.compile(r"(authorization\s*[:=]\s*Bearer\s+)([^'\"\s&]+)", re.IGNORECASE),
]


def sanitize_message(message: str) -> str:
    """Mask potential secrets and keys from log strings."""
    sanitized = str(message)
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub(r"\1***REDACTED***\3" if r"\3" in pattern.pattern else r"\1***REDACTED***", sanitized)
    return sanitized


def log_event(
    event_type: str,
    request_id: str = "",
    url: str = "",
    scraper: str = "",
    chapter: str = "",
    translation_provider: str = "",
    latency_ms: float = 0.0,
    status: str = "ok",
    error: str = "",
    extra: Dict[str, Any] = None,
):
    """Structured JSON log event."""
    data = {
        "event": event_type,
        "request_id": request_id,
        "timestamp": time.time(),
        "url": url,
        "scraper": scraper,
        "chapter": chapter,
        "translation_provider": translation_provider,
        "latency_ms": round(latency_ms, 2),
        "status": status,
        "error": sanitize_message(error) if error else "",
    }
    if extra:
        for k, v in extra.items():
            if "key" in k.lower() or "secret" in k.lower() or "token" in k.lower():
                data[k] = "***REDACTED***"
            else:
                data[k] = v

    msg = json.dumps(data, ensure_ascii=False)
    if status == "error":
        logger.error(msg)
    else:
        logger.info(msg)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = req_id

        start_time = time.time()
        try:
            response = await call_next(request)
            latency_ms = (time.time() - start_time) * 1000
            response.headers["X-Request-ID"] = req_id
            
            # Don't log health checks or noisy static calls
            if not request.url.path.endswith("/health"):
                log_event(
                    event_type="http_request",
                    request_id=req_id,
                    url=str(request.url),
                    latency_ms=latency_ms,
                    status="ok" if response.status_code < 400 else "error",
                    error="" if response.status_code < 400 else f"HTTP {response.status_code}",
                )
            return response
        except Exception as exc:
            latency_ms = (time.time() - start_time) * 1000
            log_event(
                event_type="http_request_exception",
                request_id=req_id,
                url=str(request.url),
                latency_ms=latency_ms,
                status="error",
                error=str(exc),
            )
            raise exc
