import logging
from fastapi import APIRouter, File, UploadFile, Form, HTTPException

from app.config import settings
from app.preprocessing.image_preprocess import load_and_preprocess_image
from app.pipelines.image_pipeline import ImageAnalysisPipeline
from app.api.schemas_image import AnalyzeImageResponse

router = APIRouter(prefix="/analyze", tags=["analyze"])
logger = logging.getLogger(__name__)

_pipeline = ImageAnalysisPipeline()


def _validate_text_field(name: str, value: str, max_len: int) -> str:
    v = (value or "").strip()
    if len(v) > max_len:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_parameters", "message": f"{name} exceeds max length {max_len}"},
        )
    return v


def _normalize_mode(mode: str) -> str:
    m = (mode or "").strip().lower() or "vlm"
    if m not in {"vlm", "baseline"}:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_parameters", "message": "mode must be 'vlm' or 'baseline'"},
        )
    return m


@router.post("/image", response_model=AnalyzeImageResponse)
async def analyze_image(
    file: UploadFile = File(...),
    mode: str = Form("vlm"),
    prompt: str = Form(""),
    task: str = Form(""),
    question: str = Form(""),
):
    # 1) Validate inputs early (before downloading/processing large data)
    mode = _normalize_mode(mode)

    # Keep these limits conservative; can be moved to config later if you want.
    prompt = _validate_text_field("prompt", prompt, max_len=2000)
    task = _validate_text_field("task", task, max_len=64)
    question = _validate_text_field("question", question, max_len=512)

    # 2) Preprocess (file size checks + decode + EXIF fix + RGB conversion)
    img = await load_and_preprocess_image(
        file,
        max_mb=settings.max_image_mb,
        target_size=None,
        return_array=False,
    )

    # 3) Delegate orchestration to pipeline (routing + metrics + retries)
    result = await _pipeline.run(
        image_pil=img.pil,
        mode=mode,
        prompt=prompt,
        task=task,
        question=question,
        baseline_top_k=5,
        baseline_return_embedding=True,
        baseline_embedding_preview_len=16,
    )

    # 4) Minimal API log (pipeline already logs detailed info)
    logger.info(
        "image_endpoint_ok mode=%s filename=%s content_type=%s",
        mode,
        file.filename,
        file.content_type,
    )

    # Pydantic response_model will validate this on return
    return result.to_dict()