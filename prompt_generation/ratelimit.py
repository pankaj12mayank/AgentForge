from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request

_RATE: Dict[str, Deque[float]] = defaultdict(deque)

_DEFAULT_LIMIT = 20
_DEFAULT_WINDOW = 60.0


async def rate_limit_high(request: Request) -> None:
    """Rate limit sensitive/costly endpoints (default 20 req / 60s per IP)."""
    _check(request, limit=_DEFAULT_LIMIT, window=_DEFAULT_WINDOW)


def _check(request: Request, limit: int, window: float) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = _RATE[client_ip]

    while bucket and now - bucket[0] > window:
        bucket.popleft()

    if len(bucket) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {int(window - (now - bucket[0]))}s.",
        )

    bucket.append(now)