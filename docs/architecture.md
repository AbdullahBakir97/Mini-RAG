# Architecture

## Layers

The code is split into layers. Each layer only depends on the layers below it, and only the API layer knows about HTTP, so the business logic can be reused from a CLI or a background worker and tested without a web server. `tests/test_architecture.py` enforces these rules.

```
api          routes, request/response schemas, dependency wiring, error handler
 │
services     UploadService, ProcessingService, ProjectService, IndexingService, SearchService,
             AnswerService, ConversationService, EvaluationService
 │
persistence · embeddings · llm · prompts · evaluation · storage · loaders · text
             PostgreSQL + pgvector repositories · embedding client · chat model client ·
             versioned prompts · datasets and metrics · files on disk ·
             one loader per file type · text splitter
 │
domain       Document, Chunk, Project, FileRecord, ScoredChunk, Message, Conversation, repository,
             Embedder and LLM interfaces, response signals
```

Services depend on the repository **interfaces** in `domain/repositories.py` (`ProjectRepository`, `FileRepository`, `ChunkRepository`, `AnswerRepository`, `ConversationRepository` and a `UnitOfWork` that shares one transaction), never on SQLAlchemy. `persistence/` implements them; the API wires the implementation in, and unit tests swap in in-memory fakes. Embeddings work the same way: services use the `Embedder` interface in `domain/embedder.py`, `embeddings/` implements it with the OpenAI SDK, and tests use a deterministic fake, so no test needs the network. Language models follow the same pattern: services use the `LLM` interface in `domain/llm.py`, `llm/` implements it with the OpenAI chat completions API, and tests use `FakeLLM`.

`cli.py` wires the same pieces together for the `mini-rag` command, as `api` does for HTTP: `mini-rag eval` runs a dataset through the real services (see [Evaluation](evaluation.md)), and `evaluation` itself holds only datasets, metrics and reports, depending on nothing but `domain`.

`core` holds settings, the `AppError` hierarchy and logging setup; `api`, `services`, `persistence`, `embeddings`, `llm`, `storage` and `loaders` may use it. `text` and `domain` depend on nothing, and `prompts` only on `domain`, so they stay reusable on their own. Only `api` may import FastAPI, only `persistence` (and the API, which wires it up) may import SQLAlchemy or pgvector, and only `embeddings` and `llm` may import the OpenAI SDK.

| Concern | Where it lives |
|---|---|
| Validation of IDs and request bodies | `api/schemas.py` (`ProjectId`, `FileId`, request models) |
| Turning errors into responses | Services raise an `AppError` subclass; `api/error_handlers.py` maps it to `{"signal": ...}` and its status code |
| Wiring objects together | `api/dependencies.py`, using FastAPI `Depends` |
| Path safety | `storage/file_storage.py`: every path is checked to stay inside `FILES_DIR` |
| Transactions | One database session per request; services call `uow.commit()`, and anything uncommitted is rolled back |
| Database schema | `persistence/tables.py`, changed only through Alembic migrations |
| Usage and cost | `AnswerService` records every answer's tokens and cost in the `answers` table, never the question or answer text; `GET /api/v1/projects/{project_id}/usage` adds them up |
| Conversations | `conversations` and `conversation_messages` keep the questions and answers asked in a conversation, with their citations (copied, so they still read the same after a file is re-processed); deleting a project's rows cascades to them. `AnswerService` rewrites a follow-up with the condense prompt before searching |
| Vector search | `chunks.embedding vector(1536)` (another length after `mini-rag resize-embeddings`, for another embedding model) with an HNSW index for cosine distance; search uses pgvector's iterative scan so filtering by project still returns `top_k` results |

## Prompts

Prompts live in `prompts/`, apart from the code that sends them, so they can be reviewed and versioned on their own. A released prompt never changes: new wording gets a new version (`answer-v2`), and `ANSWER_PROMPT` points to the one in use. `tests/test_answer_prompt.py` pins a hash of every released prompt, so editing one by accident fails CI, and each answer reports the `prompt_version` that produced it.

Three prompts are in use: `answer-v1` writes the answer, `condense-v1` rewrites a follow-up in a conversation into a standalone question to search with ("And on Fridays?" becomes "Do production deploys happen on Fridays?"), and `judge-v1` grades answers during [evaluation](evaluation.md#answer-metrics). All are pinned the same way.

Document text is data, not instructions. The system message holds the rules, including never following instructions found in a source; the user message holds the numbered sources in `<source>` tags and the question in `<question>` tags. Any text that would open or close one of these tags early is escaped, so a document cannot end its own source and pose as instructions. In a conversation, the earlier questions and answers go to the model as earlier messages, with their `[n]` markers removed because those numbered other sources; the condense prompt quotes them in `<conversation>` tags, escaped the same way.

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
├── evals/                    # Versioned evaluation datasets and their baselines (see evaluation.md)
├── src/mini_rag/
│   ├── main.py               # create_app(): routers, error handler, lifespan
│   ├── cli.py                # The mini-rag command: resize-embeddings, eval
│   ├── core/                 # Settings, application errors, logging setup
│   ├── api/                  # Routes, schemas, dependency wiring, error handler
│   ├── services/             # Use cases: upload, processing, project queries, indexing, search, answers, conversations, evaluation
│   ├── persistence/          # SQLAlchemy tables, engine, repositories (with pgvector)
│   │   └── migrations/       # Alembic migrations
│   ├── embeddings/           # Embedding client for OpenAI-compatible APIs
│   ├── llm/                  # Chat model client for OpenAI-compatible APIs
│   ├── prompts/              # Versioned prompts
│   ├── evaluation/           # Evaluation datasets, retrieval metrics, reports and baselines
│   ├── storage/              # File storage and path safety
│   ├── loaders/              # One loader per file type, chosen by extension
│   ├── text/                 # Recursive text splitter
│   └── domain/               # Domain models, repository, Embedder and LLM interfaces, signals
├── tests/                    # pytest suite
├── frontend/                 # Web app: Vue 3, TypeScript, Vite; nginx image (see web.md)
├── .env.example              # Settings template (copy to .env)
├── Dockerfile                # API image: multi-stage, runs as an unprivileged user
├── compose.yaml              # The stack: PostgreSQL with pgvector, the API and the web app
└── pyproject.toml            # Package, dependencies; Alembic, pytest and ruff settings
```

The web app in `frontend/` is a client of the public API only: it uses the same endpoints as any other app, so everything it does can also be done with `curl`. See [Web app](web.md).

Uploaded files are stored in `assets/files/` (`FILES_DIR`), which is git-ignored.

Contributor rules that follow from this design are in [CONTRIBUTING.md](../.github/CONTRIBUTING.md#architecture-rules).
