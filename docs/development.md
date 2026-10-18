# Development

## Setup

Install the runtime and dev dependencies from the repository root, and start PostgreSQL:

```bash
pip install -e ".[dev]"
docker compose up -d db
```

Run the same checks as CI:

```bash
ruff check .
pytest
```

Tests use temporary directories, their own settings and the `mini_rag_test` database, which they create on the same server when it is missing (set `TEST_DATABASE_URL` to use another one), so they need no `.env` file and never write to `assets/` or the development database. Embeddings and answers come from deterministic fakes, so the tests need no API key or network.

## Docker

The `Dockerfile` builds the API image in two stages: the first installs the package and its dependencies into a virtual environment, the second copies only that environment into a slim Python image and runs as an unprivileged user (UID 10001). `compose.yaml` runs the image as the `app` service next to the database, with settings from `.env` and the database address and file storage path set for the stack; uploaded files live in the `files` volume. On every start the service applies any missing migrations, then starts the API.

```bash
docker compose up --build            # the whole stack, rebuilt after code changes
docker compose up -d db              # only the database, to run the API with uvicorn
docker compose logs -f app           # follow the API's logs
docker compose down                  # stop; add --volumes to delete the data too
```

CI builds the image and starts the stack on every push, checks `/api/v1/health` and an upload, and checks that the API does not run as root.

## Database migrations

The schema is managed with Alembic; the app never creates tables itself. Migrations live in `src/mini_rag/persistence/migrations/`, and Alembic's settings are in `pyproject.toml`, so run these commands from the repository root:

```bash
alembic upgrade head                                  # apply all migrations
alembic downgrade -1                                  # undo the latest one
alembic revision --autogenerate -m "describe change"  # after changing persistence/tables.py
```

Review every generated migration before committing it. `tests/test_migrations.py` fails if the models and the migrations ever disagree.

The database needs the pgvector extension, version 0.8 or newer; the `pgvector/pgvector:pg16` image in `compose.yaml` has it, and migration `0002` enables it. To use a model with another vector length, change `EMBEDDING_DIMENSIONS` in `persistence/tables.py`, add a migration that changes the column and its index, and set `EMBEDDING_DIMENSIONS` in `.env` to match.

**Upgrading a local database from before vector search:** `compose.yaml` used `postgres:16-alpine` before and now uses the Debian-based `pgvector/pgvector:pg16`. Text sorting rules differ between the two, so don't reuse the old data volume; recreate it, migrate, and upload your files again:

```bash
docker compose down -v            # deletes the local database volume
docker compose up -d db
alembic upgrade head
```

## Workflow

- Branch from `start-001`, the default branch, and keep each pull request to one topic.
- Every change comes with tests; CI runs `ruff check .` and `pytest` on Python 3.11 and 3.12 against PostgreSQL 16 with pgvector, and a pull request merges only when it passes.
- See [CONTRIBUTING.md](../.github/CONTRIBUTING.md) for the architecture rules and style.
