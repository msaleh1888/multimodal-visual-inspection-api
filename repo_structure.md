# Repository Structure

## 1. Overview

This repository is organized to reflect **production-grade applied AI projects**:

- Clear separation of concerns
- Swappable ML components
- Testable, observable pipelines
- Easy navigation for reviewers and interviewers

The structure is intentionally explicit rather than minimal, to show engineering discipline.

---

## 2. Top-Level Layout

```text
multimodal-visual-inspection-api/
├── README.md
├── requirements.md
├── architecture.md
├── api_contract.md
├── modeling_choices.md
├── evaluation_plan.md
├── repo_structure.md
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── logging.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes_image.py
│   │   ├── routes_document.py
│   │   └── health.py
│   │
│   ├── pipelines/
│   │   ├── __init__.py
│   │   ├── image_pipeline.py
│   │   └── document_pipeline.py
│   │
│   ├── preprocessing/
│   │   ├── __init__.py
│   │   ├── image_preprocess.py
│   │   └── document_preprocess.py
│   │
│   ├── analyzers/
│   │   ├── __init__.py
│   │   ├── image_analyzer.py
│   │   ├── document_analyzer.py
│   │   └── base.py
│   │
│   ├── reasoning/
│   │   ├── __init__.py
│   │   ├── llm_client.py
│   │   └── explainer.py
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── request.py
│   │   └── response.py
│   │
│   └── utils/
│       ├── __init__.py
│       └── file_utils.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── contract/
│
├── docs/
│   ├── diagrams/
│   └── evaluation_report.md
│
├── scripts/
│   ├── run_local.sh
│   └── sample_requests.sh
│
├── .env.example
├── pyproject.toml
├── Dockerfile
└── .gitignore
```

---

## 3. Core Application (`app/`)

### 3.1 Entry Point

**`app/main.py`**
- Creates FastAPI app
- Registers routers
- Initializes logging and config

---

### 3.2 API Layer (`app/api/`)

**Purpose:** HTTP contract and request handling only.

- `routes_image.py` — `/analyze/image`
- `routes_document.py` — `/analyze/document`
- `health.py` — `/healthz`

Rules:
- No ML logic here
- Only validation, routing, and orchestration calls

---

### 3.3 Pipelines (`app/pipelines/`)

**Purpose:** Orchestrate end-to-end workflows.

- `image_pipeline.py`
  - preprocessing → image analyzer → findings → LLM explainer

- `document_pipeline.py`
  - preprocessing → document analyzer → findings → LLM explainer

This is where business logic lives.

---

### 3.4 Preprocessing (`app/preprocessing/`)

**Purpose:** Handle real-world input messiness.

- `image_preprocess.py`
  - decode, resize, normalize

- `document_preprocess.py`
  - PDF rendering, page limits, image normalization

Stateless and testable.

---

### 3.5 Analyzers (`app/analyzers/`)

**Purpose:** Wrap perception models/services.

- `base.py`
  - common interface (analyze → structured result)

- `image_analyzer.py`
  - pre-trained vision model adapter

- `document_analyzer.py`
  - document understanding service adapter

Adapters isolate external dependencies.

---

### 3.6 Reasoning Layer (`app/reasoning/`)

**Purpose:** Controlled language output.

- `llm_client.py`
  - LLM API wrapper

- `explainer.py`
  - prompt templates
  - grounding rules
  - explanation + recommendation generation

No perception logic here.

---

### 3.7 Schemas (`app/schemas/`)

**Purpose:** Stable contracts.

- `request.py` — request models
- `response.py` — response models

Ensures API consistency and testability.

---

### 3.8 Utilities (`app/utils/`)

Shared helpers:
- file handling
- MIME/type checks
- ID generation

---

## 4. Tests (`tests/`)

### 4.1 Unit Tests

- preprocessing functions
- schema validation
- findings builder

### 4.2 Integration Tests

- API endpoints with sample files
- analyzer adapters (mocked where needed)

### 4.3 Contract Tests

- Response schema stability
- Error schema stability

---

## 5. Documentation (`docs/`)

- `diagrams/` — exported architecture diagrams
- `evaluation_report.md` — evaluation results

Keeps repo reviewer-friendly.

---

## 6. Scripts (`scripts/`)

Helper scripts:
- `run_local.sh` — start API locally
- `sample_requests.sh` — example curl calls

---

## 7. Configuration & Deployment

- `.env.example` — environment variables template
- `pyproject.toml` — dependencies and tooling
- `Dockerfile` — containerized deployment

---

## 8. Why This Structure Matters (Interview Framing)

This structure demonstrates:

- Clear separation of ML, reasoning, and API layers
- Production-ready organization
- Easy extensibility (new analyzers, new pipelines)
- Testability and observability

In interviews, this shows the ability to design and maintain **real AI systems**, not just notebooks.

---

**End of Repository Structure**

