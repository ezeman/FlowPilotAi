# ezeCraft AI

> **Craft is Easy.**

AI content operations platform for multi-brand teams. The system helps editorial and marketing teams generate, review, schedule, and publish trustworthy social content with account, page, user, and plan management built in.

## Stack

- FastAPI backend with JWT auth and role-based access
- PostgreSQL with SQLAlchemy and Alembic
- Redis + Celery worker and beat scheduler
- OpenAI content generation service with safe mocked fallback
- Facebook Graph API publisher service with approval guardrails
- React admin dashboard
- Nginx reverse proxy
- Docker Compose orchestration

## Services and host ports

The defaults intentionally avoid ports already in use on this machine.

- App gateway: `http://localhost:3090`
- PostgreSQL: `localhost:5434`
- Redis: `localhost:6381`

## Project structure

```text
clean-air-agent/
├── docker-compose.yml
├── .env.example
├── README.md
├── backend/
│   ├── app/
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
├── dashboard/
│   ├── src/
│   └── Dockerfile
└── nginx/
    └── default.conf
```

## Backend capabilities

- Authentication with bootstrap admin flow and JWT login
- Roles: `admin`, `editor`, `viewer`
- CRUD for content calendar, posts, pages, and settings
- AI content generation endpoint and queued generation job
- Review, approve, schedule, and manual publish flows
- Publish logs and dashboard summary endpoint
- Audit log entries for post and settings changes
- Encrypted storage support for sensitive settings and page tokens

## Post lifecycle

`idea -> generating -> draft -> ready_for_review -> approved -> scheduled -> publishing -> posted -> failed`

## Database tables

- `users`
- `pages`
- `content_calendar`
- `posts`
- `post_assets`
- `ai_runs`
- `publish_logs`
- `references`
- `settings`
- `audit_logs`

Default content pillars are seeded into `settings.content_pillars`, and the initial content calendar includes these topics:

- ทำไมห้องนอนถึงอากาศอับกว่าที่คิด
- CO2 สูงในห้องประชุมส่งผลต่อสมาธิอย่างไร
- VOC คืออะไร และพบได้จากของใช้ใกล้ตัวแบบไหน
- เชื้อราในบ้านเกี่ยวข้องกับความชื้นอย่างไร
- เปิดหน้าต่างช่วยให้อากาศดีขึ้นเสมอหรือไม่

## Quick start

1. Copy `.env.example` to `.env` and adjust secrets.
2. Keep `MOCK_EXTERNAL_SERVICES=true` for local development unless you have valid OpenAI and Facebook credentials.
3. Start the stack:

```bash
docker compose up --build
```

4. Bootstrap the first admin user:

```bash
curl -X POST http://localhost:3090/api/v1/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","full_name":"Admin User","password":"ChangeMe123!"}'
```

5. Log in from the dashboard or the API.

## Migrations

- Inside the API container: `alembic upgrade head`
- Create a new revision: `alembic revision -m "describe change"`

## Celery jobs

- `generate_content_job`
- `review_content_job`
- `generate_image_prompt_job`
- `publish_facebook_post_job`
- `retry_failed_publish_job`
- `sync_facebook_metrics_job`

## Facebook publishing rules

- Unapproved posts are never auto-published.
- Publish attempts create a log entry with request, response, and error fields.
- Failed publishes can be retried by the scheduled Celery beat job.
- Image publishing uses the first `post_assets` image URL when present.

## Security notes

- Store secrets only in `.env` or your deployment secret manager.
- `SECRET_KEY` and `ENCRYPTION_KEY` must be replaced in non-local environments.
- Page access tokens and sensitive text settings can be encrypted before persistence.
- CORS is enabled for the local dashboard by default and should be tightened for production.

## Production notes

- Run behind TLS termination and restrict direct DB/Redis exposure.
- Replace mock integrations with live credentials and rotate keys regularly.
- Add structured logging, observability, backups, and Facebook metrics sync extensions for production operations.
- Consider separate worker autoscaling and a managed PostgreSQL backup policy.
