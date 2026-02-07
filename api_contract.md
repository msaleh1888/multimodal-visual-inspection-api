# API Contract (VLM-First)

## 1. Overview

This service exposes HTTP APIs for **multimodal analysis of images and documents**.

The system is **VLM-first**:
- Image analysis is performed using a **Vision–Language Model (VLM)** that reasons jointly over **image + prompt/task**.
- Vision-only models are supported only as **optional baselines** for debugging and evaluation.

All successful responses follow a consistent schema:
- `finding`
- `confidence`
- `details`
- `explanation`
- `recommendation`
- optional `warnings`

---

## 2. Common Conventions

### 2.1 Content Types
- Requests: `multipart/form-data`
- Responses: `application/json`

### 2.2 Request Size Limits (recommended defaults)
- Max image size: 10 MB
- Max document size: 20 MB
- Max PDF pages: 10

Limits are configurable.

### 2.3 Request IDs
- The server returns `X-Request-Id` in responses.
- If the client supplies `X-Request-Id`, it is propagated.

---

## 3. Endpoints

## 3.1 `POST /analyze/image`

### Purpose
Analyze an image using a **VLM-first** pipeline and return:
- a short summary/finding
- a confidence or uncertainty signal
- a grounded explanation
- a recommendation or next step

---

### Request

**Method:** `POST`  
**Path:** `/analyze/image`  
**Content-Type:** `multipart/form-data`

#### Form Fields

- `file` (required): Image file (`image/jpeg`, `image/png`)
- `mode` (optional): `"vlm" | "baseline"` (default: `"vlm"`)
  - `vlm`: **primary mode** — multimodal reasoning (image + prompt/task)
  - `baseline`: optional vision-only path (classifier/embeddings)
- `prompt` (optional): string  
  - Free-form instruction for the VLM  
  - Example: `"Describe what you see and suggest next steps"`
- `task` (optional): string  
  - Predefined task identifier (e.g. `"describe"`, `"qa"`, `"inspect"`)
- `question` (optional): string  
  - Used when `task="qa"`

**Rules**
- `prompt` and `task` are optional.
- If both are provided, `prompt` takes precedence.
- If `mode="baseline"`, `prompt`, `task`, and `question` are ignored.

---

#### Example — VLM mode (free prompt)

```bash
curl -X POST "http://localhost:8000/analyze/image" \
  -F "file=@samples/images/sample.jpg" \
  -F "mode=vlm" \
  -F "prompt=Describe what you see and suggest next steps"
```

#### Example — VLM Q&A style

```bash
curl -X POST "http://localhost:8000/analyze/image" \
  -F "file=@samples/images/sample.jpg" \
  -F "task=qa" \
  -F "question=Is there anything unusual in this image?"
```

#### Example — Vision-only baseline

```bash
curl -X POST "http://localhost:8000/analyze/image" \
  -F "file=@samples/images/sample.jpg" \
  -F "mode=baseline"
```

---

### Success Response

**Status:** `200 OK`

```json
{
  "finding": "string",
  "confidence": 0.0,
  "details": {
    "mode": "vlm",
    "vlm": {
      "task": "string",
      "prompt": "string",
      "raw_output": "string"
    },
    "labels": [
      { "name": "string", "score": 0.0 }
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

#### Notes
- In **VLM mode**:
  - `details.labels` may be absent or empty.
  - `details.vlm.raw_output` may include a safe subset of model output.
- In **baseline mode**:
  - `details.labels` is expected to be populated.
- `warnings` is optional.

---

### Error Responses
- `400 Bad Request` — unsupported file type / invalid parameters
- `413 Payload Too Large` — file exceeds size limits
- `422 Unprocessable Entity` — corrupt or invalid image
- `502 Bad Gateway` — downstream model/service failure
- `504 Gateway Timeout` — inference timeout

---

## 3.2 `POST /analyze/document`

### Purpose
Analyze a document (PDF or image-based) to:
- extract structured fields and tables
- generate grounded interpretation and recommendations

---

### Request

**Method:** `POST`  
**Path:** `/analyze/document`  
**Content-Type:** `multipart/form-data`

#### Form Fields
- `file` (required): PDF or image (`jpeg/png`)
- `mode` (optional): `"fast" | "full"` (default: `"full"`)
- `max_pages` (optional): integer (default: `10`, PDF only)

---

#### Example

```bash
curl -X POST "http://localhost:8000/analyze/document" \
  -F "file=@samples/docs/sample.pdf" \
  -F "mode=full" \
  -F "max_pages=5"
```

---

### Success Response

```json
{
  "finding": "string",
  "confidence": 0.0,
  "details": {
    "extracted_fields": {
      "field_name": { "value": "string", "confidence": 0.0 }
    },
    "tables": [
      { "name": "string", "rows": [ { "col": "value" } ] }
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

---

### Error Responses
- `400 Bad Request` — unsupported file type / invalid parameters
- `413 Payload Too Large`
- `422 Unprocessable Entity` — corrupt PDF / render failure
- `502 Bad Gateway`
- `504 Gateway Timeout`

---

## 3.3 `GET /healthz`

### Purpose
Health and readiness check.

**Response**
```json
{ "status": "ok" }
```

---

## 4. Error Schema (Global)

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

---

## 5. Grounding & Safety Constraints

- Outputs must be grounded in provided visual or extracted evidence.
- If confidence is low, this must be surfaced explicitly.
- Avoid speculative or domain-specific claims.
- Prefer conservative language (e.g. “possible issue”, “suggested next step”).

---

## 6. Versioning & Metadata

All responses must include model metadata:
- `details.model.name`
- `details.model.version`

This supports reproducibility and safe upgrades.

---

**End of API Contract**
