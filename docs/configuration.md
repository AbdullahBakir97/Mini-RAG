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
| `LLM_STREAM_USAGE` | `true` | Ask for token usage at the end of streamed answers (`stream_options`); set to `false` if your server rejects that option |
| `LLM_INPUT_PRICE_PER_MILLION` | `""` | US dollars per million prompt tokens, e.g. `0.4`; `0` for a free tier. Empty: costs are unknown (`null`) |
| `LLM_OUTPUT_PRICE_PER_MILLION` | `""` | US dollars per million tokens the model writes, e.g. `1.6`. Both prices are needed for a cost |
| `ANSWER_MIN_SCORE` | `0.3` | Chunks scoring below this cosine similarity are not used for answers; with none left the answer is `no_answer`. The default suits `text-embedding-3-small`; other models may need another value |
| `LOG_LEVEL` | `"INFO"` | Level for the app's own logs: `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL` (libraries log warnings and above) |
| `FILES_DIR` | `"assets/files"` | Folder where uploaded files are stored, one subfolder per project |
| `FILE_ALLOWED_TYPES` | `["text/plain", "application/pdf"]` | MIME types accepted for upload |
| `FILE_MAX_SIZE` | `10` | Maximum upload size in MB |
| `FILE_DEFAULT_CHUNK_SIZE` | `512000` | Bytes read per chunk while saving an upload |

## Model providers

Embeddings and answers each talk to an OpenAI-compatible API, so the same settings work with several providers. Leave `EMBEDDING_DIMENSIONS` at `1536` unless you also change the database column (see [Development](development.md#database-migrations)).

**OpenAI** (the default): set `OPENAI_API_KEY` and leave both base URLs empty.

**GitHub Models**: free within GitHub's rate limits. Create a fine-grained personal access token with the **Models** account permission (read-only), then:

```env
OPENAI_API_KEY="<your GitHub token>"
EMBEDDING_BASE_URL="https://models.github.ai/inference"
EMBEDDING_MODEL="openai/text-embedding-3-small"
LLM_BASE_URL="https://models.github.ai/inference"
LLM_MODEL="openai/gpt-4.1-mini"
```

Check the token before starting the app; a working one returns JSON with a `choices` list:

```bash
curl -s https://models.github.ai/inference/chat/completions \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4.1-mini","messages":[{"role":"user","content":"Reply with: pong"}],"max_tokens":5}'
```

Prices change, so they are not built in: copy them from your provider's pricing page. Within GitHub Models' free limits, set both to `0`.

**Ollama** (local, no key): set `EMBEDDING_BASE_URL` and `LLM_BASE_URL` to `"http://localhost:11434/v1"` and the model settings to models you pulled. Ollama's embedding models usually produce other vector sizes, such as 768, so change the column and `EMBEDDING_DIMENSIONS` to match first (see [Development](development.md#database-migrations)).

## Validation

Settings are validated when the app starts: a missing or invalid value stops it with a message naming the setting. Values are never printed in these messages, so secrets such as `OPENAI_API_KEY` or the database password cannot end up in logs.

`.env` holds secrets and is git-ignored; never commit it. The values in `.env.example` are for local development only.
