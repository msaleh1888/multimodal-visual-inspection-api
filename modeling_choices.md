# Modeling Choices

## 1. Purpose

This document explains the modeling approach and why the project focuses on **pre-trained models** and **adapter-based integration** rather than training large models from scratch.

The core intent is to demonstrate how real-world multimodal systems are built:

- perception (vision/document understanding) produces structured signals
- reasoning (LLM) produces grounded explanations and recommendations

---

## 2. Design Principles

1. **Production realism**
   - Most applied teams use pre-trained vision and multimodal models.
   - Training foundation models is rarely required for product delivery.

2. **Swappable components**
   - Each model/service is accessed through an adapter interface.
   - We can replace a model without rewriting the pipeline.

3. **Grounded language output**
   - LLM output must be constrained to extracted findings.
   - The LLM is treated as a controlled explanation layer.

4. **Cost/latency awareness**
   - Use fast perception first, richer reasoning second.
   - Keep heavy multimodal reasoning optional.

---

## 3. Image Analyzer Options

The image analyzer produces:
- a primary finding/label
- confidence
- optional top-k evidence

### Option A (Default): Pre-trained Vision Classifier (CNN/ViT)

**What it is**
- A pre-trained vision backbone (CNN or ViT) with a lightweight classification head.
- Can be used as-is or with minimal fine-tuning (optional extension).

**Why it fits this project**
- Demonstrates standard applied CV workflow.
- Produces stable, interpretable outputs (labels + confidence).
- Efficient for synchronous API inference.

**Tradeoffs**
- Limited reasoning on its own (no natural language).
- Best for detection/classification tasks.

### Option B: Vision Encoder Producing Embeddings (for similarity/retrieval)

**What it is**
- A pre-trained vision encoder that outputs embeddings.

**Use cases**
- Similarity search
- Near-duplicate detection
- Clustering

**Why it matters**
- Embeddings mirror how many VLM pipelines work (shared representation space).

**Tradeoffs**
- Requires downstream logic to interpret embeddings (e.g., nearest neighbors).

### Option C: Multimodal Model Used Directly for Image Q&A (Optional)

**What it is**
- A multimodal model that can take an image plus a prompt and generate text.

**Why it’s optional**
- Higher cost/latency.
- Requires more careful safety/grounding.

**Best use**
- “Explain what you see” style prompts.

---

## 4. Document Analyzer Options

The document analyzer produces:
- extracted fields/tables
- confidence
- optional layout metadata

### Option A (Default): Managed Document Understanding Service

**What it is**
- A cloud service that performs OCR + layout + key-value extraction.

**Why it fits this project**
- Closest to how enterprise document pipelines are implemented.
- Produces structured JSON reliably.
- Handles PDFs, multi-page documents, and layout variation.

**Tradeoffs**
- External dependency.
- Requires credentials and network access.

### Option B: Local OCR + Parsing Pipeline

**What it is**
- OCR engine + document parsing heuristics.

**Why it’s useful**
- Fully local development and reproducibility.

**Tradeoffs**
- Lower accuracy and higher engineering effort.
- Harder to generalize across document formats.

### Option C: VLM-based Document Q&A (Optional)

**What it is**
- Use a multimodal model to answer questions about the document image.

**Why it’s optional**
- Excellent for interpretation, but may be less deterministic for extraction.

**Recommended pattern**
- Extract structured fields first (Option A/B)
- Use VLM/LLM second for interpretation

---

## 5. LLM Explainer Choices

The LLM explainer receives structured findings and produces:
- explanation
- recommendation
- optional warnings/uncertainty notes

### Prompting Strategy (Grounded-by-Design)

- Provide the LLM a structured JSON context:
  - labels/fields/confidence
  - missing fields
- Instruct:
  - do not invent values
  - refer only to provided data
  - if uncertain, say so and propose next action

### Output Style

- Neutral, domain-agnostic language
- Avoid regulated claims
- “Possible issue” / “Suggested next step” phrasing

---

## 6. Recommended Baseline Configuration

To keep the project practical, reproducible, and impressive:

- **Image Analyzer:** Option A (pre-trained classifier) or Option B (embeddings)
- **Document Analyzer:** Option A (managed document service) with Option B as local fallback
- **LLM Explainer:** grounded prompt strategy + structured response schema

This baseline provides the strongest interview narrative:

- real-world perception components
- production-style extraction
- controlled reasoning layer
- clear modularity

---

## 7. Optional Extensions (If Time Allows)

### Extension 1: Lightweight Fine-Tuning
- Fine-tune the image classifier on a small public dataset.
- Keep it clearly optional.

### Extension 2: Retrieval-Augmented Explanation
- Store past findings in a vector DB.
- Retrieve similar cases to improve explanations.

### Extension 3: Multimodal Q&A Mode
- Add a third endpoint:
  - `POST /analyze/qa`
- Accept image + question and return answer.

---

## 8. Why We Avoid Training Foundation Models

Training large multimodal models from scratch is:
- expensive
- slow
- unnecessary for most product teams

The project instead demonstrates the skills hiring teams look for:

- selecting the right pre-trained model
- building reliable pipelines around it
- evaluation and failure handling
- deployment and observability
- producing grounded, user-facing explanations

---

**End of Modeling Choices**

