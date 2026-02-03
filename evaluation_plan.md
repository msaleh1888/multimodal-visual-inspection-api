# Evaluation Plan

## 1. Purpose

This project is evaluated as a **production-style multimodal system**, not just a model demo.

Evaluation focuses on:

1. **Perception quality** (image classification / document extraction)
2. **Robustness** to real-world input issues
3. **Reasoning quality** (LLM explanations and recommendations)
4. **Grounding** (no invented facts)
5. **System performance** (latency, reliability)

---

## 2. Evaluation Scope

### In scope
- Image endpoint: `/analyze/image`
- Document endpoint: `/analyze/document`
- LLM explanation layer (grounding + clarity)
- End-to-end pipeline behavior (errors, timeouts, logging)

### Out of scope
- Training-based model benchmarking at scale
- Regulated domain correctness (medical/agriculture specifics)

---

## 3. Test Datasets (Small, Public, Reproducible)

### 3.1 Images
- A small set of public images representing typical inputs:
  - clean images
  - low-light images
  - blurred images
  - rotated images

**Goal:** validate robustness and correct failure handling.

### 3.2 Documents
- A small set of public/sample PDFs and scanned documents:
  - clean, digital PDFs
  - scanned documents
  - multi-page PDFs
  - rotated pages

**Goal:** validate extraction quality and handling of format variability.

### 3.3 Synthetic Inputs
- Programmatically modified samples:
  - downscaled resolution
  - added noise
  - skew/rotation
  - partial crops

**Goal:** systematic robustness testing.

---

## 4. Perception Evaluation

### 4.1 Image Analyzer Metrics

Depending on the analyzer mode:

- **Top-1 accuracy** (if ground-truth labels exist)
- **Top-k accuracy** (recommended)
- **Confidence calibration sanity checks**
  - high confidence should correlate with correctness

**Acceptance criteria (baseline):**
- Model returns a label and confidence for valid images.
- For low-quality images, model still returns output but includes warnings or low confidence.

### 4.2 Document Analyzer Metrics

- **Field extraction coverage**
  - percentage of required fields extracted
- **Field correctness (spot check)**
  - manual verification for a small subset
- **Confidence sanity checks**
  - missing/uncertain fields should lower overall confidence

**Acceptance criteria (baseline):**
- Extracts at least a minimal set of fields for standard documents.
- Correctly reports missing fields and uncertainty.

---

## 5. Reasoning & Explanation Evaluation (LLM)

Evaluation here is about **clarity and grounding**, not “creativity”.

### 5.1 Output Quality Dimensions

1. **Clarity**
   - easy to understand
   - concise and structured

2. **Actionability**
   - recommendations are specific and reasonable

3. **Consistency**
   - similar inputs produce similar style and structure

4. **Uncertainty handling**
   - low confidence triggers warnings and conservative language

### 5.2 Grounding Checks (Critical)

The LLM must not invent facts.

We validate grounding with rules:

- **No new numbers/fields:**
  - if a value is not present in `details`, it must not appear in explanation

- **No unsupported claims:**
  - explanation must reference only provided labels/fields

- **Uncertainty propagation:**
  - if confidence < threshold, explanation includes a warning

**Acceptance criteria (baseline):**
- 0 hallucinated fields in a curated test set.

---

## 6. End-to-End Scenarios (Golden Tests)

Create a small set of “golden” scenarios with expected behavior:

### Image scenarios
- Clean image → confident finding + normal explanation
- Low-light image → lower confidence + warning
- Corrupt image → 422 error

### Document scenarios
- Digital PDF → good extraction + confident explanation
- Rotated scan → partial extraction + warning
- Too many pages → 413 error

Golden tests validate:
- stable response schema
- deterministic error handling
- consistent warning logic

---

## 7. Robustness & Failure Testing

### 7.1 Input Robustness
- Test multiple image sizes, formats, and edge cases
- Test PDF rendering failures
- Validate file size/page limits

### 7.2 Timeout/Retry Behavior
- Simulate slow analyzer/LLM calls
- Confirm the API returns `504` on timeouts
- Confirm logs capture stage + request_id

---

## 8. Performance Evaluation

### Metrics
- End-to-end latency (p50, p95)
- Per-stage latency breakdown:
  - preprocessing
  - perception
  - LLM

### Targets (baseline, local dev)
- Image pipeline: reasonable response time for small images
- Document pipeline: acceptable response time for small PDFs

(Exact thresholds depend on selected analyzers and environment.)

---

## 9. Test Strategy (How we implement evaluation)

### 9.1 Unit Tests
- Preprocessing functions
- Schema validation
- Field normalization logic

### 9.2 Integration Tests
- API endpoints with sample files
- Analyzer adapters mocked where needed

### 9.3 Contract Tests
- Verify response schema stays stable
- Verify error schema stays stable

### 9.4 LLM Output Tests
- Rule-based grounding checks (no new fields)
- Snapshot tests for style/structure (optional)

---

## 10. Reporting

Evaluation outputs should be recorded in:

- `docs/evaluation_report.md` (summary of results)
- optional: a small CSV/JSON file of test outcomes

Report should include:
- what was tested
- key failure modes found
- how they were mitigated

---

## 11. Definition of Done

The system is “evaluation-complete” when:

- Golden tests pass for both endpoints
- Grounding checks pass (no hallucinated fields in test set)
- Robustness tests cover common input issues
- Performance measurements are collected and documented
- Evaluation report is added to the repo

---

**End of Evaluation Plan**

