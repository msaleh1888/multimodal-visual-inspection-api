# Repository Structure

This repository follows a **production-oriented, modular layout** separating API concerns, orchestration logic, model adapters, preprocessing, and observability.

---

## Root

```
.
├── app/
├── samples/
├── scripts/
├── tests/
├── README.md
├── requirements.md
├── architecture.md
├── api_contract.md
├── modeling_choices.md
├── evaluation_plan.md
├── repo_structure.md
└── pyproject.toml / requirements.txt
```

---

## `app/` — Application Code

```
app/
├── main.py
├── config.py
├── logging.py
├── middleware/
├── utils/
├── api/
├── preprocessing/
├── analyzers/
├── pipelines/
└── observability/
```

---

### `app/main.py`
- FastAPI application factory  
- Global middleware wiring (request IDs, error handling)  
- Router registration  
- Logging initialization  

---

### `app/config.py`
- Centralized configuration using `pydantic-settings`
- Environment-driven settings (VLM provider, limits, timeouts)

---

### `app/logging.py`
- Central logging configuration
- Structured logs with request IDs
- Log level controlled via config

---

### `app/middleware/`

```
middleware/
├── request_id.py
```

- Request ID middleware
- Ensures every request has a unique correlation ID

---

### `app/utils/`

```
utils/
├── request_id.py
├── logging_filter.py
```

- Request ID context utilities
- Logging filters to inject request IDs into logs

---

## `app/api/` — HTTP API Layer (Thin)

```
api/
├── routes_image.py
├── routes_document.py
├── health.py
```

- Responsible only for:
  - HTTP request parsing
  - File upload handling
  - Calling pipelines
  - Returning JSON responses
- No ML logic or orchestration here

---

## `app/preprocessing/`

```
preprocessing/
├── image_preprocess.py
├── document_preprocess.py
```

- Input validation and preprocessing
- Image decoding, size limits, EXIF correction
- Document normalization and splitting

---

## `app/analyzers/` — Model Adapters

```
analyzers/
├── vlm_base.py
├── vlm_factory.py
├── vlm_mock.py
├── vlm_transformers.py
├── vlm_runner.py
├── vlm_errors.py
│
├── vision_base.py
├── vision_resnet.py
├── vision_factory.py
```

### VLM analyzers
- Adapter-based design for Vision–Language Models
- Supports:
  - Mock VLM (dev)
  - Transformers-based VLMs
- Retry, timeout, and invalid-output handling

### Vision-only analyzers (baseline)
- ResNet18 ImageNet-pretrained classifier
- Provides:
  - Top-K predictions
  - Embedding extraction (512-dim)
- Used for debugging, sanity checks, and potential fallback

---

## `app/pipelines/` — Orchestration Layer

```
pipelines/
├── image_pipeline.py
```

- Core orchestration logic for image analysis
- Responsibilities:
  - Route between VLM and baseline modes
  - Handle retries, timeouts, and failures
  - Emit metrics and logs
  - Return normalized pipeline results
- Keeps API layer thin and policy-free

---

## `app/observability/`

```
observability/
├── metrics.py
├── metrics_route.py
```

- Prometheus-compatible metrics
- Tracks:
  - Request counts (VLM + baseline)
  - Inference latency histograms
- `/metrics` endpoint exposed for scraping

---

## `samples/`

```
samples/
├── images/
│   └── sample.jpg
├── documents/
```

- Sample inputs for local testing and demos
- Used for smoke tests and manual validation

---

## `scripts/`

```
scripts/
```

- (Optional) Local utilities, experiments, or smoke tests
- Not required for core runtime

---

## `tests/`

```
tests/
```

- Unit tests and integration tests (planned in later milestones)
- Will cover:
  - Preprocessing
  - Pipelines
  - API endpoints

---

## Design Summary

- **API layer**: thin, stable
- **Pipelines**: orchestration and policy
- **Analyzers**: model adapters
- **Observability**: first-class (metrics + logs)
- **Docs**: aligned with real implementation

This structure mirrors real-world production ML services and is intentionally designed for extensibility and testability.
