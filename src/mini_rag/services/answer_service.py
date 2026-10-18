from collections.abc import AsyncIterator
from dataclasses import dataclass

from mini_rag.domain.llm import LLM
from mini_rag.domain.models import ScoredChunk
from mini_rag.prompts.answer import ANSWER_PROMPT, AnswerPrompt
from mini_rag.services.search_service import SearchService


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
    """``text`` is None when the project's documents do not answer the question."""

    text: str | None
    citations: list[Citation]
    prompt_version: str


class AnswerService:
    """Answers a question from a project's documents, citing its sources."""

    def __init__(self, search: SearchService, llm: LLM, min_score: float,
                 prompt: AnswerPrompt = ANSWER_PROMPT):
        self.search = search
        self.llm = llm
        self.min_score = min_score
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
            return self._no_answer()
        reply = await self.llm.complete(self.prompt.messages(question, sources))
        return self._finish(reply, sources)

    async def retrieve(self, project_name: str, question: str, top_k: int,
                       min_score: float | None = None) -> list[ScoredChunk]:
        """The chunks an answer may use: the best matches scoring at least ``min_score``."""
        if min_score is None:
            min_score = self.min_score
        return await self.search.search(project_name, question, top_k=top_k,
                                        min_score=min_score)

    async def stream(self, question: str,
                     sources: list[ScoredChunk]) -> AsyncIterator[AnswerDelta | Answer]:
        """Like ``ask``, for sources from ``retrieve``: the text as it is written, then the Answer.

        Text is held back while the reply may still be the model's no-answer
        reply, so a client never shows it; that reply yields no deltas.
        """
        if not sources:
            yield self._no_answer()
            return
        reply = ""
        holding = True
        async for piece in self.llm.stream(self.prompt.messages(question, sources)):
            reply += piece
            if holding and self.prompt.could_be_no_answer(reply):
                continue
            yield AnswerDelta(reply if holding else piece)
            holding = False
        yield self._finish(reply, sources)

    def _finish(self, reply: str, sources: list[ScoredChunk]) -> Answer:
        if self.prompt.is_no_answer(reply):
            return self._no_answer()
        # The model may cite numbers that were never given; those are dropped.
        citations = [Citation(number=number, source=sources[number - 1])
                     for number in self.prompt.cited_numbers(reply)
                     if 1 <= number <= len(sources)]
        return Answer(text=reply.strip(), citations=citations,
                      prompt_version=self.prompt.version)

    def _no_answer(self) -> Answer:
        return Answer(text=None, citations=[], prompt_version=self.prompt.version)
