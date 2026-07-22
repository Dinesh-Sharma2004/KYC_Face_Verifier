"""Queue names and task routing shared by orchestration and workers.

Celery is execution infrastructure. LangGraph remains responsible for workflow
decisions and should dispatch long-running work to these queues.
"""

from enum import StrEnum


class AgentQueue(StrEnum):
    INTAKE = "intake_queue"
    CLASSIFICATION = "classification_queue"
    EXTRACTION = "extraction_queue"
    FACE_VERIFICATION = "face_verification_queue"
    VALIDATION = "validation_queue"
    FEATURE_ENGINEERING = "feature_engineering_queue"
    FEATURE_STORE = "feature_store_queue"
    INFERENCE = "inference_queue"
    MONITORING = "monitoring_queue"
    PERFORMANCE = "performance_queue"


CELERY_TASK_ROUTES = {
    "app.tasks.extract_faces_task": {"queue": AgentQueue.FACE_VERIFICATION.value},
    "app.tasks.verify_faces_task": {"queue": AgentQueue.FACE_VERIFICATION.value},
    "ai_platform.tasks.classify_document": {"queue": AgentQueue.CLASSIFICATION.value},
    "ai_platform.tasks.extract_document": {"queue": AgentQueue.EXTRACTION.value},
    "ai_platform.tasks.validate_documents": {"queue": AgentQueue.VALIDATION.value},
    "ai_platform.tasks.engineer_features": {"queue": AgentQueue.FEATURE_ENGINEERING.value},
    "ai_platform.tasks.sync_feature_store": {"queue": AgentQueue.FEATURE_STORE.value},
    "ai_platform.tasks.run_model_inference": {"queue": AgentQueue.INFERENCE.value},
    "ai_platform.tasks.collect_monitoring": {"queue": AgentQueue.MONITORING.value},
    "ai_platform.tasks.run_benchmark": {"queue": AgentQueue.PERFORMANCE.value},
}
