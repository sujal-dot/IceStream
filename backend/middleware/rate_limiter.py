"""Rate Limiting Middleware for IceStream Security.

Provides sliding-window per-IP rate limiting on protected control operations
to prevent brute-force attacks and endpoint abuse.
"""

from collections import defaultdict
from datetime import datetime, timezone
import os
import sys
import threading
from typing import Dict, List, Tuple, Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Sensitive state-modifying control paths requiring rate limiting
PROTECTED_PATHS: Set[str] = {
    "/pipeline/pause",
    "/pipeline/resume",
    "/pipeline/recover",
    "/pipeline/remediate",
}


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Thread-safe sliding-window rate-limiting middleware for HTTP endpoints."""

    def __init__(
        self,
        app,
        requests_per_minute: int = 20,
        window_seconds: int = 60,
    ):
        super().__init__(app)
        self.requests_per_minute = int(os.getenv("RATE_LIMIT_PER_MINUTE", requests_per_minute))
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        # Storage structure: ip -> list of timestamp floats
        self._ip_history: Dict[str, List[float]] = defaultdict(list)

    def _is_protected(self, path: str) -> bool:
        path_lower = path.rstrip("/")
        if path_lower in PROTECTED_PATHS:
            return True
        if path_lower.startswith("/incidents/") and (
            path_lower.endswith("/acknowledge") or path_lower.endswith("/resolve")
        ):
            return True
        return False

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if not self._is_protected(path) or request.method.upper() != "POST":
            return await call_next(request)

        # Skip rate limiting during automated test suite execution if requested
        if os.getenv("DISABLE_RATE_LIMIT", "").lower() in ("true", "1"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown_ip"
        # Extract client IP from proxy headers if present
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        now = datetime.now(timezone.utc).timestamp()
        cutoff = now - self.window_seconds

        with self._lock:
            # Prune outdated timestamps
            timestamps = [t for t in self._ip_history[client_ip] if t > cutoff]

            if len(timestamps) >= self.requests_per_minute:
                oldest = timestamps[0]
                retry_after = int(max(1, self.window_seconds - (now - oldest)))
                self._ip_history[client_ip] = timestamps
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too Many Requests: Rate limit exceeded for control operation.",
                        "error": "RATE_LIMIT_EXCEEDED",
                        "retry_after_seconds": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            timestamps.append(now)
            self._ip_history[client_ip] = timestamps

        return await call_next(request)
