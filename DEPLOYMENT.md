# Deployment Guide

This deployment plan is designed for free-tier or low-cost infrastructure, but quotas and product limits can change. Verify provider limits before production launch.

Official references checked during audit:

- GitHub Pages custom workflows: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- Vite static deployment guide: https://github.com/vitejs/vite/blob/main/docs/guide/static-deploy.md
- Railway FastAPI guide: https://docs.railway.com/guides/fastapi
- Railway variables: https://docs.railway.com/variables
- Render FastAPI guide: https://render.com/docs/deploy-fastapi
- Render Docker guide: https://render.com/docs/docker
- Neon connection pooling: https://neon.com/docs/connect/connection-pooling
- Cloudflare R2 S3 compatibility: https://developers.cloudflare.com/r2/api/s3/api/
- Upstash Redis REST/API docs: https://upstash.com/docs/redis/features/restapi

## Local Development

Target command:

```bash
docker compose up
```

Target services:

- `frontend`
- `gateway`
- `document-service`
- `ocr-service`
- `face-service`
- `verification-service`
- `notification-service`
- `audit-service`
- `postgres`
- `redis`
- `rabbitmq`
- `minio`
- `prefect`
- `prometheus`
- `grafana`

Local storage:

- MinIO bucket `kyc-documents`.
- MinIO bucket `kyc-reports`.

Local database:

- PostgreSQL initialized with `schema.sql`.

Local queues:

- Redis for simple status/rate-limit/cache.
- RabbitMQ for local event bus if Redis Streams is not selected.

## Environment Variables

Required backend variables:

```env
ENVIRONMENT=production
DATABASE_URL=
JWT_SECRET=
JWT_ISSUER=kyc-platform
ALLOWED_ORIGINS=
REDIS_URL=
EVENT_BUS_URL=
OBJECT_STORAGE_PROVIDER=r2
S3_ENDPOINT_URL=
S3_REGION=auto
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
DOCUMENT_BUCKET=kyc-documents
REPORT_BUCKET=kyc-reports
MAX_UPLOAD_BYTES=10485760
UNIFIED_EXTRACTOR_API_KEY=
GCP_PROJECT_ID=
GCP_LOCATION=
MODEL_NAME=
```

Do not deploy with `secret123`, default database passwords, or checked-in key files.

## Frontend: GitHub Pages

Use GitHub Pages for the React/Vite static frontend.

Steps:

1. Add `frontend/package.json` with `build` script using Vite.
2. Set Vite `base` to `/REPO_NAME/` for project pages or `/` for user/org pages.
3. Store the backend URL as a build-time variable such as `VITE_API_BASE_URL`.
4. Add a GitHub Actions workflow that builds `frontend/dist` and deploys Pages.
5. In repository Settings -> Pages, select GitHub Actions as the source.

Notes:

- Vite `preview` is not a production server.
- Do not store JWT secrets or backend service tokens in frontend variables.

## Backend Option A: Railway

Railway can deploy FastAPI from GitHub or Dockerfile and supports service variables.

Recommended service split:

- `gateway`
- `document-service`
- `ocr-service`
- `face-service`
- `verification-service`
- `notification-service`
- `audit-service`

Steps:

1. Create Railway project.
2. Add each backend service from GitHub repo or Dockerfile.
3. Configure service variables in Railway Variables.
4. Set `DATABASE_URL` from Neon pooled connection string.
5. Set Redis/event variables from Upstash or Railway Redis if used.
6. Generate a public domain only for the gateway.
7. Keep worker services private/background where possible.
8. Configure health checks for `/health`.

## Backend Option B: Render

Render can deploy Python FastAPI services using native Python settings or Docker.

Native FastAPI defaults:

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

Use Docker for ML-heavy OCR/face workers where system dependencies are required.

## Database: Neon PostgreSQL

Steps:

1. Create Neon project and database.
2. Enable or copy pooled connection string for web services.
3. Set `DATABASE_URL` in backend variables.
4. Run migrations against Neon before deploying app traffic.
5. Use SSL-required connection strings in production.

Migration command target:

```bash
alembic upgrade head
```

Until Alembic is added, apply `schema.sql` manually in a controlled setup step.

## Object Storage: Cloudflare R2

Cloudflare R2 exposes an S3-compatible API endpoint:

```text
https://<ACCOUNT_ID>.r2.cloudflarestorage.com
```

Steps:

1. Create R2 buckets for documents and reports.
2. Create least-privilege API tokens for object read/write.
3. Set S3-compatible variables in backend services.
4. Use region `auto` for R2 compatibility.
5. Generate presigned URLs only through backend APIs.

## Redis: Upstash

Use Upstash for Redis-compatible status/rate-limit/cache needs. Upstash also provides an HTTP REST API, which is useful for serverless environments. For Celery-style TCP Redis usage, confirm the selected Upstash plan and client compatibility before relying on it for workers.

Required variables depend on client:

- TCP Redis clients: `REDIS_URL`
- REST clients: `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`

Do not expose standard tokens to frontend code.

## CI/CD

Required GitHub Actions workflows:

- `lint.yml`: Python and frontend lint.
- `test.yml`: unit/integration tests with coverage.
- `docker.yml`: build service images.
- `security.yml`: secret scan, dependency scan, container scan.
- `deploy-frontend.yml`: build and deploy GitHub Pages.
- `deploy-backend.yml`: deploy to Railway or Render after tests pass.

## Production Health Checks

Every service must expose:

- `GET /health`: liveness.
- `GET /ready`: readiness with DB/queue/storage checks.
- `GET /metrics`: Prometheus metrics where supported.

## Rollback Plan

Frontend:

- Revert GitHub Pages deployment to previous workflow artifact.

Backend:

- Keep previous image/release available.
- Deploy one service at a time.
- Use database migrations with downgrade scripts.
- Keep event consumers idempotent so replay is safe.

Database:

- Back up before migration.
- Run migrations in a maintenance window until schema is stable.
- Prefer additive migrations for the first production releases.

Storage:

- Object writes are immutable by key/version.
- Keep old report/document versions until cleanup jobs are validated.
