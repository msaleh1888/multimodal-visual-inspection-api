import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.utils.request_context import set_request_id, clear_request_id


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())

        # 1) For logging (contextvar)
        set_request_id(rid)

        # 2) For error handlers (exception handlers read request.state.request_id)
        request.state.request_id = rid

        try:
            response = await call_next(request)
        finally:
            clear_request_id()

        response.headers["X-Request-Id"] = rid
        return response