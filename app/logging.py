import logging
from app.config import settings
from app.utils.logging_filter import RequestIdFilter

def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    handler.addFilter(RequestIdFilter())
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s"
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    root.handlers = [handler]