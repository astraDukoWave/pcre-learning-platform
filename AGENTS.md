# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

PCRE Learning Platform — English language learning app with FastAPI backend + PostgreSQL. The frontend (Next.js) is planned but not yet implemented. All services run in Docker via `apps/backend/docker-compose.yml`.

### Starting services

```bash
cd apps/backend
cp .env.example .env  # only if .env doesn't exist
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec -T backend python -c "import sys; sys.path.insert(0, '/app'); from app.db.seed import seed_data; seed_data()"
```

- The backend container runs `uvicorn --reload` and mounts `./app`, `./alembic`, `./alembic.ini` as volumes, so code changes are hot-reloaded.
- PostgreSQL healthcheck gates backend startup (`service_healthy`).

### Gotchas

- **docker-compose v1 not installed**: Only `docker compose` (v2 plugin) is available. The repo's `validate-phase1-final.sh` uses `docker-compose`; create a shim if needed: `echo -e '#!/bin/sh\nexec docker compose "$@"' | sudo tee /usr/local/bin/docker-compose && sudo chmod +x /usr/local/bin/docker-compose`.
- **Seed script module path**: Running `python app/db/seed.py` inside the container fails with `ModuleNotFoundError`. Use `python -c "import sys; sys.path.insert(0, '/app'); from app.db.seed import seed_data; seed_data()"` instead.
- **Validation script Test 7**: `validate-phase1-final.sh` checks for migration `bc0bb9a48e10` (Phase 1) but the latest head is `816c80672425` (Phase 1.5). This is a pre-existing script issue.
- **No tests directory**: `pyproject.toml` configures pytest (`testpaths = ["tests"]`) but `apps/backend/tests/` does not exist yet.

### Lint / format

```bash
cd apps/backend
black --check app/          # formatter check
isort --check-only app/     # import sort check
black app/                  # auto-format
isort app/                  # auto-sort imports
```

Config is in `apps/backend/pyproject.toml` (line-length 88, black profile for isort).

### API verification

- Health: `curl http://localhost:8000/health`
- Swagger UI: `http://localhost:8000/docs`
- Courses: `curl http://localhost:8000/api/v1/courses`
- Class with quiz: `curl http://localhost:8000/api/v1/courses/ingles-b1-expresiones-tiempo/classes/clase-10-comparativos`

### Docker restart after VM reboot

Docker daemon must be started manually in the cloud VM (no systemd):
```bash
sudo dockerd &>/tmp/dockerd.log &
sleep 3
sudo chmod 666 /var/run/docker.sock
```
