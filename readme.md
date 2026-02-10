# Multimodal Visual Inspection API

A production-style backend service for **image and document analysis** using:
- Vision models (baseline CNNs)
- Visual-Language Models (VLMs)
- Large Language Models (LLMs) for grounded explanations

This project is designed as a **learning-first, production-grade system**:
clear architecture, strict contracts, resilience to failures, and strong testing discipline.

---

## What This Service Does

### Image Analysis
- Accepts PNG/JPEG images
- Supports two modes:
  - `vlm`: multimodal reasoning with explanations and grounding
  - `baseline`: fast vision-only classification (debug/fallback)
- Returns:
  - finding
  - confidence
  - explanation and recommendation
  - optional grounding metadata

### Document Analysis
- Accepts PDFs or images
- Converts documents into page images
- Analyzes each page independently using VLMs
- Aggregates results into a document-level response
- Guarantees partial results even if some pages fail

---

## High-Level Architecture

```
Client
  |
FastAPI (routes + schemas)
  |
Pipelines (workflow orchestration)
  |
Analyzers / Explainers (model adapters)
  |
Models (Vision / VLM / LLM)
```

Key ideas:
- API layer is thin and schema-driven
- Pipelines are model-agnostic
- Models can be swapped without rewriting workflows
- Hallucination risk is explicitly surfaced

---

## API Endpoints

### POST /analyze/image
Analyze a single image.

Modes:
- `vlm` (default)
- `baseline`

### POST /analyze/document
Analyze a document page-by-page.

Options:
- `mode`: `fast` or `full`
- `max_pages`: limit processing cost

See `api_contract.md` for full request/response schemas.

---

## Running Locally

### 1. Create environment

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Start the server

```bash
uvicorn app.main:app --reload
```

Server will be available at:
```
http://127.0.0.1:8000
```

---

## Example Requests

### Image (VLM mode)

```bash
curl -X POST "http://127.0.0.1:8000/analyze/image"   -F "file=@scan.png"   -F "mode=vlm"
```

### Document

```bash
curl -X POST "http://127.0.0.1:8000/analyze/document"   -F "file=@test.pdf"   -F "mode=full"   -F "max_pages=2"
```

---

## Grounding and Hallucination Control

This system explicitly addresses LLM hallucinations by:
- Constraining prompts to provided data only
- Enforcing strict JSON output schemas
- Using low-temperature settings
- Surfacing limitations and uncertainty in responses

Grounding metadata includes:
- risk level
- assumptions
- limitations
- explainer model identity

---

## Testing Strategy

Tests mirror the architecture:

- `tests/preprocessing`: input validation and decoding
- `tests/analyzers`: model adapters
- `tests/pipelines`: orchestration logic
- `tests/explainers`: grounding and explanation
- `tests/api`: contract-level validation
- `tests/integration`: end-to-end flows

Run all tests:

```bash
pytest
```

---

## Project Status

Implemented:
- Image analysis pipeline (VLM + baseline)
- Document analysis pipeline (page-based)
- Grounded LLM explainer
- Strict API contracts
- Unit, pipeline, and API tests

Planned:
- Full integration tests
- Model benchmarking
- Performance tuning
- Deployment configuration

---

## Learning Goals

This project is intentionally structured to practice:
- Backend system design
- Clean architecture
- Model abstraction and swapping
- Reliability and failure handling
- Testing discipline for ML systems

---
