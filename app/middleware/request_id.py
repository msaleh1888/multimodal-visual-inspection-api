import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.request_context import set_request_id, clear_request_id


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        set_request_id(rid)
        try:
            response = await call_next(request)
        finally:
            clear_request_id()
        response.headers["X-Request-Id"] = rid
        return response