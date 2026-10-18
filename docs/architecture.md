# Architecture

## Layers

The code is split into layers. Each layer only depends on the layers below it, and only the API layer knows about HTTP, so the business logic can be reused from a CLI or a background worker and tested without a web server. `tests/test_architecture.py` enforces these rules.

```
api          routes, request/response schemas, dependency wiring, error handler
 │
services     UploadService, ProcessingService, ProjectService, IndexingService, SearchService,
             AnswerService
 │
persistence · embeddings · llm · prompts · storage · loaders · text
             PostgreSQL + pgvector repositories · embedding client · chat model client ·
             versioned prompts · files on disk · one loader per file type · text splitter
 │
domain       Document, Chunk, Project, FileRecord, ScoredChunk, Message, repository,
             Embedder and LLM interfaces, response signals
```

Services depend on the repository **interfaces** in `domain/repositories.py` (`ProjectRepository`, `FileRepository`, `ChunkRepository` and a `UnitOfWork` that shares one transaction), never on SQLAlchemy. `persistence/` implements them; the API wires the implementation in, and unit tests swap in in-memory fakes. Embeddings work the same way: services use the `Embedder` interface in `domain/embedder.py`, `embeddings/` implements it with the OpenAI SDK, and tests use a deterministic fake, so no test needs the network. Language models follow the same pattern: services use the `LLM` interface in `domain/llm.py`, `llm/` implements it with the OpenAI chat completions API, and tests use `FakeLLM`.

`core` holds settings, the `AppError` hierarchy and logging setup; `api`, `services`, `persistence`, `embeddings`, `llm`, `storage` and `loaders` may use it. `text` and `domain` depend on nothing, and `prompts` only on `domain`, so they stay reusable on their own. Only `api` may import FastAPI, only `persistence` (and the API, which wires it up) may import SQLAlchemy or pgvector, and only `embeddings` and `llm` may import the OpenAI SDK.

| Concern | Where it lives |
|---|---|
| Validation of IDs and request bodies | `api/schemas.py` (`ProjectId`, `FileId`, request models) |
| Turning errors into responses | Services raise an `AppError` subclass; `api/error_handlers.py` maps it to `{"signal": ...}` and its status code |
| Wiring objects together | `api/dependencies.py`, using FastAPI `Depends` |
| Path safety | `storage/file_storage.py`: every path is checked to stay inside `FILES_DIR` |
| Transactions | One database session per request; services call `uow.commit()`, and anything uncommitted is rolled back |
| Database schema | `persistence/tables.py`, changed only through Alembic migrations |
| Vector search | `chunks.embedding vector(1536)` with an HNSW index for cosine distance; search uses pgvector's iterative scan so filtering by project still returns `top_k` results |

## Prompts

Prompts live in `prompts/`, apart from the code that sends them, so they can be reviewed and versioned on their own. A released prompt never changes: new wording gets a new version (`answer-v2`), and `ANSWER_PROMPT` points to the one in use. `tests/test_answer_prompt.py` pins a hash of every released prompt, so editing one by accident fails CI, and each answer reports the `prompt_version` that produced it.

Document text is data, not instructions. The system message holds the rules, including never following instructions found in a source; the user message holds the numbered sources in `<source>` tags and the question in `<question>` tags. Any text that would open or close one of these tags early is escaped, so a document cannot end its own source and pose as instructions.

## Adding a file type

Write a loader with a `load(path, source)` method that returns `Document`s, and register its extension in `loaders/registry.py`:

```python
def default_loader_registry() -> LoaderRegistry:
    return LoaderRegistry({".txt": TextLoader(), ".pdf": PdfLoader(), ".md": MarkdownLoader()})
```

Nothing else changes: the processing service and the API pick it up automatically.

## Project structure

```
Mini-RAG/
├── .github/                  # CI, Dependabot, contributing, conduct and security policies
├── docs/                     # This documentation
├── src/mini_rag/
│   ├── main.py               # create_app(): routers, error handler, lifespan
│   ├── core/                 # Settings, application errors, logging setup
│   ├── api/                  # Routes, schemas, dependency wiring, error handler
│   ├── services/             # Use cases: upload, processing, project queries, indexing, search, answers
│   ├── persistence/          # SQLAlchemy tables, engine, repositories (with pgvector)
│   │   └── migrations/       # Alembic migrations
│   ├── embeddings/           # Embedding client for OpenAI-compatible APIs
│   ├── llm/                  # Chat model client for OpenAI-compatible APIs
│   ├── prompts/              # Versioned prompts
│   ├── storage/              # File storage and path safety
│   ├── loaders/              # One loader per file type, chosen by extension
│   ├── text/                 # Recursive text splitter
│   └── domain/               # Domain models, repository, Embedder and LLM interfaces, signals
├── tests/                    # pytest suite
├── .env.example              # Settings template (copy to .env)
├── Dockerfile                # API image: multi-stage, runs as an unprivileged user
├── compose.yaml              # The stack: PostgreSQL with pgvector, and the API
└── pyproject.toml            # Package, dependencies; Alembic, pytest and ruff settings
```

Uploaded files are stored in `assets/files/` (`FILES_DIR`), which is git-ignored.

Contributor rules that follow from this design are in [CONTRIBUTING.md](../.github/CONTRIBUTING.md#architecture-rules).
