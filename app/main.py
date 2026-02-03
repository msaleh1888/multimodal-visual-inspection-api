import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.logging import configure_logging
from app.config import settings
from app.utils.request_id import new_request_id, set_request_id

from app.api.health import router as health_router
from app.api.routes_image import router as image_router
from app.api.routes_document import router as document_router


def create_app() -> FastAPI:
    configure_logging()
    logger = logging.getLogger(__name__)

    app = FastAPI(title=settings.app_name)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get("X-Request-Id") or new_request_id()
        set_request_id(rid)

        try:
            response = await call_next(request)
        except Exception as e:
            logger.exception("Unhandled error")
            return JSONResponse(
                status_code=500,
                content={"error": {"code": "internal_error", "message": "Internal server error", "request_id": rid}},
            )

        response.headers["X-Request-Id"] = rid
        return response

    app.include_router(health_router)
    app.include_router(image_router)
    app.include_router(document_router)

    logger.info("App initialized")
    return app


app = create_app()