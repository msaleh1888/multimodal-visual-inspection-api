from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol


# -----------------------------
# Public types
# -----------------------------

@dataclass(frozen=True)
class LLMRequest:
    """
    A provider-agnostic request for a text-only LLM.

    Keep it minimal: our grounded explainer (Issue #13) will primarily pass:
    - a single prompt string
    - deterministic generation settings (temperature=0)
    """
    prompt: str
    temperature: float = 0.0
    max_tokens: int = 512

    # Optional: useful for future tracing / routing
    request_id: Optional[str] = None


@dataclass(frozen=True)
class LLMResult:
    """
    Provider-agnostic result.

    raw_text is the only required field.
    meta allows attaching provider-specific details (usage, device, etc.)
    without leaking provider code into callers.
    """
    raw_text: str
    model_id: str
    latency_ms: int
    attempts: int
    meta: Dict[str, Any]


# -----------------------------
# Errors
# -----------------------------

class LLMError(RuntimeError):
    """Base class for all LLM client failures."""


class LLMTimeoutError(LLMError):
    """Raised when the provider times out."""


class LLMDownstreamError(LLMError):
    """
    Raised when the provider fails in a non-timeout way:
    - model load error
    - OOM
    - bad configuration
    - internal provider exception
    """


# -----------------------------
# Client interface
# -----------------------------

class LLMClient(Protocol):
    """
    Text-only LLM client interface.

    Implementation examples:
    - TransformersLLMClient (local HF model)
    - MockLLMClient (tests)
    """
    @property
    def model_id(self) -> str:
        ...

    def generate(self, req: LLMRequest) -> LLMResult:
        ...


# -----------------------------
# Retry wrapper (composition)
# -----------------------------

@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_ms: int = 250  # simple linear backoff (250ms, 500ms, 750ms...)


class RetryingLLMClient:
    """
    Wrap any LLMClient with retries.

    Why composition?
    - keeps provider clients simple
    - ensures consistent retry behavior across the app
    - easy to unit test
    """

    def __init__(self, inner: LLMClient, policy: RetryPolicy):
        self._inner = inner
        self._policy = policy

    @property
    def model_id(self) -> str:
        return self._inner.model_id

    def generate(self, req: LLMRequest) -> LLMResult:
        start = time.perf_counter()
        last_err: Optional[Exception] = None

        for attempt in range(1, self._policy.max_attempts + 1):
            try:
                res = self._inner.generate(req)
                total_ms = int((time.perf_counter() - start) * 1000)
                # Ensure attempts/latency reflect the overall wrapper, not just inner
                return LLMResult(
                    raw_text=res.raw_text,
                    model_id=res.model_id,
                    latency_ms=total_ms,
                    attempts=attempt,
                    meta={**res.meta, "retry_wrapper": True},
                )
            except LLMTimeoutError as e:
                # Retriable
                last_err = e
            except LLMDownstreamError as e:
                # Often retriable too (transient GPU OOM, lazy init races, etc.)
                last_err = e
            except Exception as e:
                # Unknown errors become downstream errors so callers have a consistent surface
                last_err = LLMDownstreamError(f"{type(e).__name__}: {e}")

            # Backoff before next attempt (except after the last attempt)
            if attempt < self._policy.max_attempts:
                time.sleep((self._policy.backoff_ms * attempt) / 1000.0)

        # Exhausted retries
        assert last_err is not None
        if isinstance(last_err, LLMError):
            raise last_err
        raise LLMDownstreamError(str(last_err))