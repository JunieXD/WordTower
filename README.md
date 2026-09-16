# WordTower

WordTower is a monorepo containing a Vue frontend and a FastAPI backend. Production runs as a Docker Compose application behind the host OpenResty instance.

## Repository layout

```text
frontend/               Vue, Vite and the frontend OpenResty image
backend/                FastAPI, Alembic and the backend image
deploy/openresty/       Host OpenResty reverse-proxy example
deploy/server/          Release and database backup scripts
.github/workflows/      Tests, GHCR image builds and production deployment
compose.yaml            Local and production service topology
```

## Local development

Run PostgreSQL and Redis locally, then start each application with its native toolchain:

```bash
cd backend
cp .env.example .env
uv sync --frozen
uv run alembic -c app/alembic.ini upgrade head
uv run uvicorn app.main:app --reload
```

```bash
cd frontend
npm ci
npm run dev
```

The production Compose file expects externally managed PostgreSQL and Redis services. To run it outside 1Panel, provide an external Docker network and reachable `postgresql` and `redis` hosts in `.env`. The application is then available at `http://127.0.0.1:8080`. SRS is disabled by default and the backend has no PyTorch dependency.

## Production topology

The host OpenResty instance terminates HTTPS and proxies the site to `127.0.0.1:8080`. The Compose frontend is also based on OpenResty; it serves the Vue assets and sends `/api/*` to FastAPI. The backend and one-shot migration container join both the private application network and 1Panel's external `1panel-network`. They reach the 1Panel-managed services through the stable Docker aliases `postgresql` and `redis`; WordTower does not run its own database or Redis containers.

Copy the location block from `deploy/openresty/wordtower.location.conf.example` into the HTTPS site managed by OpenResty or 1Panel.

## First server setup

The deployment user must have Docker Compose v2 access and write permission to `/opt/1panel/www/sites/WordTower` (or the path configured in the GitHub `DEPLOY_PATH` variable). PostgreSQL and Redis must already be managed by 1Panel and attached to `1panel-network` with the aliases `postgresql` and `redis`. Manual SQL backups are stored below the WordTower directory so they can be included in a site snapshot; the live database files remain under the 1Panel PostgreSQL application directory.

1. Install PostgreSQL and Redis through 1Panel and confirm both services are on `1panel-network`.
2. Create the deployment directory and place `.env.example` there as `.env`.
3. Set the PostgreSQL host, port, database, user and URL-safe password. Set `REDIS_URL` to the 1Panel Redis alias and include its URL-encoded password when Redis authentication is enabled.
4. Replace the remaining placeholders, especially `SECRET_KEY` and `ECNU_API_KEY`, and set `COOKIE_SECURE=true` for HTTPS.
5. Configure the OpenResty location block and point DNS to the server.
6. Configure the GitHub production environment described below, then push `main`. The workflow logs the server into GHCR with its temporary GitHub token during each deployment.

Do not commit the production `.env` file.

## ECNU LLM configuration and migration

WordTower uses `ecnu-plus` through the university's OpenAI-compatible API.
Set these values in `backend/.env` for local development, or the deployment
directory's `.env` for Docker:

```dotenv
ECNU_API_KEY=<your-school-api-key>
ECNU_API_BASE_URL=https://chat.ecnu.edu.cn/open/api/v1
ECNU_API_MODEL_ID=ecnu-plus
ECNU_MAX_CONCURRENCY=3
```

Only the key is required; the remaining values above are the defaults. Remove
the old `ARK_API_KEY`, `ARK_API_BASE_URL` and `ARK_API_MODEL_ID` entries after
migration. They are no longer read and there is no fallback to Volcengine.

Update the server `.env` **before** deploying this release. CI/CD uploads
`.env.example`, preserves `.env`, and checks required configuration before
changing image tags or running migrations. If the key is missing, the release
stops and the running application stays on its previous version. After fixing
`.env`, rerun the failed GitHub Actions deployment. For an already deployed
version, apply environment changes with `docker compose up -d --force-recreate backend`
from the deployment directory; `docker compose restart` does not reload
environment variables.

The [model documentation](https://developer.ecnu.edu.cn/vitepress/llm/model.html)
and [quota documentation](https://developer.ecnu.edu.cn/vitepress/llm/limit.html)
currently specify at most three simultaneous requests per user and model.
Generation, review, prewarming and grading share a process-wide queue, with a
20-second queue wait limit and one SDK retry for transient failures (including
429). Production explicitly runs one Uvicorn worker. Keep one backend replica;
multiple replicas or workers require a shared distributed limiter. If the same
school account is used by other applications, reduce `ECNU_MAX_CONCURRENCY`
(allowed range: 1–3) to leave capacity for them. The quota is shared across that
account, so this application cannot reserve capacity against external callers.

All calls disable thinking, cap output at 2048 tokens, and request
`response_format={"type":"json_object"}` using ECNU's
[structured output API](https://developer.ecnu.edu.cn/vitepress/llm/api/structuredoutput.html).
This enforces JSON syntax for the different generation stages; field and
semantic checks remain in the existing question workflows. Empty, truncated
or otherwise incomplete replies are rejected and retried once.

Run a real API smoke test (consumes a small amount of the account's quota):

```bash
cd backend
uv run python -m app.test.test_LLM
```

## GitHub deployment settings

Create a GitHub environment named `production` and configure:

| Kind | Name | Value |
| --- | --- | --- |
| Secret | `DEPLOY_HOST` | Server IP or hostname |
| Secret | `DEPLOY_PORT` | SSH port, normally `22` |
| Secret | `DEPLOY_USER` | SSH deployment user |
| Secret | `DEPLOY_SSH_KEY` | Private Ed25519 SSH key |
| Secret | `DEPLOY_KNOWN_HOSTS` | Output of `ssh-keyscan -p <port> -H <host>` |
| Variable | `DEPLOY_PATH` | Optional; defaults to `/opt/1panel/www/sites/WordTower` |

Every push to `main` runs frontend and backend tests and pushes both commit-SHA images to GHCR. It then uploads the deployment files and executes `deploy/server/deploy.sh`. The same release can be started manually with `workflow_dispatch`. A failed health check restores the previous application image tag.

## Backups and moving servers

Run database backups from the deployment directory:

```bash
./deploy/server/backup.sh
```

Copy the resulting `backups/*.sql.gz` file and the production `.env` to storage outside the server. A WordTower site snapshot does not contain the live 1Panel PostgreSQL data directory, so create a manual SQL backup before a snapshot that must be independently restorable.

Restore a dump on the destination server before switching traffic:

```bash
./deploy/server/restore.sh /absolute/path/to/wordtower.sql.gz
```

To move to a new server:

1. Install Docker Compose v2 and OpenResty/1Panel.
2. Install PostgreSQL and Redis in 1Panel and recreate the database user recorded in `.env`.
3. Recreate the deployment directory and `.env`, then restore the latest SQL dump before opening traffic.
4. Copy the OpenResty location configuration and update DNS.
5. Update `DEPLOY_HOST` and `DEPLOY_KNOWN_HOSTS` in GitHub, then rerun the latest workflow or push `main`.

Database restoration is intentionally a manual operation because it replaces persistent data. For a new empty database, the deployment workflow applies all Alembic migrations automatically.
