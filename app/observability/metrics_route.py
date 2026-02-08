from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

router = APIRouter()

@router.get("/metrics")
def metrics() -> Response:
    """
    Exposes Prometheus metrics in the standard text format.
    Prometheus scrapes this endpoint periodically.
    """
    payload = generate_latest()  # Collect all registered metrics
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)