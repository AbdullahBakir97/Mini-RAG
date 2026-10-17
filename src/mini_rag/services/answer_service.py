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
        if min_score is None:
            min_score = self.min_score
        sources = await self.search.search(project_name, question, top_k=top_k,
                                           min_score=min_score)
        if not sources:
            return self._no_answer()

        reply = await self.llm.complete(self.prompt.messages(question, sources))
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
