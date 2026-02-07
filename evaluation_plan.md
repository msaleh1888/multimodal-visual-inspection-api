# Evaluation Plan (VLM-First)

## 1. Purpose

This document defines how the system is evaluated to ensure:
- correct multimodal reasoning
- grounded outputs
- robustness to real-world inputs
- production-readiness

The evaluation strategy is **VLM-aware** and explicitly avoids treating image analysis as a pure classification problem.

---

## 2. Evaluation Principles

1. **Grounding over fluency**
   - Outputs must be supported by visual or extracted evidence.
   - Fluent but unsupported explanations are considered failures.

2. **Uncertainty awareness**
   - Low-quality or ambiguous inputs must surface uncertainty.
   - Overconfident answers are penalized.

3. **Mode-aware evaluation**
   - VLM mode and vision-only baseline mode are evaluated differently.
   - Metrics must match the modeling approach.

---

## 3. Image Analysis Evaluation (VLM Mode — Primary)

### 3.1 Multimodal Grounding Tests

**Goal:** Ensure language output is grounded in visual input.

Checks:
- Does the explanation reference visible attributes (objects, colors, spatial relations)?
- Are claims consistent with the image content?
- Are absent elements explicitly not hallucinated?

Examples:
- Image without defects → no defect mentioned
- Blurry image → uncertainty surfaced

---

### 3.2 Hallucination Detection

**Goal:** Detect unsupported or fabricated claims.

Checks:
- Mentions of objects not present in the image
- Inference of hidden/internal states without evidence
- Overly specific claims from low-resolution images

Evaluation:
- Manual review for early iterations
- Rule-based heuristics for common hallucination patterns

---

### 3.3 Prompt Sensitivity & Robustness

**Goal:** Ensure stable behavior across prompt variations.

Checks:
- Equivalent prompts produce consistent findings
- Prompt injection attempts do not override visual evidence
- Empty or vague prompts still produce safe, minimal outputs

---

### 3.4 Confidence Calibration

**Goal:** Align confidence scores with output reliability.

Checks:
- Clear images → higher confidence
- Occluded/low-quality images → lower confidence
- Ambiguous cases → explicit warnings

---

## 4. Image Analysis Evaluation (Vision-Only Baseline — Optional)

These metrics apply **only** when baseline mode is enabled.

### 4.1 Perception Accuracy

- Top-k label sanity checks
- Gross misclassification detection

### 4.2 Stability

- Consistent predictions for the same image
- Sensitivity to small perturbations

> Note: Baseline metrics are **not** the primary success signal for the project.

---

## 5. Document Analysis Evaluation

### 5.1 Extraction Accuracy

- Correct field extraction
- Table structure preservation
- Confidence score reasonableness

### 5.2 Interpretation Grounding

- Explanations reference extracted fields
- Missing or low-confidence fields trigger warnings
- No invented values

---

## 6. End-to-End API Evaluation

### 6.1 Error Handling

- Unsupported file types → `400`
- Oversized payloads → `413`
- Corrupt inputs → `422`
- Downstream failures → `502` / `504`

### 6.2 Latency & Stability

- Single-request latency within acceptable bounds
- No crashes on malformed inputs
- Graceful degradation on model failure

---

## 7. Regression & Change Safety

- Snapshot tests for representative images/documents
- Compare outputs before/after model or prompt changes
- Manual review of diffs for reasoning changes

---

## 8. What Is Explicitly NOT Evaluated

- Medical, legal, or regulated correctness
- Dataset-level accuracy benchmarks
- Competitive leaderboard performance

---

## 9. Success Criteria

The system passes evaluation if:

- VLM image analysis produces grounded, visually consistent explanations
- Hallucinations are rare and detectable
- Confidence reflects actual uncertainty
- Document analysis remains deterministic and explainable
- The system can be explained clearly in a technical interview

---

## 10. Continuous Improvement

Evaluation artifacts (images, prompts, outputs) should be versioned and reused to:
- detect regressions
- validate new VLMs
- justify architectural decisions

---

**End of Evaluation Plan**
