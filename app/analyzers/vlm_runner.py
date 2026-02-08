from __future__ import annotations

import time
import anyio

from app.config import settings
from app.analyzers.vlm_errors import VLMTimeout


async def run_with_timeout(fn, *args, **kwargs):
    start = time.perf_counter()
    try:
        with anyio.fail_after(settings.vlm_timeout_seconds):
            result = await anyio.to_thread.run_sync(lambda: fn(*args, **kwargs))
        duration = time.perf_counter() - start
        return result, duration
    except TimeoutError as e:
        raise VLMTimeout(f"VLM timed out after {settings.vlm_timeout_seconds}s") from e