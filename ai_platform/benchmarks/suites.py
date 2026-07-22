"""Reproducible benchmark suite metadata for the Performance Agent."""

BENCHMARK_SUITES = {
    "single_user_identity": {
        "users": 1,
        "documents": ["PAN_CARD", "AADHAAR_CARD", "SELFIE"],
        "metrics": ["end_to_end_latency_ms"],
    },
    "ten_concurrent_users": {
        "users": 10,
        "documents_per_user": 3,
        "metrics": ["throughput", "queue_wait_ms", "worker_utilization"],
    },
    "fifty_concurrent_users": {
        "users": 50,
        "documents_per_user": 3,
        "metrics": ["scaling_behavior", "bottlenecks", "failure_rate"],
    },
    "hundred_concurrent_users": {
        "users": 100,
        "documents_per_user": 3,
        "metrics": ["stability", "failure_rate", "recovery_rate"],
    },
    "thousand_documents": {
        "users": None,
        "documents": 1000,
        "metrics": ["documents_per_minute", "processing_time_ms", "queue_depth"],
    },
}
