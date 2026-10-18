import pytest

from mini_rag.api.dependencies import get_embedder, get_llm

from .fakes import FakeEmbedder, FakeLLM

# One chunk per paragraph at chunk_size 60.
GUIDE = "\n\n".join([
    "Upload a file first, as text or PDF.",
    "Processing splits each file into chunks.",
    "Indexing stores an embedding vector per chunk.",
    "Search compares the question with the chunks.",
])


@pytest.fixture
def embedder(client):
    fake = FakeEmbedder()
    client.app.dependency_overrides[get_embedder] = lambda: fake
    return fake


@pytest.fixture
def llm(client):
    fake = FakeLLM("Each chunk gets an embedding vector [1].")
    client.app.dependency_overrides[get_llm] = lambda: fake
    return fake


def upload_process_and_index(client, project="demo", name="guide.txt", text=GUIDE,
                             content_type="text/plain"):
    response = client.post(f"/api/v1/data/upload/{project}",
                           files={"file": (name, text, content_type)})
    file_id = response.json()["file_id"]
    response = client.post(f"/api/v1/data/process/{project}",
                           json={"file_id": file_id, "chunk_size": 60, "overlap_size": 0})
    assert response.status_code == 200
    assert client.post(f"/api/v1/index/{project}").status_code == 200
    return file_id


def ask(client, project="demo", **body):
    return client.post(f"/api/v1/ask/{project}", json=body)


def test_answers_with_citations(client, embedder, llm):
    file_id = upload_process_and_index(client)

    response = ask(client, question="Where is the embedding vector stored?", min_score=0.2)

    assert response.status_code == 200
    body = response.json()
    score = body["citations"][0].pop("score")
    assert body == {
        "signal": "answer_success",
        "answer": "Each chunk gets an embedding vector [1].",
        "citations": [{"number": 1, "file_id": file_id, "chunk_index": 2, "page": None,
                       "text": "Indexing stores an embedding vector per chunk."}],
        "prompt_version": "answer-v1",
    }
    assert 0.2 <= score <= 1
    # The model saw the question and only the matching chunk, as data.
    [[system, user]] = llm.calls
    assert "only as data" in system.content
    assert "Indexing stores an embedding vector per chunk." in user.content
    assert "Upload a file first" not in user.content
    assert "<question>\nWhere is the embedding vector stored?\n</question>" in user.content


def test_pdf_citations_carry_the_page(client, embedder, llm, make_pdf):
    pdf = make_pdf(["Nothing to see here.", "Each chunk gets an embedding vector."])
    upload_process_and_index(client, name="guide.pdf", text=pdf, content_type="application/pdf")

    citations = ask(client, question="embedding vector", min_score=0.2).json()["citations"]

    assert [citation["page"] for citation in citations] == [2]


def test_no_matching_chunk_means_no_answer(client, embedder, llm):
    upload_process_and_index(client)

    response = ask(client, question="Where is Paris?")

    assert response.status_code == 200
    assert response.json() == {"signal": "no_answer", "answer": None, "citations": [],
                               "prompt_version": "answer-v1"}
    assert llm.calls == []


def test_model_finding_no_answer_means_no_answer(client, embedder, llm):
    upload_process_and_index(client)
    llm.reply = "NO_ANSWER"

    response = ask(client, question="Why is the embedding vector stored?", min_score=0.2)

    assert response.json()["signal"] == "no_answer"
    assert len(llm.calls) == 1


def test_unindexed_project_has_no_answer(client, embedder, llm):
    client.post("/api/v1/data/upload/demo", files={"file": ("a.txt", GUIDE, "text/plain")})

    assert ask(client, question="embedding vector").json()["signal"] == "no_answer"


def test_unknown_project(client, embedder, llm):
    response = ask(client, project="missing", question="anything")

    assert (response.status_code, response.json()) == (404, {"signal": "project_not_found"})


@pytest.mark.parametrize("body", [
    {"question": ""},
    {"question": "   "},
    {"question": "x" * 2001},
    {"question": "ok", "top_k": 0},
    {"question": "ok", "top_k": 21},
    {"question": "ok", "min_score": -1.5},
    {"query": "ok"},
])
def test_validates_the_request(client, embedder, llm, body):
    assert ask(client, **body).status_code == 422


def test_reports_model_failures(client, embedder):
    client.app.dependency_overrides[get_llm] = lambda: FakeLLM(fail=True)
    upload_process_and_index(client)

    response = ask(client, question="embedding vector", min_score=0.2)

    assert (response.status_code, response.json()) == (502, {"signal": "llm_failed"})


def test_without_llm_configuration(client, embedder):
    client.app.state.llm = None

    response = ask(client, question="anything")

    assert (response.status_code, response.json()) == (503, {"signal": "llm_not_configured"})


def test_without_embedding_configuration(client, llm):
    client.app.state.embedder = None

    response = ask(client, question="anything")

    assert (response.status_code, response.json()) == (503, {"signal": "embedding_not_configured"})
