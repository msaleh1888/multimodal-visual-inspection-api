from __future__ import annotations

from app.analyzers.vision_resnet import ResNet18VisionAnalyzer


# Instantiate once (similar to VLM analyzer usage).
# This keeps model loading cost out of the request path.
_vision = None


def create_vision_analyzer():
    global _vision
    if _vision is None:
        _vision = ResNet18VisionAnalyzer()
    return _vision