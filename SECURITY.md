# Security Plan

## Current Security Findings

- `.env` files exist inside the workspace.
- `4_document_classification/Unified_extractor/my-gcp-key.json` exists inside the workspace.
- Default API keys are hardcoded as `secret123`.
- Uploaded documents, generated user profiles, sample KYC/property PDFs, logs, and model artifacts live inside source folders.
- Current services lack JWT auth, RBAC, rate limiting, strong CORS policy, upload limits, content validation, malware scanning, and centralized audit logging.

## Immediate Actions

1. Rotate any credentials that were present in `.env` or JSON key files.
2. Remove secrets from the repository.
3. Add `.env.example` files with placeholder values only.
4. Add secret scanning in CI.
5. Add a workspace `.gitignore` covering:
   - `.env`
   - `*.key`
   - `*gcp*key*.json`
   - virtualenvs
   - logs
   - uploads
   - generated OCR/results JSON
   - local databases
   - model artifacts unless explicitly tracked through LFS or an artifact registry

## Authentication

- Use JWT access tokens issued by the API Gateway.
- Store password hashes with Argon2id or bcrypt.
- Short-lived access tokens, refresh tokens stored server-side or rotated.
- Require auth for all upload, job, result, audit, and settings endpoints.
- Keep service-to-service credentials separate from user JWTs.

## Authorization

Roles:

- `admin`: manage users, settings, audit, all jobs.
- `analyst`: upload documents, view assigned jobs/results.
- `auditor`: read-only audit and reports.
- `service`: internal workers only.

Every endpoint must check tenant and role scope.

## Rate Limiting

Gateway limits:

- Login attempts per IP and account.
- Upload requests per user/tenant.
- Job creation per tenant.
- SSE/WebSocket connections per user.

Use Redis-backed rate limiting locally and Upstash/managed Redis in production.

## Upload Security

Required controls:

- Max file size per file and per job.
- Allowlist MIME types: PDF, PNG, JPEG.
- Verify MIME type by content sniffing, not only file extension.
- Reject encrypted PDFs unless explicitly supported.
- Reject corrupt files.
- Store original filename as metadata only; never trust it as a path.
- Generate storage keys server-side.
- Compute and persist SHA-256.
- Scan uploads with ClamAV or provider-integrated malware scanning before OCR in production.

## Data Protection

- Store document bytes in MinIO/R2, not PostgreSQL.
- Encrypt object storage at rest.
- Use presigned URLs with short expiration for downloads.
- Avoid logging raw OCR text, ID numbers, addresses, or face metadata.
- Mask identifiers in UI and logs.
- Add retention policies by tenant and document type.
- Soft delete metadata; separately schedule object deletion when legal retention allows.

## Secrets Management

Local:

- `.env` files only outside source control.
- `docker compose --env-file .env`.

Production:

- Railway/Render service variables for backend secrets.
- Neon connection strings stored as service variables.
- Cloudflare R2 keys stored as service variables.
- Upstash Redis tokens stored as service variables.
- Never expose standard Redis/R2 tokens to frontend.

## CORS

- Allow only configured frontend origins.
- Disable wildcard origins with credentials.
- Set allowed methods and headers explicitly.

## Audit Logging

Audit events:

- Login success/failure.
- Job creation.
- Document upload/delete.
- OCR/face/verification lifecycle events.
- Report download.
- Settings changes.
- User and role changes.

Audit logs must be append-only and must include actor, tenant, action, resource, IP address, user agent, timestamp, and trace id where available.

## OWASP Controls

- Validate every request with Pydantic/Zod schemas.
- Use parameterized SQL through ORM/core APIs.
- Add security headers at gateway.
- Use HTTPS in production.
- Use least-privilege database and object storage credentials.
- Add dependency vulnerability scanning.
- Add container scanning.
- Add structured error responses that do not leak stack traces.

## Security Acceptance Criteria

- No known secrets in repository.
- Auth and RBAC enforced on protected endpoints.
- Upload validation rejects unsafe files.
- Audit logs are persisted for sensitive actions.
- CI runs secret, dependency, and container scans.
- Production deployment uses managed secrets and HTTPS.
