# API

All endpoints are under `/api/v1` (only `/` sits outside it, redirecting to `/docs`). The interactive reference, generated from the code, is at `/docs` on a running server (and the schema at `/openapi.json`).

Every error response has the form `{"signal": "<name>"}` with a matching HTTP status; validation errors (`422`) list the fields that failed.

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Redirects to `/docs` |
| `GET` | `/api/v1/` | Welcome message with app name and version |
| `GET` | `/api/v1/health` | `200` `{"status": "ok", "database": "ok"}`, or `503` when the database is unreachable |
| `POST` | `/api/v1/data/upload/{project_id}` | Upload a file into a project |
| `POST` | `/api/v1/data/process/{project_id}` | Split an uploaded file into chunks and store them |
| `POST` | `/api/v1/index/{project_id}` | Embed a project's chunks so they can be searched |
| `POST` | `/api/v1/search/{project_id}` | Find the chunks that best match a question |
| `POST` | `/api/v1/ask/{project_id}` | Answer a question from the project's documents, with citations |
| `GET` | `/api/v1/projects/{project_id}` | Project details with file, chunk and index counts |
| `GET` | `/api/v1/projects/{project_id}/files` | List a project's files (paged) |
| `GET` | `/api/v1/projects/{project_id}/files/{file_id}/chunks` | List a file's chunks (paged) |

## Upload a file

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

## Process a file into chunks

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

## Read projects, files and chunks

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

## Index chunks for search

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

## Search

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

## Ask a question

Asking searches the project like the search endpoint, then has a language model answer from the best matching chunks only, citing each source with a `[n]` marker. It needs a language model as well as embeddings: `OPENAI_API_KEY`, or an OpenAI-compatible server in `LLM_BASE_URL`.

```bash
curl -X POST http://localhost:8000/api/v1/ask/demo1 \
  -H "Content-Type: application/json" \
  -d '{"question": "How does the overlap work?"}'
```

```json
{
  "signal": "answer_success",
  "answer": "Each chunk begins with up to overlap_size characters of the text before it [1], starting at a word boundary [2].",
  "citations": [
    {"number": 1, "file_id": "a16q20nzrtvj_notes.txt", "chunk_index": 2, "page": 1, "score": 0.83, "text": "..."},
    {"number": 2, "file_id": "a16q20nzrtvj_notes.txt", "chunk_index": 5, "page": 2, "score": 0.71, "text": "..."}
  ],
  "prompt_version": "answer-v1"
}
```

`citations` lists the sources the answer cites, in the order they are first cited; `number` matches the `[n]` marker in `answer`. `page` is set for PDFs and `null` otherwise. `prompt_version` names the prompt that produced the answer, so answers can be compared when prompts change.

When the documents do not answer the question, the response is `200` with signal `no_answer`, `answer` `null` and no citations, rather than a guess:

```json
{"signal": "no_answer", "answer": null, "citations": [], "prompt_version": "answer-v1"}
```

That happens when no indexed chunk scores at least `min_score` (the model is then not called at all), or when the model finds no answer in the chunks it is given. Document text is passed to the model as quoted data, so instructions hidden in a document are not followed; see [Prompts](architecture.md#prompts).

| Field | Default | Rules |
|---|---|---|
| `question` | required | 1–2000 characters, not blank |
| `top_k` | `5` | 1–20; most chunks the answer may use |
| `min_score` | `ANSWER_MIN_SCORE` (`0.3`) | -1 to 1; chunks scoring below it are not used |

| Case | Status | Response |
|---|---|---|
| Answered | `200` | `{"signal": "answer_success", ...}` |
| The documents do not answer the question | `200` | `{"signal": "no_answer", "answer": null, ...}` |
| No such project | `404` | `{"signal": "project_not_found"}` |
| Invalid request | `422` | Validation error details |
| The embedding provider or the language model failed | `502` | `{"signal": "embedding_failed"}` / `{"signal": "llm_failed"}` |
| Embeddings or the language model are not configured | `503` | `{"signal": "embedding_not_configured"}` / `{"signal": "llm_not_configured"}` |
