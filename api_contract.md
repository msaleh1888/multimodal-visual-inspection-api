# API Contract — Multimodal Visual Inspection API

This document defines the external HTTP contract for the Multimodal Visual Inspection API.
All responses are JSON and validated against strict schemas. Extra fields are forbidden unless explicitly documented.

---

## Base URL

POST /analyze/image  
POST /analyze/document

---

## Common Headers

| Header | Required | Description |
|------|----------|-------------|
| X-Request-Id | No | Optional client-provided request ID for request tracing |

---

## POST /analyze/image

Analyze a single image using either:
- VLM mode (multimodal visual-language reasoning)
- Baseline mode (vision-only classifier, debug/fallback)

### Request (multipart/form-data)

| Field | Type | Required | Description |
|------|------|----------|-------------|
| file | file | Yes | Image file (PNG or JPEG) |
| mode | string | No | vlm (default) or baseline |

---

### Success Response — 200 OK

```json
{
  "finding": "visual_summary_placeholder",
  "confidence": 0.2,
  "details": {
    "mode": "vlm",
    "model": {
      "name": "mock-vlm",
      "version": "0.1"
    },
    "meta": {
      "duration_ms": 0,
      "attempts_used": 1
    },
    "grounding": {
      "risk_level": "high",
      "assumptions": [],
      "limitations": [
        "The analysis contains warnings that reduce confidence.",
        "LLM JSON missing required keys"
      ],
      "llm_model": "mock-llm-v1"
    },
    "vlm": {
      "task": "",
      "prompt": "",
      "raw_output": "[MOCK] prompt= task= question=None"
    }
  },
  "explanation": "A detailed explanation could not be generated reliably from the available analysis results.",
  "recommendation": "Review the extracted results manually and verify low-confidence items.",
  "warnings": [
    "empty_prompt_used_default_behavior"
  ]
}
```

---

### Image details object

- details.mode: vlm or baseline
- details.model: model name and version
- details.meta: optional runtime metadata
- details.grounding: optional LLM grounding metadata
- details.vlm: present only in vlm mode
- details.baseline: present only in baseline mode

Extra fields are forbidden.

---

## POST /analyze/document

Analyze a document (PDF or image) using page-based visual-language analysis.

### Request (multipart/form-data)

| Field | Type | Required | Description |
|------|------|----------|-------------|
| file | file | Yes | PDF or image file |
| mode | string | No | fast or full |
| max_pages | integer | No | Maximum number of pages to process (default: 10) |

---

### Success Response — 200 OK

```json
{
  "finding": "Extracted 0 field(s) and 0 table(s) from the document.",
  "confidence": 0.0,
  "details": {
    "extracted_fields": {},
    "tables": [],
    "model": {
      "name": "document",
      "version": "v1"
    }
  },
  "explanation": "The system processed the document page-by-page.",
  "recommendation": "Validate extracted values manually.",
  "warnings": [
    "page[0]: Model output is not valid JSON; using empty extraction."
  ]
}
```

---

## Error Response (All Endpoints)

```json
{
  "error": {
    "code": "invalid_parameters",
    "message": "mode must be 'vlm' or 'baseline'",
    "request_id": "abc-123"
  }
}
```

---

## Contract Invariants

- Extra response fields are forbidden
- Optional fields may be omitted
- Grounding metadata is optional and best-effort
- API responses are stable across minor model changes
