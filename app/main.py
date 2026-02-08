import logging
from fastapi import FastAPI

from app.logging import configure_logging
from app.config import settings

from app.api.health import router as health_router
from app.api.routes_image import router as image_router
from app.api.routes_document import router as document_router
from app.middleware.request_id import RequestIdMiddleware
from app.observability.metrics_route import router as metrics_router


def create_app() -> FastAPI:
    configure_logging()
    logger = logging.getLogger(__name__)

    app = FastAPI(title=settings.app_name)

    app.include_router(health_router)
    app.include_router(image_router)
    app.include_router(document_router)
    app.include_router(metrics_router)

    app.add_middleware(RequestIdMiddleware)
    logger.info("App initialized")

    return app


app = create_app()