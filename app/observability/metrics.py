from prometheus_client import Counter, Histogram

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