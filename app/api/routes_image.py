from fastapi import APIRouter, File, UploadFile

router = APIRouter(prefix="/analyze", tags=["analyze"])

@router.post("/image")
async def analyze_image(file: UploadFile = File(...), mode: str = "full"):
    # stub response for now
    return {
        "finding": "not_implemented",
        "confidence": 0.0,
        "details": {"filename": file.filename, "mode": mode},
        "explanation": "Image pipeline not implemented yet.",
        "recommendation": "Implement preprocessing and image analyzer.",
        "warnings": ["stub_response"]
    }