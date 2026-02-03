from fastapi import APIRouter, File, UploadFile

router = APIRouter(prefix="/analyze", tags=["analyze"])

@router.post("/document")
async def analyze_document(file: UploadFile = File(...), mode: str = "full", max_pages: int = 10):
    return {
        "finding": "not_implemented",
        "confidence": 0.0,
        "details": {"filename": file.filename, "mode": mode, "max_pages": max_pages},
        "explanation": "Document pipeline not implemented yet.",
        "recommendation": "Implement PDF rendering and document analyzer.",
        "warnings": ["stub_response"]
    }