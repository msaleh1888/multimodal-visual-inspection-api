# Modeling Choices — Multimodal Visual Inspection API

This document explains **why specific modeling approaches were chosen**, how they are used in the system,
and what trade-offs they introduce. The focus is on **engineering reasoning**, not model hype.

---

## Design Principles

All modeling choices follow these principles:

- Separate *workflow logic* from *model logic*
- Prefer adapters and interfaces over hard-coded models
- Make uncertainty and failure explicit
- Optimize for debuggability and testability before accuracy

---

## Image Analysis Models

### Baseline Vision Model (CNN)

**Purpose**
- Fast sanity check
- Debugging and fallback
- Cost-efficient inference

**Characteristics**
- Vision-only (no language reasoning)
- Returns top-k class predictions
- Optionally returns embeddings

**Why this exists**
- Provides a stable reference point
- Allows comparison against VLM output
- Useful when VLM is unavailable or too slow

**Trade-offs**
- No semantic reasoning
- Labels may not match domain concepts

---

## Visual-Language Models (VLM)

### Role in the System

VLMs are used for:
- Image understanding with natural language output
- Page-level document analysis
- Structured extraction (fields, tables, confidence)

They form the **core reasoning engine** of the system.

---

### VLM Adapter Pattern

VLMs are accessed through a strict adapter interface:

- Input: image + prompt/task
- Output: structured JSON only
- Errors: timeout, invalid output, model failure

**Why**
- Prevents pipelines from depending on vendor-specific APIs
- Allows local mocks and tests
- Enables future model swapping (local, hosted, open-source)

---

### Output Constraints

VLM outputs are constrained by:
- Explicit prompt instructions
- Required JSON schema
- Validation and retry logic
- Prompt tightening on retries

This reduces hallucinations and parsing failures.

---

## Document Analysis Models

### Page-Level VLM Processing

Documents are processed as **independent pages**.

**Why**
- Limits blast radius of failures
- Enables parallelism
- Keeps hallucinations localized

Each page returns:
- extracted fields
- tables
- page confidence
- warnings

Document-level aggregation happens in the pipeline, not the model.

---

## LLM Explainer

### Purpose

The LLM explainer is **not** responsible for perception.
It only:
- Explains pipeline results
- Generates recommendations
- Reports uncertainty

---

### Grounded Explainer Design

The explainer:
- Consumes only structured pipeline output
- Is forbidden from introducing new facts
- Outputs fixed JSON

Grounding mechanisms:
- Prompt instructions: use only provided data
- Strict JSON schema
- Low temperature
- Explicit limitation reporting

---

## NoOp and Mock Models

### Why They Exist

- Enable test isolation
- Allow development without external dependencies
- Support deterministic unit tests

Used in:
- Unit tests
- Local development
- CI pipelines

---

## Model Configuration and Selection

Model selection is centralized in factory modules:
- `vision_factory.py`
- `vlm_factory.py`

This allows:
- Environment-based model switching
- Safe defaults
- Explicit version tracking

---

## Known Limitations

- No automatic model benchmarking yet
- VLM accuracy depends heavily on prompt quality
- Grounding reduces but does not eliminate hallucinations

---

## Future Improvements

Planned enhancements:
- Quantitative model evaluation
- Model comparison dashboards
- Better confidence calibration
- Domain-specific fine-tuning

---

## Summary

This system treats models as **replaceable components**, not core logic.
Reliability, clarity, and controllability are prioritized over raw model power.

---
