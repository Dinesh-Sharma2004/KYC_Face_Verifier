"""Celery task names reserved for platform agents.

Existing services can bind these names to concrete implementations as they are
migrated into the shared architecture.
"""

TASK_NAMES = {
    "classify_document": "ai_platform.tasks.classify_document",
    "extract_document": "ai_platform.tasks.extract_document",
    "validate_documents": "ai_platform.tasks.validate_documents",
    "engineer_features": "ai_platform.tasks.engineer_features",
    "sync_feature_store": "ai_platform.tasks.sync_feature_store",
    "run_model_inference": "ai_platform.tasks.run_model_inference",
    "collect_monitoring": "ai_platform.tasks.collect_monitoring",
    "run_benchmark": "ai_platform.tasks.run_benchmark",
}
