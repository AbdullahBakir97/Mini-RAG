# Configuration

Settings are read from `.env` in the repository root (copy it from `.env.example`) or from environment variables.

| Variable | Example | Description |
|---|---|---|
| `APP_NAME` | `"mini-RAG"` | Name returned by the welcome endpoint |
| `APP_VERSION` | `"0.1"` | Version returned by the welcome endpoint |
| `OPENAI_API_KEY` | `""` | API key for OpenAI, used for embeddings and answers. Leave empty when both use local servers set in `EMBEDDING_BASE_URL` and `LLM_BASE_URL` |
| `DATABASE_URL` | `"postgresql+asyncpg://mini_rag:mini_rag@localhost:5432/mini_rag"` | PostgreSQL connection (must use the `postgresql+asyncpg://` driver); the default matches `compose.yaml` |
| `EMBEDDING_BASE_URL` | `""` | OpenAI-compatible server for embeddings, e.g. `"http://localhost:11434/v1"` for Ollama; empty means OpenAI |
| `EMBEDDING_MODEL` | `"text-embedding-3-small"` | Embedding model name |
| `EMBEDDING_DIMENSIONS` | `1536` | Length of each vector. Must match the database column (1536); the app refuses to start otherwise |
| `EMBEDDING_BATCH_SIZE` | `64` | Chunks sent per embedding request while indexing |
| `LLM_BASE_URL` | `""` | OpenAI-compatible server for answers, e.g. `"http://localhost:11434/v1"` for Ollama; empty means OpenAI. Independent of `EMBEDDING_BASE_URL` |
| `LLM_MODEL` | `"gpt-4.1-mini"` | Chat model that writes answers |
| `LLM_MAX_TOKENS` | `1024` | Most tokens the model may write per answer |
| `LLM_TEMPERATURE` | `""` | Sampling temperature from 0 to 2; empty uses the model's default (reasoning models accept no other) |
| `LOG_LEVEL` | `"INFO"` | Level for the app's own logs: `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL` (libraries log warnings and above) |
| `FILES_DIR` | `"assets/files"` | Folder where uploaded files are stored, one subfolder per project |
| `FILE_ALLOWED_TYPES` | `["text/plain", "application/pdf"]` | MIME types accepted for upload |
| `FILE_MAX_SIZE` | `10` | Maximum upload size in MB |
| `FILE_DEFAULT_CHUNK_SIZE` | `512000` | Bytes read per chunk while saving an upload |

Settings are validated when the app starts: a missing or invalid value stops it with a message naming the setting. Values are never printed in these messages, so secrets such as `OPENAI_API_KEY` or the database password cannot end up in logs.

`.env` holds secrets and is git-ignored; never commit it. The values in `.env.example` are for local development only.
