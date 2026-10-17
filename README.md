# Mini RAG

> A retrieval-augmented generation (RAG) service: upload documents, split them into chunks, index them with embeddings, and find the passages that answer a question.

[![CI](https://github.com/AbdullahBakir97/Mini-RAG/actions/workflows/ci.yml/badge.svg)](https://github.com/AbdullahBakir97/Mini-RAG/actions/workflows/ci.yml) ![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=flat-square&logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](./LICENSE)

## Features

- **Upload** TXT and PDF files into separate projects, with type checks and a size limit enforced while streaming.
- **Process** them into chunks that respect paragraphs, with exact overlap between chunks and page numbers for PDFs.
- **Index** chunks as embeddings with OpenAI or any OpenAI-compatible server, such as Ollama.
- **Search** by meaning with PostgreSQL and pgvector, best match first, with a similarity score.
- **Ask** questions and get answers with citations to the file, page and chunk, or an explicit "no answer" when the documents don't say.
- **Browse** projects, files and chunks through paged endpoints; check readiness with a health endpoint.

Streaming answers and conversations are next; see the [roadmap](docs/roadmap.md).

## Quick start

Requires Python 3.11+ and Docker.

```bash
git clone https://github.com/AbdullahBakir97/Mini-RAG.git
cd Mini-RAG

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .

cp .env.example .env             # Windows: copy .env.example .env
docker compose up -d db          # PostgreSQL 16 with pgvector on localhost:5432
alembic upgrade head             # create or update the database tables
uvicorn mini_rag.main:app --reload
```

Open **http://localhost:8000** for the interactive API docs. Run commands from the repository root, where `.env` is read. Indexing, search and answers need `OPENAI_API_KEY` in `.env`, or OpenAI-compatible servers in `EMBEDDING_BASE_URL` and `LLM_BASE_URL`.

### Try it

```bash
curl -F "file=@notes.txt;type=text/plain" http://localhost:8000/api/v1/data/upload/demo
# {"signal": "file_uploaded_successfully", "file_id": "a16q20nzrtvj_notes.txt"}

curl -X POST http://localhost:8000/api/v1/data/process/demo \
  -H "Content-Type: application/json" -d '{"file_id": "a16q20nzrtvj_notes.txt"}'
curl -X POST http://localhost:8000/api/v1/index/demo

curl -X POST http://localhost:8000/api/v1/search/demo \
  -H "Content-Type: application/json" -d '{"query": "What do my notes say about overlap?"}'
curl -X POST http://localhost:8000/api/v1/ask/demo \
  -H "Content-Type: application/json" -d '{"question": "What do my notes say about overlap?"}'
```

## Documentation

| | |
|---|---|
| [Configuration](docs/configuration.md) | Every setting, with defaults |
| [API](docs/api.md) | Endpoints, requests, responses and errors |
| [Architecture](docs/architecture.md) | Layers, rules and extension points |
| [Development](docs/development.md) | Tests, migrations and workflow |
| [Roadmap](docs/roadmap.md) | Completed and planned work |

## Tech stack

FastAPI · PostgreSQL 16 with pgvector · SQLAlchemy 2 (async) and Alembic · OpenAI-compatible embeddings and chat models · pypdf · pytest and ruff in GitHub Actions

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](.github/CONTRIBUTING.md) and the [Code of Conduct](.github/CODE_OF_CONDUCT.md). To report a security issue, follow [SECURITY.md](.github/SECURITY.md).

## Author

**Abdullah Bakir** — [@AbdullahBakir97](https://github.com/AbdullahBakir97)

Full-Stack Developer based in Germany - Python · Django · Vue · Nuxt.

## License

Released under the [MIT License](./LICENSE).
