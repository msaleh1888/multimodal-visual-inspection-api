from __future__ import annotations

from dataclasses import asdict
from typing import List, Optional, Tuple

import torch
import torch.nn.functional as F
from torchvision import models
from torchvision.models import ResNet18_Weights

from app.analyzers.vision_base import (
    EmbeddingInfo,
    TopKPrediction,
    VisionImageAnalyzer,
    VisionInput,
    VisionResult,
)


class ResNet18VisionAnalyzer(VisionImageAnalyzer):
    """
    Vision-only baseline using torchvision ResNet-18 pretrained on ImageNet.

    Outputs:
    - top-k class predictions
    - optional embedding (512-d) from the penultimate layer
    """

    def __init__(self, device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # Pretrained weights include proper preprocessing transforms + categories
        self.weights = ResNet18_Weights.DEFAULT
        self.categories = list(self.weights.meta.get("categories", []))

        model = models.resnet18(weights=self.weights)
        model.eval()
        model.to(self.device)
        self.model = model

        self.model_name = "resnet18"
        self.model_version = "torchvision-imagenet"

    @torch.no_grad()
    def analyze(self, image_pil, inputs: VisionInput) -> VisionResult:
        # 1) Preprocess image to tensor using weights' recommended transforms
        preprocess = self.weights.transforms()
        x = preprocess(image_pil).unsqueeze(0).to(self.device)  # [1,3,H,W]

        # 2) Forward pass that also captures embedding
        logits, embedding = self._forward_with_embedding(x)

        # 3) Convert logits -> probabilities -> top-k predictions
        probs = F.softmax(logits, dim=1)[0]  # [1000]
        top_k = max(1, int(inputs.top_k))

        values, indices = torch.topk(probs, k=min(top_k, probs.shape[0]))
        preds: List[TopKPrediction] = []
        for p, idx in zip(values.tolist(), indices.tolist()):
            label = self.categories[idx] if idx < len(self.categories) else f"class_{idx}"
            preds.append(TopKPrediction(label=label, prob=float(p)))

        # 4) Build embedding preview (don’t return the full vector by default)
        emb_info: Optional[EmbeddingInfo] = None
        if inputs.return_embedding:
            emb = embedding[0].detach().cpu().float().tolist()  # 512 floats
            n = max(0, int(inputs.embedding_preview_len))
            emb_info = EmbeddingInfo(dim=len(emb), preview=emb[:n])

        return VisionResult(
            top_k=preds,
            embedding=emb_info,
            model_name=self.model_name,
            model_version=self.model_version,
            raw_debug={
                "top1": asdict(preds[0]) if preds else None,
                "device": self.device,
            },
        )

    def _forward_with_embedding(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Runs a ResNet forward pass manually so we can capture the embedding.

        ResNet structure (high-level):
        conv1 -> bn1 -> relu -> maxpool
        -> layer1..4 -> avgpool -> flatten -> fc (logits)

        The embedding we want is right after avgpool+flatten (before fc).
        """
        m = self.model

        x = m.conv1(x)
        x = m.bn1(x)
        x = m.relu(x)
        x = m.maxpool(x)

        x = m.layer1(x)
        x = m.layer2(x)
        x = m.layer3(x)
        x = m.layer4(x)

        x = m.avgpool(x)               # [1, 512, 1, 1]
        emb = torch.flatten(x, 1)      # [1, 512]
        logits = m.fc(emb)             # [1, 1000]

        return logits, emb