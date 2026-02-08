from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "multimodal-visual-inspection-api"
    log_level: str = "INFO"

    # request limits (can be used later in validation)
    max_image_mb: int = 10
    max_document_mb: int = 20
    max_pdf_pages: int = 10

    # VLM configuration
    vlm_provider: str = "mock"  # "mock" | "transformers"
    vlm_model_id: str = "llava-hf/llava-1.5-7b-hf"

    class Config:
        env_file = ".env"

settings = Settings()