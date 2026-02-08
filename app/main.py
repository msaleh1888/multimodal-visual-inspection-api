import logging
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from app.logging import configure_logging
from app.config import settings

from app.api.health import router as health_router
from app.api.routes_image import router as image_router
from app.api.routes_document import router as document_router
from app.middleware.request_id import RequestIdMiddleware
from app.observability.metrics_route import router as metrics_router

from app.api.error_handlers import (
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)


def create_app() -> FastAPI:
    configure_logging()
    logger = logging.getLogger(__name__)

    app = FastAPI(title=settings.app_name)

    # Global error schema
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(health_router)
    app.include_router(image_router)
    app.include_router(document_router)
    app.include_router(metrics_router)

    app.add_middleware(RequestIdMiddleware)
    logger.info("App initialized")

    return app


app = create_app()