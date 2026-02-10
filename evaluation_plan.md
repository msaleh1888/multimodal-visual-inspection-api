# Evaluation Plan — Multimodal Visual Inspection API

This document describes how the system is evaluated from an engineering perspective.
The focus is on **correctness, reliability, and safety**, not only model accuracy.

---

## Evaluation Goals

The evaluation strategy aims to answer:

- Does the system return valid responses under all expected conditions?
- Are failures isolated and observable?
- Is hallucination risk surfaced and controlled?
- Can changes be made without breaking contracts?

---

## What Is Evaluated

### 1. Preprocessing Correctness

Validated via unit tests.

Checks include:
- File type validation
- Size limits
- Corrupted input handling
- Deterministic resizing and normalization

Relevant tests:
- `tests/preprocessing/`

---

### 2. Analyzer Behavior

Analyzers are evaluated in isolation using mocks and stubs.

Checks include:
- Correct input/output mapping
- Proper error propagation
- Handling of invalid model output
- Timeout behavior

Relevant tests:
- `tests/analyzers/`

---

### 3. Pipeline Orchestration

Pipelines are evaluated as deterministic workflows.

Checks include:
- Page-level isolation (document pipeline)
- Partial failure tolerance
- Warning aggregation
- Confidence aggregation logic

Relevant tests:
- `tests/pipelines/`

---

### 4. API Contract Compliance

The API is evaluated against strict schemas.

Checks include:
- Extra fields are rejected
- Missing optional fields are allowed
- Error responses match the contract

Relevant tests:
- `tests/api/`
- `tests/contract/`

---

### 5. Grounding and Hallucination Control

The explainer is evaluated qualitatively and structurally.

Checks include:
- Output is strictly JSON
- No new facts are introduced
- Limitations and assumptions are present when confidence is low

Relevant tests:
- `tests/explainers/`

---

### 6. End-to-End Integration

Integration tests validate full request flows.

Checks include:
- Image endpoint (VLM and baseline)
- Document endpoint (multi-page)
- Correct interaction between pipelines, analyzers, and explainers

Relevant tests:
- `tests/integration/`

---

## Metrics and Observability

The system emits metrics used for evaluation:

- Request counts (success / failure)
- Inference latency
- Retry counts
- Timeout frequency

These metrics support:
- Regression detection
- Performance tuning
- Model comparison

---

## Non-Goals

The current evaluation plan does NOT include:
- Model accuracy benchmarks
- Dataset-driven scoring
- Automated hallucination detection

These are intentionally deferred.

---

## Manual Review Guidelines

When inspecting outputs manually:

- Verify explanations reference only returned data
- Check that warnings align with low confidence
- Ensure grounding metadata is present when expected

---

## Regression Strategy

Before merging changes:
- All tests must pass
- API schemas must remain backward compatible
- New failure modes must be explicitly handled

---

## Future Evaluation Enhancements

Planned improvements:
- Golden test datasets
- Confidence calibration metrics
- Cross-model comparison
- Automated drift detection

---

## Summary

Evaluation in this system prioritizes:
- Stability over raw accuracy
- Transparency over silent failure
- Safety over overconfidence

---
