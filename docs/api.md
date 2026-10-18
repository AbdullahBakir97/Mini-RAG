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
| `POST` | `/api/v1/ask/{project_id}/stream` | The same answer, streamed as it is written (Server-Sent Events) |
| `GET` | `/api/v1/projects` | List projects in name order (paged) |
| `GET` | `/api/v1/projects/{project_id}` | Project details with file, chunk and index counts |
| `GET` | `/api/v1/projects/{project_id}/usage` | Token usage and cost of the project's answers |
| `GET` | `/api/v1/projects/{project_id}/files` | List a project's files (paged) |
| `GET` | `/api/v1/projects/{project_id}/files/{file_id}/chunks` | List a file's chunks (paged) |
| `POST` | `/api/v1/projects/{project_id}/conversations` | Start a conversation |
| `GET` | `/api/v1/projects/{project_id}/conversations` | List conversations, most recent first (paged) |
| `GET` | `/api/v1/projects/{project_id}/conversations/{conversation_id}` | A conversation with its questions and answers |
| `DELETE` | `/api/v1/projects/{project_id}/conversations/{conversation_id}` | Delete a conversation and its messages |
| `PUT` | `/api/v1/projects/{project_id}/conversations/{conversation_id}/messages/{message_id}/feedback` | Rate an answer thumbs up or down |
| `DELETE` | `/api/v1/projects/{project_id}/conversations/{conversation_id}/messages/{message_id}/feedback` | Remove an answer's rating |
| `GET` | `/api/v1/projects/{project_id}/feedback` | Rated answers, most recently rated first (paged) |

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
curl http://localhost:8000/api/v1/projects
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

Lists are paged with `offset` (default `0`) and `limit` (default `20`, at most `100`); `total` is the number of items overall. Projects are listed by name, with only `name` and `created_at`; a project exists once a file was uploaded into it. Files are listed in upload order, chunks by `chunk_index`. An unknown project returns `404` `{"signal": "project_not_found"}`, an unknown file `404` `{"signal": "file_not_found"}`.

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

Results are the project's indexed chunks that best match the query, best first. With `SEARCH_MODE=hybrid` (the default), a chunk ranks higher both for being close in meaning and for containing the query's words, so exact terms such as names, codes and numbers are found even when the embedding misses them; with `vector`, only meaning counts. Either way `score` is the cosine similarity between the query and the chunk (1 is the best match), which `min_score` and `ANSWER_MIN_SCORE` are compared with. Chunks that are not indexed yet are not found; a project without any returns an empty list.

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
  "prompt_version": "answer-v1",
  "usage": {"input_tokens": 1180, "output_tokens": 41, "cost_usd": 0.0005376}
}
```

`citations` lists the sources the answer cites, in the order they are first cited; `number` matches the `[n]` marker in `answer`. `page` is set for PDFs and `null` otherwise. `prompt_version` names the prompt that produced the answer, so answers can be compared when prompts change.

When the documents do not answer the question, the response is `200` with signal `no_answer`, `answer` `null` and no citations, rather than a guess:

```json
{"signal": "no_answer", "answer": null, "citations": [], "prompt_version": "answer-v1",
 "usage": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}}
```

That happens when no indexed chunk scores at least `min_score` (the model is then not called at all), or when the model finds no answer in the chunks it is given. Document text is passed to the model as quoted data, so instructions hidden in a document are not followed; see [Prompts](architecture.md#prompts).

| Field | Default | Rules |
|---|---|---|
| `question` | required | 1–2000 characters, not blank |
| `top_k` | `5` | 1–20; most chunks the answer may use |
| `min_score` | `ANSWER_MIN_SCORE` (`0.3`) | -1 to 1; chunks scoring below it are not used |
| `conversation_id` | none | A conversation of this project (see [Conversations](#conversations)); omit to ask on its own |

| Case | Status | Response |
|---|---|---|
| Answered | `200` | `{"signal": "answer_success", ...}` |
| The documents do not answer the question | `200` | `{"signal": "no_answer", "answer": null, ...}` |
| No such project | `404` | `{"signal": "project_not_found"}` |
| No such conversation in this project | `404` | `{"signal": "conversation_not_found"}` |
| Invalid request | `422` | Validation error details |
| The embedding provider or the language model failed | `502` | `{"signal": "embedding_failed"}` / `{"signal": "llm_failed"}` |
| Embeddings or the language model are not configured | `503` | `{"signal": "embedding_not_configured"}` / `{"signal": "llm_not_configured"}` |

### Streaming the answer

`POST /api/v1/ask/{project_id}/stream` takes the same request and returns the same answer as [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events), so a client can show the text while the model writes it:

```bash
curl -N -X POST http://localhost:8000/api/v1/ask/demo1/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "How does the overlap work?"}'
```

```text
event: delta
data: {"text": "Each chunk begins with"}

event: delta
data: {"text": " up to overlap_size characters [1]."}

event: answer
data: {"signal": "answer_success", "answer": "Each chunk begins with up to overlap_size characters [1].", "citations": [...], "prompt_version": "answer-v1"}
```

| Event | Data | When |
|---|---|---|
| `delta` | `{"text": "..."}` | The next piece of the answer; joined in order, they give the full text |
| `answer` | The same JSON as `POST /api/v1/ask/{project_id}` | Once, at the end, with the citations |
| `error` | `{"signal": "llm_failed"}` | The language model failed partway; the stream ends |

A `no_answer` reply sends no `delta` events, only the final `answer` event: text that might still be the model's no-answer reply is held back until it is clearly an answer. Errors found before streaming starts, such as an unknown project or a missing model configuration, are ordinary JSON responses with the status codes in the table above.

### Token usage and cost

Every answer reports what it used in `usage`: the prompt tokens the model read (`input_tokens`), the tokens it wrote (`output_tokens`) and the cost in US dollars (`cost_usd`). When no source matches, the model is not called and all three are `0`. Token counts are `null` when the provider does not report them, and `cost_usd` is `null` unless both `LLM_INPUT_PRICE_PER_MILLION` and `LLM_OUTPUT_PRICE_PER_MILLION` are set (see [Configuration](configuration.md)).

Each answer, streamed or not, is also recorded in the database: its project, model, prompt version, whether it found an answer, its tokens and its cost. This record never holds the question or the answer text; only a [conversation](#conversations) keeps those, when the question is asked in one. Answers that fail, or streams that end early, are not recorded.

```bash
curl http://localhost:8000/api/v1/projects/demo1/usage
```

```json
{"answers": 12, "answered": 9, "input_tokens": 14160, "output_tokens": 492, "cost_usd": 0.0064512, "unpriced_answers": 0}
```

`answered` counts the answers that were not `no_answer`. `cost_usd` adds up the answers with a known cost; `unpriced_answers` counts the model calls whose cost is unknown, which are left out of it. An unknown project returns `404` `{"signal": "project_not_found"}`.

### Conversations

A conversation lets a question follow on from the ones before it: "And on Fridays?" after "When do production deploys happen?". Start one, then pass its `id` as `conversation_id` when asking, streamed or not:

```bash
curl -X POST http://localhost:8000/api/v1/projects/demo1/conversations
```

```json
{"id": "6a69d3de-2e61-455f-a678-428c8c520d70", "title": null,
 "created_at": "2026-10-18T10:00:00Z", "updated_at": "2026-10-18T10:00:00Z"}
```

```bash
curl -X POST http://localhost:8000/api/v1/ask/demo1 \
  -H "Content-Type: application/json" \
  -d '{"question": "And on Fridays?", "conversation_id": "6a69d3de-2e61-455f-a678-428c8c520d70"}'
```

A follow-up cannot be searched for on its own, so the model first rewrites it into a standalone question from the last three questions and answers (prompt `condense-v1`). The sources are searched with that question, and the answer is written with the earlier questions and answers in view. The response then carries `conversation_id`, and `search_question` when the question was rewritten:

```json
{"signal": "answer_success", "answer": "Never on Fridays after noon [1].", "citations": [...],
 "prompt_version": "answer-v1", "usage": {...},
 "conversation_id": "6a69d3de-2e61-455f-a678-428c8c520d70",
 "search_question": "Do production deploys happen on Fridays?"}
```

`usage` includes the rewriting. The first question of a conversation is asked as it is, and becomes its `title` (up to 80 characters); the body of `POST .../conversations` may set one instead: `{"title": "Deploys"}`.

Each answered question is added to the conversation with its answer, citations and `search_question`; failed answers and streams that end early are not. `GET .../conversations/{conversation_id}` returns them oldest first, and `GET .../conversations` lists conversations by when they were last answered in (`offset`, `limit`). An answer that found nothing is stored with `content` `null`:

```json
{"id": "6a69d3de-...", "title": "When do production deploys happen?", "created_at": "...", "updated_at": "...",
 "messages": [
   {"id": 41, "role": "user", "content": "When do production deploys happen?", "citations": [], "prompt_version": null, "search_question": null, "created_at": "..."},
   {"id": 42, "role": "assistant", "content": "On weekdays between 9:00 and 16:00 [1].", "citations": [{"number": 1, "file_id": "...", ...}], "prompt_version": "answer-v1", "search_question": null, "created_at": "...", "feedback": null}
 ]}
```

`DELETE .../conversations/{conversation_id}` removes a conversation and its messages (`204`). A conversation belongs to one project: using its id with another project, or an id that does not exist, returns `404` `{"signal": "conversation_not_found"}`; an id that is not a UUID returns `422`.

### Feedback

An answer in a conversation can be rated thumbs up or down, with an optional comment of up to 1000 characters. The answer's `message_id` is in the response to the question, and every message of `GET .../conversations/{conversation_id}` has its `id` and its `feedback`.

```bash
curl -X PUT http://localhost:8000/api/v1/projects/demo1/conversations/6a69d3de-2e61-455f-a678-428c8c520d70/messages/42/feedback \
  -H "Content-Type: application/json" \
  -d '{"rating": "down", "comment": "It should mention Friday mornings."}'
```

The response is the message with its new `feedback`; rating again replaces it, and `DELETE` on the same path removes it (`204`). Only answers take feedback: a question's id, or an id from another conversation, returns `404` `{"signal": "message_not_found"}`.

`GET /api/v1/projects/{project_id}/feedback` lists the rated answers with the question each one answered, most recently rated first, and how many of each rating the project has; `rating=up` or `rating=down` filters, `offset` and `limit` page:

```json
{"up": 12, "down": 3, "total": 15, "offset": 0, "limit": 20,
 "items": [{"conversation_id": "6a69d3de-...", "message_id": 42,
            "question": "And on a Friday afternoon?", "answer": "Not after noon [1].",
            "citations": [...],
            "feedback": {"rating": "down", "comment": "It should mention Friday mornings.", "created_at": "..."}}]}
```

`mini-rag feedback-export` turns these into evaluation cases; see [Evaluation](evaluation.md#growing-the-test-set-from-feedback).
