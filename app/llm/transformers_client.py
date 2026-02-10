from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.llm.llm_client import LLMClient, LLMError, LLMDownstreamError, LLMRequest, LLMResult, LLMTimeoutError



@dataclass
class TransformersLLMConfig:
    """
    Configuration for a local Hugging Face Transformers *text* model.

    model_id:
      Example: "microsoft/phi-2", "TinyLlama/TinyLlama-1.1B-Chat-v1.0", etc.

    device:
      - "cpu" always works
      - "cuda" requires a CUDA-enabled PyTorch install + GPU
      - "auto" picks cuda if available else cpu

    timeout_s:
      Best-effort timeout for generation. Implemented using a thread wait.
      (Python can't safely kill a running generation thread.)
    """
    model_id: str
    device: str = "auto"
    timeout_s: float = 30.0
    max_new_tokens_default: int = 256


class TransformersLLMClient(LLMClient):
    """
    Local text-only LLM client using Hugging Face Transformers.

    Why this class exists:
    - It hides all Transformers details behind our LLMClient interface.
    - Other code only depends on LLMRequest/LLMResult.

    Design choices:
    - Lazy loads model/tokenizer on first use.
    - Deterministic defaults: temperature=0 (good for grounded JSON outputs).
    - Best-effort timeout via thread + future timeout.
    """

    def __init__(self, cfg: TransformersLLMConfig):
        self._cfg = cfg
        self._tokenizer = None
        self._model = None
        self._executor = ThreadPoolExecutor(max_workers=1)

    @property
    def model_id(self) -> str:
        return self._cfg.model_id

    # -----------------------------
    # Internal: lazy load
    # -----------------------------

    def _ensure_loaded(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return

        try:
            # Local imports: avoid heavy dependencies at module import time
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except Exception as e:
            raise LLMDownstreamError(f"Failed to import Transformers/PyTorch: {type(e).__name__}: {e}")

        # Choose device
        device = self._cfg.device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"

        try:
            tokenizer = AutoTokenizer.from_pretrained(self._cfg.model_id, use_fast=True)

            # For many decoder-only LLMs
            model = AutoModelForCausalLM.from_pretrained(self._cfg.model_id)

            if device == "cuda":
                model = model.to("cuda")

            model.eval()

            self._tokenizer = tokenizer
            self._model = model
            self._device = device

        except Exception as e:
            raise LLMDownstreamError(f"Failed to load model '{self._cfg.model_id}': {type(e).__name__}: {e}")

    # -----------------------------
    # Public API
    # -----------------------------

    def generate(self, req: LLMRequest) -> LLMResult:
        """
        Generate text from a single prompt.

        Notes on parameters:
        - temperature:
            * 0.0 => greedy decode (deterministic, best for JSON)
            * >0 => sampling (less deterministic)
        - max_tokens:
            Mapped to Transformers' max_new_tokens.
        """
        self._ensure_loaded()
        assert self._model is not None
        assert self._tokenizer is not None

        start = time.perf_counter()

        # Submit generation to background thread to support a best-effort timeout.
        future = self._executor.submit(self._generate_blocking, req)

        try:
            raw_text, meta = future.result(timeout=self._cfg.timeout_s)
        except FuturesTimeoutError:
            # Can't safely cancel a running HF generate in a thread,
            # but we can report a timeout to the caller.
            raise LLMTimeoutError(
                f"Transformers generation exceeded timeout ({self._cfg.timeout_s}s) for model '{self._cfg.model_id}'."
            )
        except LLMError:
            raise
        except Exception as e:
            raise LLMDownstreamError(f"{type(e).__name__}: {e}")

        latency_ms = int((time.perf_counter() - start) * 1000)

        return LLMResult(
            raw_text=raw_text,
            model_id=self._cfg.model_id,
            latency_ms=latency_ms,
            attempts=1,  # retries are handled by RetryingLLMClient wrapper
            meta=meta,
        )

    # -----------------------------
    # Blocking generation logic
    # -----------------------------

    def _generate_blocking(self, req: LLMRequest) -> tuple[str, Dict[str, Any]]:
        """
        The actual Transformers call. Runs inside a thread.

        We implement:
        - greedy decode when temperature==0
        - sampling when temperature>0
        """
        import torch

        tokenizer = self._tokenizer
        model = self._model
        assert tokenizer is not None and model is not None

        # Tokenize
        inputs = tokenizer(req.prompt, return_tensors="pt")

        # Move tensors to GPU if needed
        if getattr(self, "_device", "cpu") == "cuda":
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        max_new = req.max_tokens if req.max_tokens is not None else self._cfg.max_new_tokens_default

        # Decode settings
        do_sample = req.temperature > 0.0
        gen_kwargs: Dict[str, Any] = {
            "max_new_tokens": int(max_new),
            "do_sample": bool(do_sample),
        }

        # If sampling, use temperature; otherwise greedy
        if do_sample:
            gen_kwargs["temperature"] = float(req.temperature)

        # Generate
        with torch.no_grad():
            out = model.generate(**inputs, **gen_kwargs)

        # Decode full sequence and then strip the prompt prefix (best-effort)
        decoded = tokenizer.decode(out[0], skip_special_tokens=True)

        # Common behavior: decoded contains the prompt + completion
        # Remove prompt prefix if present to return only generated part.
        completion = decoded
        if decoded.startswith(req.prompt):
            completion = decoded[len(req.prompt):].lstrip()

        meta = {
            "device": getattr(self, "_device", "cpu"),
            "do_sample": do_sample,
            "max_new_tokens": int(max_new),
            "request_id": req.request_id,
        }

        return completion, meta
