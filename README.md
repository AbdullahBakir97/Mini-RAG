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
| Storage for projects, files and chunks | 🔜 Next |
| Embeddings and vector search | Planned |
| Answer generation with an LLM | Planned |
| Docker packaging | Planned |

## Tech stack

- **Python 3.11+** with **FastAPI** and **Uvicorn**
- **pydantic-settings** for configuration from `.env`
- **PostgreSQL 16** with **SQLAlchemy 2** (async, asyncpg)
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
docker compose up -d db          # PostgreSQL 16 on localhost:5432
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
| `OPEN_API_KEY` | `""` | API key for the LLM provider (used from the generation stage) |
| `DATABASE_URL` | `"postgresql+asyncpg://mini_rag:mini_rag@localhost:5432/mini_rag"` | PostgreSQL connection (must use the `postgresql+asyncpg://` driver); the default matches `docker-compose.yml` |
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
| `POST` | `/api/v1/data/upload/{project_id}` | Upload a file into a project |
| `POST` | `/api/v1/data/process/{project_id}` | Split an uploaded file into text chunks |

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
{
  "signal": "processing_success",
  "file_id": "a16q20nzrtvj_notes.txt",
  "chunks_count": 1,
  "chunks": [
    {"text": "...", "metadata": {"source": "a16q20nzrtvj_notes.txt", "chunk_index": 0}}
  ]
}
```

| Field | Default | Rules |
|---|---|---|
| `file_id` | required | ID returned by the upload endpoint |
| `chunk_size` | `1000` | 1–100000 characters |
| `overlap_size` | `200` | 0 or more, smaller than `chunk_size` |

Supported files are `.txt` (read as UTF-8) and `.pdf`. PDF chunks also carry a `page` number in their metadata.

| Case | Status | Response |
|---|---|---|
| Chunks created | `200` | `{"signal": "processing_success", ...}` |
| No such file in this project | `404` | `{"signal": "file_not_found"}` |
| Extension is not `.txt` or `.pdf` | `415` | `{"signal": "file_type_not_supported"}` |
| No extractable text (e.g. a scanned PDF) | `422` | `{"signal": "file_has_no_text"}` |
| File could not be read | `422` | `{"signal": "processing_failed"}` |
| Invalid `file_id` or chunk settings | `422` | Validation error details |

## Architecture

The code is split into layers. Each layer only depends on the layers below it, and only the API layer knows about HTTP, so the business logic can be reused from a CLI or a background worker and tested without a web server. `tests/test_architecture.py` enforces these rules.

```
api        routes, request/response schemas, dependency wiring, error handler
 │
services   UploadService, ProcessingService: the use cases
 │
storage · loaders · text     files on disk · one loader per file type · text splitter
 │
domain     Document, Chunk, response signals
```

`core` holds settings and the `AppError` hierarchy; `api`, `services`, `storage` and `loaders` may use it. `text` and `domain` depend on nothing, so they stay reusable on their own.

| Concern | Where it lives |
|---|---|
| Validation of IDs and request bodies | `api/schemas.py` (`ProjectId`, `FileId`, request models) |
| Turning errors into responses | Services raise an `AppError` subclass; `api/error_handlers.py` maps it to `{"signal": ...}` and its status code |
| Wiring objects together | `api/dependencies.py`, using FastAPI `Depends` |
| Path safety | `storage/file_storage.py`: every path is checked to stay inside `FILES_DIR` |

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

Tests use temporary directories, their own settings and the `mini_rag_test` database (set `TEST_DATABASE_URL` to use another one), so they need no `.env` file and never write to `assets/` or the development database.

## Project structure

```
Mini-RAG/
├── src/
│   ├── mini_rag/
│   │   ├── main.py           # create_app(): routers and error handler
│   │   ├── core/             # Settings, application errors, logging setup
│   │   ├── api/              # Routes, schemas, dependency wiring, error handler
│   │   ├── services/         # Upload rules and document processing
│   │   ├── storage/          # File storage and path safety
│   │   ├── loaders/          # One loader per file type, chosen by extension
│   │   ├── text/             # Recursive text splitter
│   │   └── domain/           # Document, Chunk and response signals
├── assets/files/             # Uploaded files (git-ignored, FILES_DIR)
├── migrations/               # Alembic migrations
├── tests/                    # pytest suite
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── alembic.ini
├── docker-compose.yml        # Local PostgreSQL
└── pyproject.toml            # pytest and ruff configuration
```

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). Security issues: see [SECURITY.md](./SECURITY.md).

## Author

**Abdullah Bakir** — [@AbdullahBakir97](https://github.com/AbdullahBakir97)

Full-Stack Developer based in Germany - Python · Django · Vue · Nuxt.

## License

Released under the [MIT License](./LICENSE).
