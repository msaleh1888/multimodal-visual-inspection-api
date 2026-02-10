# Repository Structure — Multimodal Visual Inspection API

This document describes the repository layout and the responsibility of each directory.
The structure reflects the architectural separation between API, pipelines, analyzers, and models.

---

## Top-Level Layout

```
.
├── app/
├── tests/
├── README.md
├── requirements.txt
└── pyproject.toml
```

---

## Application Code (`app/`)

```
app/
├── api/
├── analyzers/
├── explainers/
├── middleware/
├── observability/
├── pipelines/
├── preprocessing/
├── config.py
├── main.py
```

Each subdirectory represents a **single architectural responsibility**.

---

## API Layer (`app/api/`)

```
api/
├── routes_image.py
├── routes_document.py
├── schemas_image.py
├── error_handlers.py
├── health.py
```

Responsibilities:
- HTTP endpoints
- Request parsing
- Response serialization
- Error mapping

Design rules:
- No model logic
- No orchestration logic
- Strict schema enforcement

---

## Analyzers (`app/analyzers/`)

```
analyzers/
├── document_analyzer.py
├── vlm_base.py
├── vlm_factory.py
├── vlm_runner.py
├── vlm_errors.py
├── vlm_transformers.py
├── vision_base.py
├── vision_factory.py
```

Responsibilities:
- Adapt pipelines to specific model APIs
- Enforce input/output contracts
- Handle model-specific errors

Notes:
- Pipelines depend on analyzer interfaces, not implementations
- Factories control which model is active

---

## Explainers (`app/explainers/`)

```
explainers/
├── grounded_explainer.py
```

Responsibilities:
- Generate explanations and recommendations using LLMs
- Produce grounding metadata (risk, assumptions, limitations)
- Never introduce new facts beyond pipeline output

---

## Pipelines (`app/pipelines/`)

```
pipelines/
├── image_pipeline.py
├── document_pipeline.py
```

Responsibilities:
- Orchestrate multi-step workflows
- Apply retries, timeouts, and resilience policies
- Aggregate results into stable outputs

Design rule:
- Pipelines are model-agnostic

---

## Preprocessing (`app/preprocessing/`)

```
preprocessing/
├── document.py
├── image_preprocess.py
```

Responsibilities:
- Validate and normalize raw inputs
- Convert PDFs into page images
- Prepare data for pipelines

---

## Middleware (`app/middleware/`)

```
middleware/
├── request_id.py
```

Responsibilities:
- Inject and propagate request IDs
- Ensure traceability across logs and metrics

---

## Observability (`app/observability/`)

```
observability/
├── metrics.py
```

Responsibilities:
- Define Prometheus-style metrics
- Track model usage, latency, and failures

---

## Configuration

```
config.py
```

Responsibilities:
- Centralized runtime configuration
- Environment-based settings

---

## Entry Point

```
main.py
```

Responsibilities:
- FastAPI app creation
- Router registration
- Middleware setup

---

## Tests (`tests/`)

```
tests/
├── analyzers/
├── api/
├── contract/
├── explainers/
├── integration/
├── pipelines/
├── preprocessing/
├── unit/
```

Test categories mirror the application layers.

---

## Key Structural Invariants

- One directory = one responsibility
- API layer never imports model backends directly
- Pipelines isolate workflow complexity
- Tests mirror production architecture

---
