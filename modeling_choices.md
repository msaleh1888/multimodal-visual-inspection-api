# Modeling Choices

## 1. Purpose

This document explains the modeling strategy for the project, with a **VLM-first design**.

**Primary goal:** demonstrate how modern systems use **Vision–Language Models (VLMs)** to perform multimodal reasoning directly over images and text.

Vision-only models are supported **only as optional baselines** for debugging, evaluation, and comparison.

---

## 2. Core Design Principles

1. **VLM-first for image understanding**
   - Image reasoning is performed by a multimodal model that conditions language generation on visual input.
   - The LLM must "see" the image, not a summary of labels.

2. **Adapters over tight coupling**
   - All models (VLMs, vision backbones, document engines) are accessed via adapters.
   - This allows safe swapping of models without changing pipelines or APIs.

3. **Grounded language output**
   - Language models must produce outputs grounded in visual or extracted evidence.
   - Uncertainty must be surfaced explicitly.

4. **Production realism**
   - Pre-trained models are used.
   - No training of foundation models from scratch.

---

## 3. Image Analysis — Primary (VLM)

### What is used

A **Vision–Language Model** capable of accepting:
- image input
- optional text prompt or task instruction

and producing:
- natural-language explanation
- recommendation or next steps
- confidence / uncertainty signal

Examples of suitable model families:
- CLIP-based multimodal LLMs
- Vision-capable LLM APIs
- Open-source VLMs with image-token support

The exact model choice is abstracted behind a `VLMImageAnalyzer` adapter.

---

### Why this is the default

- True multimodal reasoning
- No lossy intermediate representation (e.g. labels)
- Matches how VLM-powered products are actually built

---

## 4. Image Analysis — Secondary (Vision-Only Baseline)

### What it is

A pre-trained vision model (e.g. ResNet / ViT) used to:
- produce labels or embeddings
- inspect raw perception quality
- compare against VLM behavior

### Why it exists

- Debugging and evaluation
- Performance benchmarking
- Failure analysis

### Important constraint

This path is:
- **never the default**
- **never presented as the main solution**

---

## 5. Document Analysis Modeling

Document analysis follows a different but complementary pattern:

1. **Document understanding** (OCR, layout, key-value extraction)
2. **Language interpretation** over extracted structured data

This separation is intentional:
- extraction must be deterministic
- interpretation must be grounded

VLM-based document Q&A may be explored as a future extension.

---

## 6. Language Model Role

Language models are used in two roles:

1. **Multimodal reasoning** (image + text → output) via VLMs
2. **Interpretation and explanation** for document extraction results

In both cases:
- hallucinations must be avoided
- outputs must reference provided evidence

---

## 7. Recommended Baseline Configuration

**Primary (default):**
- VLM image analyzer (image + prompt)

**Secondary (optional):**
- Vision-only classifier or embedding model

**Document path:**
- Document analyzer + grounded language interpretation

This configuration best demonstrates applied multimodal system design.

---

## 8. Optional Extensions

- Fine-tuning vision encoders for domain adaptation
- Multimodal question-answering endpoint
- Visual grounding / citation extraction

These extensions are intentionally out of scope for the core project.

---

## 9. Why This Choice Matters

This modeling strategy demonstrates:
- correct understanding of what a VLM actually is
- separation of perception, reasoning, and interpretation
- production-aware tradeoffs around cost, latency, and control

It avoids the common mistake of presenting a vision classifier + LLM as a VLM.

---

**End of Modeling Choices**

