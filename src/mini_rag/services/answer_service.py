from collections.abc import AsyncIterator
from dataclasses import dataclass

from mini_rag.domain.llm import LLM, TokenPrices, TokenUsage
from mini_rag.domain.models import AnswerRecord, ScoredChunk
from mini_rag.domain.repositories import UnitOfWork
from mini_rag.prompts.answer import ANSWER_PROMPT, AnswerPrompt
from mini_rag.services.search_service import SearchService

# The usage of an answer for which the model was not called.
NOT_CALLED = TokenUsage(input_tokens=0, output_tokens=0)


@dataclass(frozen=True)
class Citation:
    """A source the answer cites; ``number`` is its [n] marker in the answer."""

    number: int
    source: ScoredChunk


@dataclass(frozen=True)
class AnswerDelta:
    """The next piece of an answer's text, while the model is still writing it."""

    text: str


@dataclass(frozen=True)
class Answer:
    """``text`` is None when the project's documents do not answer the question.

    ``usage`` is None when the provider did not report it; ``cost_usd`` is
    None when the usage or the model's prices are unknown.
    """

    text: str | None
    citations: list[Citation]
    prompt_version: str
    usage: TokenUsage | None
    cost_usd: float | None


class AnswerService:
    """Answers a question from a project's documents, citing its sources.

    Every answer is recorded with its token usage and cost; the question
    and the answer text are not.
    """

    def __init__(self, search: SearchService, llm: LLM, uow: UnitOfWork, min_score: float,
                 prices: TokenPrices | None = None, prompt: AnswerPrompt = ANSWER_PROMPT):
        self.search = search
        self.llm = llm
        self.uow = uow
        self.min_score = min_score
        self.prices = prices
        self.prompt = prompt

    async def ask(self, project_name: str, question: str, top_k: int,
                  min_score: float | None = None) -> Answer:
        """Retrieve the best matching chunks and have the model answer from them.

        Only chunks scoring at least ``min_score`` (default: the service's)
        are used. Without any, or when the model finds no answer in them,
        the answer has no text, and without any the model is not called.
        """
        sources = await self.retrieve(project_name, question, top_k, min_score)
        if not sources:
            answer = self._no_answer(NOT_CALLED)
        else:
            completion = await self.llm.complete(self.prompt.messages(question, sources))
            answer = self._finish(completion.text, sources, completion.usage)
        await self._record(project_name, answer, model_called=bool(sources), streamed=False)
        return answer

    async def retrieve(self, project_name: str, question: str, top_k: int,
                       min_score: float | None = None) -> list[ScoredChunk]:
        """The chunks an answer may use: the best matches scoring at least ``min_score``."""
        if min_score is None:
            min_score = self.min_score
        return await self.search.search(project_name, question, top_k=top_k,
                                        min_score=min_score)

    async def stream(self, project_name: str, question: str,
                     sources: list[ScoredChunk]) -> AsyncIterator[AnswerDelta | Answer]:
        """Like ``ask``, for sources from ``retrieve``: the text as it is written, then the Answer.

        Text is held back while the reply may still be the model's no-answer
        reply, so a client never shows it; that reply yields no deltas. The
        answer is recorded only when the stream completes.
        """
        if not sources:
            answer = self._no_answer(NOT_CALLED)
        else:
            reply = ""
            usage = None
            holding = True
            async for piece in self.llm.stream(self.prompt.messages(question, sources)):
                if isinstance(piece, TokenUsage):
                    usage = piece
                    continue
                reply += piece
                if holding and self.prompt.could_be_no_answer(reply):
                    continue
                yield AnswerDelta(reply if holding else piece)
                holding = False
            answer = self._finish(reply, sources, usage)
        await self._record(project_name, answer, model_called=bool(sources), streamed=True)
        yield answer

    def _finish(self, reply: str, sources: list[ScoredChunk],
                usage: TokenUsage | None) -> Answer:
        if self.prompt.is_no_answer(reply):
            return self._no_answer(usage)
        # The model may cite numbers that were never given; those are dropped.
        citations = [Citation(number=number, source=sources[number - 1])
                     for number in self.prompt.cited_numbers(reply)
                     if 1 <= number <= len(sources)]
        return Answer(text=reply.strip(), citations=citations, prompt_version=self.prompt.version,
                      usage=usage, cost_usd=self._cost(usage))

    def _no_answer(self, usage: TokenUsage | None) -> Answer:
        return Answer(text=None, citations=[], prompt_version=self.prompt.version,
                      usage=usage, cost_usd=self._cost(usage))

    def _cost(self, usage: TokenUsage | None) -> float | None:
        if usage == NOT_CALLED:
            return 0.0
        if usage is None or self.prices is None:
            return None
        return self.prices.cost(usage)

    async def _record(self, project_name: str, answer: Answer, *, model_called: bool,
                      streamed: bool) -> None:
        # Retrieval found the project, so it exists.
        project = await self.uow.projects.get_by_name(project_name)
        await self.uow.answers.add(AnswerRecord(
            project_id=project.id, prompt_version=answer.prompt_version,
            model=self.llm.model if model_called else None, streamed=streamed,
            answered=answer.text is not None,
            input_tokens=answer.usage.input_tokens if answer.usage else None,
            output_tokens=answer.usage.output_tokens if answer.usage else None,
            cost_usd=answer.cost_usd))
        await self.uow.commit()
