# Event Contracts

## Event Envelope

All async messages use a common envelope. Services may add event-specific fields in `data`, but envelope fields are required.

```json
{
  "event_id": "uuid",
  "event_type": "document.uploaded",
  "event_version": 1,
  "occurred_at": "2026-07-21T00:00:00Z",
  "trace_id": "uuid",
  "job_id": "uuid",
  "document_id": "uuid",
  "producer": "document-service",
  "idempotency_key": "document.uploaded:job:document:version",
  "data": {},
  "metadata": {
    "tenant_id": "uuid",
    "user_id": "uuid"
  }
}
```

## Event List

| Event | Producer | Consumers | Purpose |
| --- | --- | --- | --- |
| `document.uploaded` | Document Service | OCR Service, Face Service, Verification Service, Audit Service | A document version is stored and ready for processing |
| `ocr.started` | OCR Service | Notification Service, Audit Service | OCR began for a document |
| `ocr.completed` | OCR Service | Verification Service, Notification Service, Audit Service | OCR and entity extraction completed |
| `ocr.failed` | OCR Service | Verification Service, Notification Service, Audit Service | OCR failed after allowed attempts |
| `face.started` | Face Verification Service | Notification Service, Audit Service | Face extraction/comparison began |
| `face.completed` | Face Verification Service | Verification Service, Notification Service, Audit Service | Face verification completed |
| `face.failed` | Face Verification Service | Verification Service, Notification Service, Audit Service | Face processing failed or was not possible |
| `verification.started` | Verification Service | Notification Service, Audit Service | Matching/scoring started |
| `verification.completed` | Verification Service | Notification Service, Audit Service | Final score and decision stored |
| `verification.failed` | Verification Service | Notification Service, Audit Service | Matching/scoring failed |
| `report.generated` | Verification Service | Notification Service, Audit Service | Verification report artifact stored |

## Event Data Schemas

### `document.uploaded`

```json
{
  "document_role": "primary",
  "document_type_hint": "PAN_CARD",
  "version": 1,
  "filename": "pan.pdf",
  "content_type": "application/pdf",
  "size_bytes": 123456,
  "sha256": "hex",
  "storage_bucket": "kyc-documents",
  "storage_key": "tenant/job/document/v1/original.pdf"
}
```

### `ocr.started`

```json
{
  "attempt": 1,
  "engine": "tesseract+gemini",
  "input_storage_key": "tenant/job/document/v1/original.pdf"
}
```

### `ocr.completed`

```json
{
  "attempt": 1,
  "engine": "tesseract+gemini",
  "document_type": "PAN_CARD",
  "classification_confidence": 0.93,
  "raw_text_storage_key": "tenant/job/document/v1/ocr.txt",
  "extracted_entities": {
    "full_name": "Example User",
    "date_of_birth": "1990-01-01",
    "pan_number": "ABCDE1234F"
  },
  "quality": {
    "text_length": 1200,
    "pages_processed": 1
  }
}
```

### `ocr.failed`

```json
{
  "attempt": 3,
  "engine": "tesseract+gemini",
  "error_code": "OCR_TIMEOUT",
  "error_message": "OCR worker exceeded timeout",
  "retryable": false
}
```

### `face.started`

```json
{
  "attempt": 1,
  "mode": "extract_and_compare",
  "reference_document_id": "uuid",
  "probe_document_id": "uuid"
}
```

### `face.completed`

```json
{
  "attempt": 1,
  "faces_detected": 1,
  "reference_face_id": "uuid",
  "probe_face_id": "uuid",
  "match": true,
  "confidence": 0.87,
  "model_version": "face-verifier-v1"
}
```

### `face.failed`

```json
{
  "attempt": 2,
  "error_code": "NO_FACE_DETECTED",
  "error_message": "No usable face detected in primary document",
  "retryable": false
}
```

### `verification.started`

```json
{
  "scoring_version": "kyc-score-v1",
  "documents_considered": ["uuid", "uuid"]
}
```

### `verification.completed`

```json
{
  "decision": "verified",
  "score": 92,
  "threshold": 80,
  "checks": {
    "name": {"status": "match", "score": 0.96},
    "dob": {"status": "match", "score": 1.0},
    "address": {"status": "partial_match", "score": 0.72},
    "id": {"status": "match", "score": 1.0},
    "face": {"status": "match", "score": 0.87}
  }
}
```

### `verification.failed`

```json
{
  "error_code": "INSUFFICIENT_EVIDENCE",
  "error_message": "No OCR result available for required primary document",
  "retryable": false
}
```

### `report.generated`

```json
{
  "report_id": "uuid",
  "format": "json",
  "storage_bucket": "kyc-reports",
  "storage_key": "tenant/job/report.json",
  "sha256": "hex"
}
```

## Ordering and Idempotency

- Consumers must deduplicate by `event_id` and `idempotency_key`.
- `processing_events.sequence` stores per-job ordering.
- Event payloads are append-only. Use a new `event_version` for breaking changes.
- Failed events are valid terminal inputs to Verification Service; they should not disappear.

## Queue Mapping

| Event | Queue/stream |
| --- | --- |
| `document.uploaded` | `document.events` |
| OCR lifecycle | `ocr.events` |
| Face lifecycle | `face.events` |
| Verification lifecycle | `verification.events` |
| Report lifecycle | `report.events` |
| Audit copies | `audit.events` |
