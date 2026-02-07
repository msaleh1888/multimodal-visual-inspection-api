# Multimodal Visual Inspection & Explanation API

A **VLM-first**, production-style backend service for analyzing **images and documents** and returning **grounded explanations and recommendations**.

This project is intentionally designed to demonstrate **real-world multimodal system design**, not toy demos or academic experiments.

---

## 🔑 Key Idea (VLM-First)

**Image analysis is performed using a true Vision–Language Model (VLM)**:

> **image + prompt/task → multimodal reasoning → explanation**

The language model reasons **directly over visual input**, not over pre-generated labels.

Vision-only models (e.g., classifiers or embeddings) are supported **only as optional baselines** for debugging and evaluation.

---

## ✨ What This Project Demonstrates

- Correct use of **Vision–Language Models (VLMs)**
- Separation of **perception**, **reasoning**, and **interpretation**
- Production-style API design with FastAPI
- Grounded, explainable outputs (not hallucination-prone demos)
- Swappable model adapters (VLMs, vision baselines, document engines)

This mirrors how **real AI products** are built.

---

## 🧱 System Capabilities

### Image Analysis (Primary)
- Accepts image + optional prompt/task
- Uses a VLM for multimodal reasoning
- Returns:
  - short finding/summary
  - confidence or uncertainty signal
  - grounded explanation
  - recommended next steps

### Image Analysis (Optional Baseline)
- Vision-only classifier or embedding model
- Used for debugging, benchmarking, and comparison
- Never the default path

### Document Analysis
- OCR and layout-aware extraction
- Structured field and table extraction
- Grounded interpretation using language models

---

## 🏗 High-Level Architecture

```
Client
  ↓
FastAPI API
  ↓
Preprocessing (decode / normalize)
  ↓
┌───────────────────────────┐
│ Image → VLM Analyzer      │  ← primary
│ Image → Vision Baseline   │  ← optional
│ Document → Doc Analyzer  │
└───────────────────────────┘
  ↓
Response Assembly
  ↓
JSON Output
```

The architecture is documented in detail in `architecture.md`.

---

## 📡 API Overview

### Image Analysis
`POST /analyze/image`

- Supports:
  - `mode=vlm` (default)
  - `mode=baseline` (optional)
- Accepts optional `prompt` or task-based parameters
- Returns structured and natural-language outputs

### Document Analysis
`POST /analyze/document`

- Accepts PDF or image documents
- Extracts fields/tables
- Generates grounded interpretation

See `api_contract.md` for full request/response schemas.

---

## 🧪 Evaluation Philosophy

The project focuses on **robustness and grounding**, not leaderboard scores:

- Hallucination checks
- Low-confidence surfacing
- Prompt sensitivity testing
- Failure-mode awareness

Evaluation details are documented in `evaluation_plan.md`.

---

## 🛠 Tech Stack

- **Python**
- **FastAPI**
- **Vision–Language Models (VLMs)**
- Optional: vision-only CNN / ViT baselines
- Optional: managed or open-source document understanding engines

---

## 🚫 Explicit Non-Goals

- Training foundation models from scratch
- Domain-specific or regulated claims (e.g., medical diagnosis)
- Frontend/UI development
- Authentication or billing systems

---

## 🎯 Who This Project Is For

- AI / ML Engineers working with multimodal systems
- Backend engineers integrating AI services
- Technical interviewers evaluating applied AI skills
- Teams building explainable AI products

---

## ▶️ Running Locally (Example)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

---

## 📄 Documentation Index

- `requirements.md` — functional and non-functional requirements
- `architecture.md` — system design and data flows
- `modeling_choices.md` — modeling decisions (VLM-first)
- `api_contract.md` — API schema and examples
- `evaluation_plan.md` — evaluation and testing strategy

---

## 🧠 Why This Matters

This project avoids the common mistake of presenting:

> *vision classifier + LLM = VLM*

Instead, it demonstrates **correct multimodal reasoning**, making it suitable for **real production systems and technical interviews**.

---

**End of README**
