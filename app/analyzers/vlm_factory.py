from app.config import settings
from app.analyzers.vlm_base import VLMImageAnalyzer
from app.analyzers.vlm_mock import MockVLMAnalyzer
from app.analyzers.vlm_transformers import TransformersVLMAnalyzer


def create_vlm_analyzer() -> VLMImageAnalyzer:
    provider = settings.vlm_provider.lower()

    if provider == "mock":
        return MockVLMAnalyzer()

    if provider == "transformers":
        return TransformersVLMAnalyzer(
            model_id=settings.vlm_model_id
        )

    raise ValueError(f"Unsupported VLM provider: {provider}")