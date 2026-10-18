import pytest

from mini_rag.core.errors import EmbeddingFailed, LLMFailed, ProjectNotFound
from mini_rag.domain.models import Chunk
from mini_rag.services.answer_service import Answer, AnswerDelta, AnswerService
from mini_rag.services.indexing_service import IndexingService
from mini_rag.services.search_service import SearchService

from .fakes import FakeEmbedder, FakeLLM, FakeUnitOfWork

pytestmark = pytest.mark.anyio

TEXTS = ["Cats purr and sleep all day.",
         "Postgres stores vectors with pgvector.",
         "Dogs bark at cats."]


@pytest.fixture
async def uow():
    uow = FakeUnitOfWork()
    project = await uow.projects.get_or_create("p1")
    record = await uow.files.add(project_id=project.id, key="a_notes.txt", original_name="notes.txt",
                                 content_type="text/plain", size_bytes=0)
    await uow.chunks.replace_for_file(record, [Chunk(i, text, {"source": "a_notes.txt"})
                                               for i, text in enumerate(TEXTS)])
    await IndexingService(uow, FakeEmbedder(), batch_size=10).index("p1")
    return uow


def service(uow, llm, min_score=0.2, embedder=None):
    return AnswerService(SearchService(uow, embedder or FakeEmbedder()), llm, min_score=min_score)


async def test_answers_from_the_matching_chunks_with_citations(uow):
    llm = FakeLLM("Dogs bark at cats [1], which purr [2].\n")

    answer = await service(uow, llm).ask("p1", "cats?", top_k=5)

    assert answer.text == "Dogs bark at cats [1], which purr [2]."
    assert answer.prompt_version == "answer-v1"
    # Only the two chunks about cats pass min_score, best first.
    [[_, user]] = llm.calls
    assert user.content.count("<source ") == 2
    assert [(c.number, c.source.chunk.text, c.source.file_key) for c in answer.citations] == [
        (1, TEXTS[2], "a_notes.txt"), (2, TEXTS[0], "a_notes.txt")]
    assert answer.citations[0].source.score > answer.citations[1].source.score


async def test_citations_follow_the_answer_and_skip_unknown_numbers(uow):
    llm = FakeLLM("Dogs bark [2]. Cats purr [1][2]. Also [7].")

    answer = await service(uow, llm).ask("p1", "cats?", top_k=5)

    assert [citation.number for citation in answer.citations] == [2, 1]


async def test_top_k_limits_the_sources(uow):
    llm = FakeLLM("Cats purr [1].")

    await service(uow, llm).ask("p1", "cats?", top_k=1)

    assert llm.calls[0][1].content.count("<source ") == 1


async def test_no_matching_chunk_means_no_answer_without_calling_the_model(uow):
    llm = FakeLLM()

    answer = await service(uow, llm).ask("p1", "Where is Paris?", top_k=5)

    assert (answer.text, answer.citations) == (None, [])
    assert llm.calls == []


async def test_request_min_score_overrides_the_default(uow):
    llm = FakeLLM("Something [1].")

    answer = await service(uow, llm, min_score=0.99).ask("p1", "Where is Paris?", top_k=5,
                                                          min_score=-1)

    assert answer.text == "Something [1]."
    assert llm.calls[0][1].content.count("<source ") == 3


async def test_the_model_can_say_the_sources_do_not_answer(uow):
    answer = await service(uow, FakeLLM("NO_ANSWER")).ask("p1", "Why do cats purr?", top_k=5)

    assert (answer.text, answer.citations, answer.prompt_version) == (None, [], "answer-v1")


async def test_project_without_indexed_chunks_has_no_answer():
    uow = FakeUnitOfWork()
    await uow.projects.get_or_create("empty")
    llm = FakeLLM()

    answer = await service(uow, llm).ask("empty", "Anything?", top_k=5)

    assert answer.text is None and llm.calls == []


async def test_unknown_project(uow):
    with pytest.raises(ProjectNotFound):
        await service(uow, FakeLLM()).ask("missing", "cats", top_k=5)


@pytest.mark.parametrize(("llm", "embedder", "error"), [
    (FakeLLM(fail=True), FakeEmbedder(), LLMFailed),
    (FakeLLM(), FakeEmbedder(fail_on_call=1), EmbeddingFailed),
], ids=["llm", "embedder"])
async def test_provider_failures_propagate(uow, llm, embedder, error):
    with pytest.raises(error):
        await service(uow, llm, embedder=embedder).ask("p1", "cats?", top_k=5)


async def stream(answers, question, top_k=5):
    sources = await answers.retrieve("p1", question, top_k=top_k)
    return [event async for event in answers.stream(question, sources)]


async def test_stream_sends_the_text_as_written_then_the_answer(uow):
    reply = "Dogs bark at cats [1], which purr [2]."
    llm = FakeLLM(reply, piece_size=5)

    events = await stream(service(uow, llm), "cats?")

    *deltas, answer = events
    assert all(isinstance(delta, AnswerDelta) for delta in deltas) and len(deltas) > 1
    assert "".join(delta.text for delta in deltas) == reply
    assert isinstance(answer, Answer) and answer.text == reply
    assert [citation.number for citation in answer.citations] == [1, 2]


async def test_stream_holds_back_a_no_answer_reply(uow):
    events = await stream(service(uow, FakeLLM("NO_ANSWER", piece_size=2)), "cats?")

    assert events == [Answer(text=None, citations=[], prompt_version="answer-v1")]


async def test_stream_releases_text_once_it_cannot_be_no_answer(uow):
    events = await stream(service(uow, FakeLLM("NOTE: cats purr [1].", piece_size=2)), "cats?")

    # "NO" is held back; with "NOTE" it is clearly an answer, sent as one delta.
    assert events[0] == AnswerDelta("NOTE")
    assert "".join(e.text for e in events[:-1]) == "NOTE: cats purr [1]."


async def test_stream_without_sources_has_no_answer_and_skips_the_model(uow):
    llm = FakeLLM()

    events = await stream(service(uow, llm), "Where is Paris?")

    assert events == [Answer(text=None, citations=[], prompt_version="answer-v1")]
    assert llm.calls == []


async def test_stream_failure_after_some_text_propagates(uow):
    answers = service(uow, FakeLLM("Cats purr all day [1].", piece_size=4, fail_after=2))
    sources = await answers.retrieve("p1", "cats?", top_k=5)
    received = []

    with pytest.raises(LLMFailed):
        async for event in answers.stream("cats?", sources):
            received.append(event)
    assert received == [AnswerDelta("Cats"), AnswerDelta(" pur")]
