# Mini RAG

> A minimal retrieval-augmented generation (RAG) service built with FastAPI, developed step by step from document upload to LLM-generated answers.

[![CI](https://github.com/AbdullahBakir97/Mini-RAG/actions/workflows/ci.yml/badge.svg)](https://github.com/AbdullahBakir97/Mini-RAG/actions/workflows/ci.yml) ![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=flat-square&logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](./LICENSE)

---

## Overview

Mini RAG is a small, readable backend for answering questions over your own documents. It is being built in stages:

| Stage | Status |
|---|---|
| File upload API with validation | ✅ Done |
| Document processing (load TXT/PDF, split into chunks) | ✅ Done |
| Storage for projects, files and chunks (PostgreSQL) | ✅ Done |
| Embeddings and vector search (pgvector) | ✅ Done |
| Answer generation with an LLM | 🔜 Next |
| Docker packaging | Planned |

## Tech stack

- **Python 3.11+** with **FastAPI** and **Uvicorn**
- **pydantic-settings** for configuration from `.env`
- **PostgreSQL 16** with **SQLAlchemy 2** (async, asyncpg)
- **pgvector** for vector search, with embeddings from the **OpenAI** API or any OpenAI-compatible server (e.g. Ollama)
- **aiofiles** for streaming uploads to disk
- **pypdf** for PDF text extraction, plus a small built-in recursive text splitter
- **pytest** and **ruff** for tests and linting, run in GitHub Actions CI

## Quick start

```bash
git clone https://github.com/AbdullahBakir97/Mini-RAG.git
cd Mini-RAG

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # Windows: copy .env.example .env
docker compose up -d db          # PostgreSQL 16 with pgvector on localhost:5432
alembic upgrade head             # create or update the database tables
uvicorn --app-dir src mini_rag.main:app --reload
```

Then open **http://localhost:8000**. It redirects to the interactive API docs at `/docs`, where you can try every endpoint from the browser.

> Run commands from the repository root: `--app-dir src` tells Uvicorn where the `mini_rag` package lives, and `.env` is read from the current directory.

## Configuration

Settings are read from `.env` in the repository root (copy it from `.env.example`) or from environment variables.

| Variable | Example | Description |
|---|---|---|
| `APP_NAME` | `"mini-RAG"` | Name returned by the welcome endpoint |
| `APP_VERSION` | `"0.1"` | Version returned by the welcome endpoint |
| `OPENAI_API_KEY` | `""` | API key for OpenAI (embeddings now, answer generation later). Leave empty for a local server set in `EMBEDDING_BASE_URL` |
| `DATABASE_URL` | `"postgresql+asyncpg://mini_rag:mini_rag@localhost:5432/mini_rag"` | PostgreSQL connection (must use the `postgresql+asyncpg://` driver); the default matches `docker-compose.yml` |
| `EMBEDDING_BASE_URL` | `""` | OpenAI-compatible server for embeddings, e.g. `"http://localhost:11434/v1"` for Ollama; empty means OpenAI |
| `EMBEDDING_MODEL` | `"text-embedding-3-small"` | Embedding model name |
| `EMBEDDING_DIMENSIONS` | `1536` | Length of each vector. Must match the database column (1536); the app refuses to start otherwise |
| `EMBEDDING_BATCH_SIZE` | `64` | Chunks sent per embedding request while indexing |
| `LOG_LEVEL` | `"INFO"` | Level for the app's own logs: `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL` (libraries log warnings and above) |
| `FILES_DIR` | `"assets/files"` | Folder where uploaded files are stored, one subfolder per project |
| `FILE_ALLOWED_TYPES` | `["text/plain", "application/pdf"]` | MIME types accepted for upload |
| `FILE_MAX_SIZE` | `10` | Maximum upload size in MB |
| `FILE_DEFAULT_CHUNK_SIZE` | `512000` | Bytes read per chunk while saving an upload |

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Redirects to `/docs` |
| `GET` | `/api/v1/` | Welcome message with app name and version |
| `GET` | `/api/v1/health` | `200` `{"status": "ok", "database": "ok"}`, or `503` when the database is unreachable |
| `POST` | `/api/v1/data/upload/{project_id}` | Upload a file into a project |
| `POST` | `/api/v1/data/process/{project_id}` | Split an uploaded file into chunks and store them |
| `POST` | `/api/v1/index/{project_id}` | Embed a project's chunks so they can be searched |
| `POST` | `/api/v1/search/{project_id}` | Find the chunks that best match a question |
| `GET` | `/api/v1/projects/{project_id}` | Project details with file, chunk and index counts |
| `GET` | `/api/v1/projects/{project_id}/files` | List a project's files (paged) |
| `GET` | `/api/v1/projects/{project_id}/files/{file_id}/chunks` | List a file's chunks (paged) |

### Upload a file

`project_id` may contain letters, digits, `_` and `-` (1–64 characters). Files are stored under `FILES_DIR/<project_id>/` (default `assets/files/`) with a random prefix, so uploads never overwrite each other.

```bash
curl -F "file=@notes.txt;type=text/plain" http://localhost:8000/api/v1/data/upload/demo1
```

```json
{"signal": "file_uploaded_successfully", "file_id": "a16q20nzrtvj_notes.txt"}
```

| Case | Status | Response |
|---|---|---|
| Upload saved | `200` | `{"signal": "file_uploaded_successfully", "file_id": "..."}` |
| File type not in `FILE_ALLOWED_TYPES` | `415` | `{"signal": "file_type_not_supported"}` |
| File larger than `FILE_MAX_SIZE` | `413` | `{"signal": "file_size_exceeded"}` |
| Invalid `project_id` | `422` | Validation error details |
| Storage failure on the server | `500` | `{"signal": "file_upload_failed"}` |

### Process a file into chunks

Send the `file_id` returned by the upload. Text is split on paragraphs first, then lines, then words, and a word is cut only if it alone is longer than a chunk. Paragraph breaks are respected: a chunk may hold several whole paragraphs, but part of a paragraph is never joined with another one. Every chunk after the first begins with up to `overlap_size` characters of the text just before it, starting at a word boundary, so context carries across chunk borders. Each chunk is at most `chunk_size` characters, overlap included, and is an exact slice of the document text.

```bash
curl -X POST http://localhost:8000/api/v1/data/process/demo1 \
  -H "Content-Type: application/json" \
  -d '{"file_id": "a16q20nzrtvj_notes.txt", "chunk_size": 1000, "overlap_size": 200}'
```

```json
{"signal": "processing_success", "file_id": "a16q20nzrtvj_notes.txt", "chunks_count": 1}
```

The chunks are stored in the database. Processing a file again (for example with other chunk settings) replaces its chunks in one transaction; if it fails, the previous chunks are kept.

| Field | Default | Rules |
|---|---|---|
| `file_id` | required | ID returned by the upload endpoint |
| `chunk_size` | `1000` | 1–100000 characters |
| `overlap_size` | `200` | 0 or more, smaller than `chunk_size` |

Supported files are `.txt` (read as UTF-8) and `.pdf`. PDF chunks also carry a `page` number in their metadata.

| Case | Status | Response |
|---|---|---|
| Chunks created | `200` | `{"signal": "processing_success", ...}` |
| No such file in this project (or not uploaded through the API) | `404` | `{"signal": "file_not_found"}` |
| Extension is not `.txt` or `.pdf` | `415` | `{"signal": "file_type_not_supported"}` |
| No extractable text (e.g. a scanned PDF) | `422` | `{"signal": "file_has_no_text"}` |
| File could not be read | `422` | `{"signal": "processing_failed"}` |
| Invalid `file_id` or chunk settings | `422` | Validation error details |

### Read projects, files and chunks

```bash
curl http://localhost:8000/api/v1/projects/demo1
curl "http://localhost:8000/api/v1/projects/demo1/files?offset=0&limit=20"
curl "http://localhost:8000/api/v1/projects/demo1/files/a16q20nzrtvj_notes.txt/chunks?limit=5"
```

```json
{"name": "demo1", "created_at": "2026-10-16T21:13:55Z", "files_count": 1, "chunks_count": 4, "embedded_chunks_count": 4}
```

```json
{
  "total": 4, "offset": 0, "limit": 5,
  "items": [
    {"chunk_index": 0, "text": "...", "metadata": {"source": "a16q20nzrtvj_notes.txt", "page": 1}}
  ]
}
```

Lists are paged with `offset` (default `0`) and `limit` (default `20`, at most `100`); `total` is the number of items overall. Files are listed in upload order, chunks by `chunk_index`. An unknown project returns `404` `{"signal": "project_not_found"}`, an unknown file `404` `{"signal": "file_not_found"}`.

### Index chunks for search

Indexing turns each chunk into an embedding: a vector that captures its meaning. It needs `OPENAI_API_KEY`, or an OpenAI-compatible server in `EMBEDDING_BASE_URL`.

```bash
curl -X POST http://localhost:8000/api/v1/index/demo1
curl -X POST http://localhost:8000/api/v1/index/demo1 \
  -H "Content-Type: application/json" -d '{"file_id": "a16q20nzrtvj_notes.txt"}'   # one file only
```

```json
{"signal": "indexing_success", "embedded_count": 4, "chunks_count": 4}
```

Only chunks without an embedding are sent, in batches of `EMBEDDING_BATCH_SIZE`, and each batch is saved on its own. So calling it again after a failure continues where it stopped, and after processing a file only its new chunks are embedded. Processing a file again removes its old embeddings with its old chunks, so index the project again afterwards. `embedded_chunks_count` in the project details shows how much of a project is indexed.

| Case | Status | Response |
|---|---|---|
| Done (also when there was nothing to do) | `200` | `{"signal": "indexing_success", ...}` |
| No such project or file | `404` | `{"signal": "project_not_found"}` / `{"signal": "file_not_found"}` |
| The embedding provider failed | `502` | `{"signal": "embedding_failed"}` |
| No API key and no `EMBEDDING_BASE_URL` | `503` | `{"signal": "embedding_not_configured"}` |

### Search

```bash
curl -X POST http://localhost:8000/api/v1/search/demo1 \
  -H "Content-Type: application/json" \
  -d '{"query": "How does the overlap work?", "top_k": 3}'
```

```json
{
  "signal": "search_success",
  "results": [
    {"file_id": "a16q20nzrtvj_notes.txt", "chunk_index": 2, "score": 0.83,
     "text": "...", "metadata": {"source": "a16q20nzrtvj_notes.txt", "page": 1}}
  ]
}
```

Results are the project's indexed chunks closest in meaning to the query, best first. `score` is the cosine similarity between the query and the chunk (1 is the best match). Chunks that are not indexed yet are not found; a project without any returns an empty list.

| Field | Default | Rules |
|---|---|---|
| `query` | required | 1–2000 characters, not blank |
| `top_k` | `5` | 1–50 |
| `min_score` | none | -1 to 1; leaves out weaker results |

Errors are the same as for indexing, without `file_not_found`.

## Architecture

The code is split into layers. Each layer only depends on the layers below it, and only the API layer knows about HTTP, so the business logic can be reused from a CLI or a background worker and tested without a web server. `tests/test_architecture.py` enforces these rules.

```
api          routes, request/response schemas, dependency wiring, error handler
 │
services     UploadService, ProcessingService, ProjectService, IndexingService, SearchService
 │
persistence · embeddings · storage · loaders · text
             PostgreSQL + pgvector repositories · embedding client · files on disk ·
             one loader per file type · text splitter
 │
domain       Document, Chunk, Project, FileRecord, ScoredChunk, repository and Embedder
             interfaces, response signals
```

Services depend on the repository **interfaces** in `domain/repositories.py` (`ProjectRepository`, `FileRepository`, `ChunkRepository` and a `UnitOfWork` that shares one transaction), never on SQLAlchemy. `persistence/` implements them; the API wires the implementation in, and unit tests swap in in-memory fakes. Embeddings work the same way: services use the `Embedder` interface in `domain/embedder.py`, `embeddings/` implements it with the OpenAI SDK, and tests use a deterministic fake, so no test needs the network.

`core` holds settings, the `AppError` hierarchy and logging setup; `api`, `services`, `persistence`, `embeddings`, `storage` and `loaders` may use it. `text` and `domain` depend on nothing, so they stay reusable on their own. Only `api` may import FastAPI, only `persistence` (and the API, which wires it up) may import SQLAlchemy or pgvector, and only `embeddings` may import the OpenAI SDK.

| Concern | Where it lives |
|---|---|
| Validation of IDs and request bodies | `api/schemas.py` (`ProjectId`, `FileId`, request models) |
| Turning errors into responses | Services raise an `AppError` subclass; `api/error_handlers.py` maps it to `{"signal": ...}` and its status code |
| Wiring objects together | `api/dependencies.py`, using FastAPI `Depends` |
| Path safety | `storage/file_storage.py`: every path is checked to stay inside `FILES_DIR` |
| Transactions | One database session per request; services call `uow.commit()`, and anything uncommitted is rolled back |
| Database schema | `persistence/tables.py`, changed only through Alembic migrations |
| Vector search | `chunks.embedding vector(1536)` with an HNSW index for cosine distance; search uses pgvector's iterative scan so filtering by project still returns `top_k` results |

### Adding a file type

Write a loader with a `load(path, source)` method that returns `Document`s, and register its extension in `loaders/registry.py`:

```python
def default_loader_registry() -> LoaderRegistry:
    return LoaderRegistry({".txt": TextLoader(), ".pdf": PdfLoader(), ".md": MarkdownLoader()})
```

Nothing else changes: the processing service and the API pick it up automatically.

## Database migrations

The schema is managed with Alembic; the app never creates tables itself.

```bash
alembic upgrade head                                  # apply all migrations
alembic downgrade -1                                  # undo the latest one
alembic revision --autogenerate -m "describe change"  # after changing persistence/tables.py
```

Review every generated migration before committing it. `tests/test_migrations.py` fails if the models and the migrations ever disagree.

The database needs the pgvector extension, version 0.8 or newer; the `pgvector/pgvector:pg16` image in `docker-compose.yml` has it, and migration `0002` enables it. To use a model with another vector length, change `EMBEDDING_DIMENSIONS` in `persistence/tables.py`, add a migration that changes the column and its index, and set `EMBEDDING_DIMENSIONS` in `.env` to match.

**Upgrading a local database from before vector search:** `docker-compose.yml` used `postgres:16-alpine` before and now uses the Debian-based `pgvector/pgvector:pg16`. Text sorting rules differ between the two, so don't reuse the old data volume; recreate it, migrate, and upload your files again:

```bash
docker compose down -v            # deletes the local database volume
docker compose up -d db
alembic upgrade head
```

## Development

Install the runtime and dev dependencies from the repository root, and start PostgreSQL (the compose file also creates the `mini_rag_test` database the tests use):

```bash
pip install -r requirements-dev.txt
docker compose up -d db
```

Run the same checks as CI:

```bash
ruff check .
pytest
```

Tests use temporary directories, their own settings and the `mini_rag_test` database (set `TEST_DATABASE_URL` to use another one), so they need no `.env` file and never write to `assets/` or the development database. Embeddings come from a deterministic fake, so the tests need no API key or network.

## Project structure

```
Mini-RAG/
├── src/
│   ├── mini_rag/
│   │   ├── main.py           # create_app(): routers and error handler
│   │   ├── core/             # Settings, application errors, logging setup
│   │   ├── api/              # Routes, schemas, dependency wiring, error handler
│   │   ├── services/         # Use cases: upload, processing, project queries, indexing, search
│   │   ├── persistence/      # SQLAlchemy tables, engine and repositories (with pgvector)
│   │   ├── embeddings/       # Embedding client for OpenAI-compatible APIs
│   │   ├── storage/          # File storage and path safety
│   │   ├── loaders/          # One loader per file type, chosen by extension
│   │   ├── text/             # Recursive text splitter
│   │   └── domain/           # Domain models, repository and Embedder interfaces, signals
├── assets/files/             # Uploaded files (git-ignored, FILES_DIR)
├── docker/postgres/init/     # Creates the test database in docker-compose
├── migrations/               # Alembic migrations
├── tests/                    # pytest suite
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── alembic.ini
├── docker-compose.yml        # Local PostgreSQL with pgvector
└── pyproject.toml            # pytest and ruff configuration
```

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md). Security issues: see [SECURITY.md](.github/SECURITY.md).

## Author

**Abdullah Bakir** — [@AbdullahBakir97](https://github.com/AbdullahBakir97)

Full-Stack Developer based in Germany - Python · Django · Vue · Nuxt.

## License

Released under the [MIT License](./LICENSE).
