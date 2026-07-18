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

For a production-like local stack:

```bash
cp .env.example .env
# Replace POSTGRES_PASSWORD and SECRET_KEY before starting.
docker compose up --build
```

The application is available at `http://127.0.0.1:8080`. SRS is disabled by default and the backend has no PyTorch dependency.

## Production topology

The host OpenResty instance terminates HTTPS and proxies the site to `127.0.0.1:8080`. The Compose frontend is also based on OpenResty; it serves the Vue assets and sends `/api/*` to FastAPI. Backend, PostgreSQL and Redis do not publish host ports.

Copy the location block from `deploy/openresty/wordtower.location.conf.example` into the HTTPS site managed by OpenResty or 1Panel.

## First server setup

The deployment user must have Docker Compose v2 access and write permission to `/opt/1panel/www/sites/WordTower` (or the path configured in the GitHub `DEPLOY_PATH` variable). PostgreSQL, Redis and SQL backups are stored below this directory so they can be included in a 1Panel site snapshot.

1. Create the deployment directory and place `.env.example` there as `.env`.
2. Replace every placeholder in `.env`, especially `POSTGRES_PASSWORD`, `SECRET_KEY` and `ARK_API_KEY`. Use a URL-safe PostgreSQL password and set `COOKIE_SECURE=true` for HTTPS.
3. If GHCR packages are private, log in once with a token that has `read:packages`:

   ```bash
   docker login ghcr.io
   ```

4. Configure the OpenResty location block and point DNS to the server.
5. Configure the GitHub production environment described below, then push `main`.

Do not commit the production `.env` file.

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
| Variable | `DEPLOY_ENABLED` | Set to `true` only after the server and secrets are ready |

Every push to `main` runs frontend and backend tests and pushes both commit-SHA images to GHCR. When `DEPLOY_ENABLED=true`, it also uploads the deployment files and executes `deploy/server/deploy.sh`. The same release can be started manually with `workflow_dispatch`. A failed health check restores the previous application image tag.

## Backups and moving servers

Run database backups from the deployment directory:

```bash
./deploy/server/backup.sh
```

Copy the resulting `backups/*.sql.gz` file and the production `.env` to storage outside the server. The bind-mounted `data/` directory is included in the site tree, but an online filesystem snapshot is not a substitute for a consistent PostgreSQL dump.

Restore a dump on the destination server before switching traffic:

```bash
./deploy/server/restore.sh /absolute/path/to/wordtower.sql.gz
```

To move to a new server:

1. Install Docker Compose v2 and OpenResty/1Panel.
2. Recreate the deployment directory and `.env`, then log in to GHCR if required.
3. Start PostgreSQL and restore the latest SQL dump before opening traffic.
4. Copy the OpenResty location configuration and update DNS.
5. Update `DEPLOY_HOST` and `DEPLOY_KNOWN_HOSTS` in GitHub, then rerun the latest workflow or push `main`.

Database restoration is intentionally a manual operation because it replaces persistent data. For a new empty database, the deployment workflow applies all Alembic migrations automatically.
