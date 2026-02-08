from __future__ import annotations

from app.config import settings
from app.analyzers.vlm_mock import MockVLMAnalyzer


def create_vlm_analyzer():
    """
    Factory for VLM analyzers.

    Key design choice: lazy-import the transformers-based analyzer so the app can
    start in mock mode even if transformers/torch are not installed correctly.
    """
    provider = (settings.vlm_provider or "mock").strip().lower()

    if provider == "mock":
        return MockVLMAnalyzer()

    if provider == "transformers":
        # Lazy import to avoid crashing app startup when provider != transformers
        from app.analyzers.vlm_transformers import TransformersVLMAnalyzer

        return TransformersVLMAnalyzer(
            model_id=settings.vlm_model_id,
        )

    raise ValueError(f"Unsupported VLM provider: {provider}")