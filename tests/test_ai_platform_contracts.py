from ai_platform.contracts.queues import AgentQueue, CELERY_TASK_ROUTES
from ai_platform.contracts.schemas import PlatformJob, UploadedDocument, WorkflowState
from ai_platform.evaluation.metrics import binary_classification_metrics, extraction_field_metrics


def test_workflow_state_defaults():
    job = PlatformJob(documents=[UploadedDocument(filename="pan.jpg", file_path="/tmp/pan.jpg")])
    state = WorkflowState(job=job)

    assert state.job.job_id
    assert state.job.trace_id
    assert state.job.documents[0].document_type == "UNKNOWN"
    assert state.errors == []


def test_queue_routes_include_face_tasks():
    assert CELERY_TASK_ROUTES["app.tasks.extract_faces_task"]["queue"] == AgentQueue.FACE_VERIFICATION
    assert CELERY_TASK_ROUTES["app.tasks.verify_faces_task"]["queue"] == AgentQueue.FACE_VERIFICATION


def test_evaluation_metrics():
    extraction = extraction_field_metrics({"pan": "ABCDE1234F", "name": "A"}, {"pan": "ABCDE1234F"})
    face = binary_classification_metrics([True, False, True], [True, False, False])

    assert extraction["field_accuracy"] == 0.5
    assert extraction["coverage"] == 0.5
    assert face["accuracy"] == 2 / 3
    assert face["false_reject_rate"] == 0.5
