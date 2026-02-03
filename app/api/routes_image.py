from fastapi import APIRouter, File, UploadFile

from app.config import settings
from app.preprocessing.image_preprocess import load_and_preprocess_image

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post("/image")
async def analyze_image(file: UploadFile = File(...), mode: str = "full"):
    img = await load_and_preprocess_image(
        file,
        max_mb=settings.max_image_mb,
        target_size=(224, 224),
    )

    # Analyzer not implemented yet; show preprocessing output only
    return {
        "finding": "preprocessed_image_ready",
        "confidence": 0.0,
        "details": {
            "input": {"filename": file.filename, "content_type": file.content_type},
            "preprocessing": {"width": img.width, "height": img.height, "dtype": str(img.array.dtype)},
        },
        "explanation": "Image validated and normalized. Ready for image analyzer inference.",
        "recommendation": "Next: run the image analyzer adapter to produce labels and confidence.",
        "warnings": [],
    }