# API Contract

## 1. Overview

This service exposes two primary endpoints:

- `POST /analyze/image` — analyze a single image
- `POST /analyze/document` — analyze a document (PDF or image-based document)

All successful responses return a consistent top-level schema:

- `finding`
- `confidence`
- `details`
- `explanation`
- `recommendation`
- optional `warnings`

All error responses return a consistent error schema.

---

## 2. Common Conventions

### 2.1 Content Types

- Requests use `multipart/form-data` with a required file field: `file`
- Responses use `application/json`

### 2.2 Request Limits (recommended defaults)

- Max image size: 10 MB
- Max document size: 20 MB
- Max PDF pages: 10

These limits may be adjusted via configuration.

---

## 3. Endpoints

## 3.1 `POST /analyze/image`

### Purpose
Analyze a single image (e.g., photo, screenshot) and return:
- a structured finding
- confidence
- explanation and recommendation

### Request

**Method:** `POST`

**Path:** `/analyze/image`

**Content-Type:** `multipart/form-data`

**Form Fields**
- `file` (required): Image file (JPEG/PNG)
- `mode` (optional): `"fast" | "full"` (default: `"full"`)
  - `fast`: minimal analysis + shorter explanation
  - `full`: include richer evidence and more detailed explanation

#### Example (curl)

```bash
curl -X POST "http://localhost:8000/analyze/image" \
  -F "file=@sample.jpg" \
  -F "mode=full"
```

### Success Response

**Status:** `200 OK`

**Body:**

```json
{
  "finding": "string",
  "confidence": 0.0,
  "details": {
    "labels": [
      {"name": "string", "score": 0.0}
    ],
    "model": {
      "name": "string",
      "version": "string"
    }
  },
  "explanation": "string",
  "recommendation": "string",
  "warnings": ["string"]
}
```

**Notes**
- `details.labels` should contain top-k results when available.
- `warnings` is optional and may be omitted or returned as an empty list.

### Error Responses

- `400 Bad Request` — unsupported file type
- `413 Payload Too Large` — file exceeds size limit
- `422 Unprocessable Entity` — corrupt/invalid image
- `502 Bad Gateway` — downstream model/service failure
- `504 Gateway Timeout` — analyzer/LLM timeout

---

## 3.2 `POST /analyze/document`

### Purpose
Analyze a document (PDF or scanned image document) to:
- extract structured fields/tables
- generate interpretation and recommendation

### Request

**Method:** `POST`

**Path:** `/analyze/document`

**Content-Type:** `multipart/form-data`

**Form Fields**
- `file` (required): PDF or image (JPEG/PNG)
- `mode` (optional): `"fast" | "full"` (default: `"full"`)
- `max_pages` (optional): integer (default: `10`)
  - applies only to PDFs

#### Example (curl)

```bash
curl -X POST "http://localhost:8000/analyze/document" \
  -F "file=@sample.pdf" \
  -F "mode=full" \
  -F "max_pages=5"
```

### Success Response

**Status:** `200 OK`

**Body:**

```json
{
  "finding": "string",
  "confidence": 0.0,
  "details": {
    "extracted_fields": {
      "field_name": {
        "value": "string",
        "confidence": 0.0
      }
    },
    "tables": [
      {
        "name": "string",
        "rows": [
          {"col": "value"}
        ]
      }
    ],
    "model": {
      "name": "string",
      "version": "string"
    }
  },
  "explanation": "string",
  "recommendation": "string",
  "warnings": ["string"]
}
```

**Notes**
- `finding` should be a short, human-readable summary (e.g., “Document processed successfully”, “Missing key fields”).
- `confidence` should reflect overall extraction confidence.

### Error Responses

- `400 Bad Request` — unsupported file type
- `413 Payload Too Large` — file exceeds size limit
- `422 Unprocessable Entity` — corrupt PDF / failed rendering
- `502 Bad Gateway` — downstream document engine failure
- `504 Gateway Timeout` — document engine/LLM timeout

---

## 3.3 `GET /healthz` (recommended)

### Purpose
Health check endpoint for readiness/liveness.

### Request

**Method:** `GET`

**Path:** `/healthz`

### Success Response

**Status:** `200 OK`

```json
{
  "status": "ok"
}
```

---

## 4. Error Schema

All error responses return:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "request_id": "string"
  }
}
```

### Error Codes (recommended)

- `unsupported_file_type`
- `payload_too_large`
- `unprocessable_input`
- `preprocessing_failed`
- `analyzer_failed`
- `llm_failed`
- `timeout`

---

## 5. Grounding & Safety Constraints (LLM Output)

The explanation layer must follow these constraints:

- Use only the structured fields/labels provided in `details`.
- If confidence is low or key fields are missing, return a warning and suggest next steps.
- Avoid domain-specific claims. Use neutral phrasing (e.g., “possible issue”, “recommended action”).

---

## 6. Versioning

The service should expose model metadata in responses:

- `details.model.name`
- `details.model.version`

This enables safe upgrades and reproducibility.

---

## 7. Examples (Human-Readable)

### Image Example
- **finding:** “Possible visual anomaly detected”
- **confidence:** 0.81
- **explanation:** Explains what the model likely saw and why.
- **recommendation:** Suggests capturing a clearer image or next inspection step.

### Document Example
- **finding:** “Key fields extracted with moderate confidence”
- **confidence:** 0.74
- **explanation:** Summarizes extracted fields and highlights missing/uncertain parts.
- **recommendation:** Suggests providing a higher-quality scan or verifying specific fields.

---

**End of API Contract**

