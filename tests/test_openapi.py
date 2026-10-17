import pytest


@pytest.fixture
def schema(client):
    return client.get("/openapi.json").json()


def response_schema(schema, path, status):
    content = schema["paths"][path]["post"]["responses"][status]["content"]
    return content["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]


def test_app_metadata_comes_from_settings(schema):
    assert schema["info"] == {"title": "mini-RAG-test", "version": "0.0.1"}


def test_success_responses_are_documented(schema):
    assert response_schema(schema, "/api/v1/data/upload/{project_id}", "200") == "UploadResponse"
    assert response_schema(schema, "/api/v1/data/process/{project_id}", "200") == "ProcessResponse"


def test_error_responses_are_documented_with_their_signals(schema):
    upload = schema["paths"]["/api/v1/data/upload/{project_id}"]["post"]["responses"]
    process = schema["paths"]["/api/v1/data/process/{project_id}"]["post"]["responses"]

    assert response_schema(schema, "/api/v1/data/process/{project_id}", "404") == "ErrorResponse"
    assert "file_not_found" in process["404"]["description"]
    assert "file_size_exceeded" in str(upload) and "file_type_not_supported" in str(upload)
    assert "processing_failed" in str(process) and "file_has_no_text" in str(process)


def test_project_id_rules_are_documented(schema):
    params = schema["paths"]["/api/v1/data/upload/{project_id}"]["post"]["parameters"]
    [project_id] = [p for p in params if p["name"] == "project_id"]

    assert project_id["schema"]["pattern"] == "^[A-Za-z0-9_-]{1,64}$"


def test_index_endpoint_is_documented(schema):
    responses = schema["paths"]["/api/v1/index/{project_id}"]["post"]["responses"]

    assert response_schema(schema, "/api/v1/index/{project_id}", "200") == "IndexResponse"
    assert "project_not_found" in responses["404"]["description"]
    assert "file_not_found" in responses["404"]["description"]
    assert "embedding_failed" in responses["502"]["description"]
    assert "embedding_not_configured" in responses["503"]["description"]


def test_search_endpoint_is_documented(schema):
    responses = schema["paths"]["/api/v1/search/{project_id}"]["post"]["responses"]

    assert response_schema(schema, "/api/v1/search/{project_id}", "200") == "SearchResponse"
    assert "project_not_found" in responses["404"]["description"]
    assert "embedding_failed" in responses["502"]["description"]


def test_ask_endpoint_is_documented(schema):
    responses = schema["paths"]["/api/v1/ask/{project_id}"]["post"]["responses"]

    assert response_schema(schema, "/api/v1/ask/{project_id}", "200") == "AskResponse"
    assert "project_not_found" in responses["404"]["description"]
    assert "embedding_failed" in responses["502"]["description"]
    assert "llm_failed" in responses["502"]["description"]
    assert "embedding_not_configured" in responses["503"]["description"]
    assert "llm_not_configured" in responses["503"]["description"]


def test_ask_stream_endpoint_is_documented(schema):
    responses = schema["paths"]["/api/v1/ask/{project_id}/stream"]["post"]["responses"]

    assert "text/event-stream" in responses["200"]["content"]
    assert "project_not_found" in responses["404"]["description"]
    assert "llm_not_configured" in responses["503"]["description"]
