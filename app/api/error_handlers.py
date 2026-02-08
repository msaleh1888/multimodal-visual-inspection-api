from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


def _get_request_id(request: Request) -> Optional[str]:
    """
    Best-effort request_id retrieval without coupling to a specific middleware impl.
    - If your RequestIdMiddleware sets request.state.request_id, we use it.
    - Otherwise fall back to inbound header.
    """
    rid = getattr(getattr(request, "state", None), "request_id", None)
    if rid:
        return rid
    return request.headers.get("X-Request-Id")


def _error_payload(code: str, message: str, request_id: Optional[str]) -> Dict[str, Any]:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Normalize FastAPI HTTPException into the global error schema.
    We support:
    - detail as dict: {"code": "...", "message": "..."}  (your pipeline style)
    - detail as str: "..."                            (FastAPI default style)
    """
    rid = _get_request_id(request)

    code = "http_error"
    message = "Request failed"

    if isinstance(exc.detail, dict):
        code = str(exc.detail.get("code", code))
        message = str(exc.detail.get("message", message))
    elif isinstance(exc.detail, str):
        message = exc.detail

    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(code=code, message=message, request_id=rid),
        headers={"X-Request-Id": rid} if rid else None,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Normalize validation errors (422) into the global error schema.
    We keep the message concise to avoid leaking internals, but include a short summary.
    """
    rid = _get_request_id(request)

    # Build a short summary like: "body.field: msg; query.x: msg"
    parts = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []) if x != "body")
        msg = err.get("msg", "Invalid value")
        parts.append(f"{loc}: {msg}" if loc else str(msg))

    message = "; ".join(parts) if parts else "Validation error"

    return JSONResponse(
        status_code=422,
        content=_error_payload(code="validation_error", message=message, request_id=rid),
        headers={"X-Request-Id": rid} if rid else None,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler to ensure we always return the global error schema on 500.
    """
    rid = _get_request_id(request)
    logger.exception("Unhandled error")

    return JSONResponse(
        status_code=500,
        content=_error_payload(code="internal_error", message="Internal server error", request_id=rid),
        headers={"X-Request-Id": rid} if rid else None,
    )