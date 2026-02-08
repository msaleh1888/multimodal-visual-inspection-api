import logging
from fastapi import APIRouter, File, UploadFile, Form

from app.config import settings
from app.preprocessing.image_preprocess import load_and_preprocess_image
from app.pipelines.image_pipeline import ImageAnalysisPipeline

router = APIRouter(prefix="/analyze", tags=["analyze"])
logger = logging.getLogger(__name__)

_pipeline = ImageAnalysisPipeline()


@router.post("/image")
async def analyze_image(
    file: UploadFile = File(...),
    mode: str = Form("vlm"),
    prompt: str = Form(""),
    task: str = Form(""),
    question: str = Form(""),
):
    # 1) Preprocess (file size checks + decode + EXIF fix + RGB conversion)
    img = await load_and_preprocess_image(
        file,
        max_mb=settings.max_image_mb,
        target_size=None,      # let analyzers decide
        return_array=False,    # pipeline/analyzers use PIL
    )

    # 2) Delegate orchestration to pipeline (routing + metrics + retries)
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

    # 3) Optional: minimal request log at API layer (pipeline already logs too)
    logger.info(
        "image_endpoint_ok mode=%s filename=%s content_type=%s",
        mode,
        file.filename,
        file.content_type,
    )

    return result.to_dict()