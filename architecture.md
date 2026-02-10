# Architecture — Multimodal Visual Inspection API

This document describes the high-level architecture of the Multimodal Visual Inspection API,
its core components, and how data flows through the system.

---

## Architectural Goals

- Clear separation between API, orchestration, and model logic
- Ability to swap models (VLM, LLM, vision backends) without changing workflows
- Robustness against partial failures (page-level, model-level)
- Strong guardrails against LLM hallucinations
- Testability at unit, pipeline, and integration levels

---

## High-Level Overview

The system is organized into layered modules:

```
Client
  |
  v
FastAPI (routes + schemas)
  |
  v
Pipelines (workflow orchestration)
  |
  v
Analyzers / Explainers (model adapters)
  |
  v
Models (VLM, Vision, LLM backends)
```

Each layer depends only on the layer below it.

---

## API Layer (`app/api`)

Responsibilities:
- HTTP request parsing and validation
- Response serialization using strict schemas
- Error mapping to API contract
- Request ID propagation

Key files:
- `routes_image.py`
- `routes_document.py`
- `schemas_image.py`
- `error_handlers.py`

The API layer **does not**:
- Run model inference
- Implement business logic
- Handle retries or timeouts

---

## Pipeline Layer (`app/pipelines`)

Pipelines coordinate multi-step workflows and enforce resilience policies.

### Image Pipeline

File:
- `image_pipeline.py`

Responsibilities:
- Route requests to VLM or baseline vision analyzer
- Handle retries, timeouts, and prompt tightening
- Emit metrics and logs
- Normalize output into a stable boundary object

### Document Pipeline

File:
- `document_pipeline.py`

Responsibilities:
- Iterate over document pages
- Call page-level document analyzers
- Aggregate warnings and confidence
- Guarantee partial results on failure

Design rule:
- One page failure must not fail the entire document.

---

## Preprocessing Layer (`app/preprocessing`)

Responsibilities:
- Validate file type and size
- Decode and normalize inputs
- Convert PDFs into page images
- Prepare inputs for downstream pipelines

Key files:
- `document.py`
- `image_preprocess.py`

Preprocessing errors are mapped early to client-facing errors.

---

## Analyzer Layer (`app/analyzers`)

Analyzers adapt pipelines to concrete model implementations.

### Vision Analyzers

- CNN-based image classifiers (baseline mode)
- Stateless, synchronous

### VLM Analyzers

- Multimodal visual-language models
- Strict JSON output enforcement
- Timeout and retry aware

### Document Analyzer

- Page-level VLM-based extraction
- Returns structured fields, tables, confidence, warnings
- NoOp analyzer used only as a fallback or test stub

Design pattern:
- Pipelines depend on analyzer interfaces, not implementations.

---

## Explainer Layer (`app/explainers`)

The explainer layer uses an LLM to add **grounded explanations**.

Responsibilities:
- Generate explanation, recommendation, and grounding metadata
- Consume only structured outputs from pipelines
- Never introduce new facts

Grounding mechanisms:
- Prompt constraints (use only provided data)
- Fixed JSON schema
- Low temperature settings
- Explicit limitation reporting

---

## Model Backends

Models are treated as interchangeable backends.

Current categories:
- Vision models (e.g., ImageNet CNNs)
- VLMs (visual-language models)
- LLMs (text-only explainers)

Factories (`*_factory.py`) handle model selection and instantiation.

---

## Error Handling Strategy

- Validation errors: API layer (400–422)
- Model timeouts: mapped to 504
- Invalid model output: mapped to 502
- Unexpected failures: converted to safe, typed errors

Unhandled model exceptions never crash the service.

---

## Observability

The system emits:
- Structured logs with request IDs
- Prometheus-style metrics
- Timing and retry counters

Key goals:
- Debuggability
- Performance visibility
- Model behavior monitoring

---

## Testing Strategy (Architectural View)

Tests are layered to match architecture:

- Unit tests: individual functions and adapters
- Pipeline tests: orchestration logic
- API tests: request/response validation
- Integration tests: end-to-end workflows

Mocks and NoOp analyzers are used to isolate layers.

---

## Key Architectural Invariants

- API schemas are strict (extra fields forbidden)
- Pipelines are model-agnostic
- Models never talk directly to HTTP
- Partial failures are tolerated
- Hallucination risk is explicitly surfaced

---
