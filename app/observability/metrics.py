from prometheus_client import Counter, Histogram

# -------------------------
# VLM metrics
# -------------------------

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["path", "method", "status"],
)

VLM_REQUESTS_TOTAL = Counter(
    "vlm_requests_total",
    "Total VLM requests",
    ["mode", "result", "model"],
)

VLM_INFERENCE_SECONDS = Histogram(
    "vlm_inference_seconds",
    "VLM inference latency in seconds",
    ["model"],
)

# -------------------------
# Baseline (vision-only) metrics
# -------------------------

VISION_REQUESTS_TOTAL = Counter(
    "vision_requests_total",
    "Total number of vision-only baseline image analysis requests",
    ["result", "model"],
)

VISION_INFERENCE_SECONDS = Histogram(
    "vision_inference_seconds",
    "Time spent running vision-only baseline inference",
    ["model"],
)