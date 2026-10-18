"""Command-line tools. Run `mini-rag --help`."""

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path

from mini_rag.core.config import Settings, get_settings
from mini_rag.core.errors import AppError
from mini_rag.embeddings.factory import create_embedder
from mini_rag.evaluation.dataset import Dataset, DatasetError, load_dataset
from mini_rag.evaluation.report import (
    BaselineMismatch,
    baseline_from,
    build_report,
    compare,
)
from mini_rag.loaders.registry import default_loader_registry
from mini_rag.persistence.database import (
    EmbeddingDimensionsMismatch,
    create_engine,
    create_session_factory,
    match_embedding_dimensions,
    resize_embeddings,
    stored_embedding_dimensions,
)
from mini_rag.persistence.repositories import SqlUnitOfWork
from mini_rag.services.evaluation_service import EvaluationService
from mini_rag.services.indexing_service import IndexingService
from mini_rag.services.processing_service import ProcessingService
from mini_rag.services.search_service import SearchService
from mini_rag.services.upload_service import UploadService
from mini_rag.storage.file_storage import FileStorage

# Exit codes of `mini-rag eval`.
PASSED, REGRESSED, FAILED = 0, 1, 2


async def _resize_embeddings() -> int:
    settings = get_settings()
    wanted = settings.EMBEDDING_DIMENSIONS
    engine = create_engine(settings.DATABASE_URL)
    try:
        stored = await stored_embedding_dimensions(engine)
        if stored is None:
            print("Could not read the vector size: the database is unreachable or not "
                  "migrated yet (run `alembic upgrade head`).", file=sys.stderr)
            return 1
        if stored == wanted:
            print(f"Vectors already have {wanted} dimensions; nothing to change.")
            return 0
        cleared = await resize_embeddings(engine, wanted)
    finally:
        await engine.dispose()
    print(f"Vectors now have {wanted} dimensions instead of {stored}. {cleared} stored "
          f"vectors were cleared: index your projects again to embed them with "
          f"{settings.EMBEDDING_MODEL}.")
    return 0


async def _run_retrieval(settings: Settings, args: argparse.Namespace,
                         dataset: Dataset) -> dict:
    embedder = create_embedder(settings)
    if embedder is None:
        raise _Failure("No embedding model is configured: set OPENAI_API_KEY, or "
                       "EMBEDDING_BASE_URL for an OpenAI-compatible server such as Ollama.")
    engine = create_engine(settings.DATABASE_URL)
    try:
        if await stored_embedding_dimensions(engine) is None:
            raise _Failure("The database is unreachable or not migrated yet "
                           "(run `alembic upgrade head`).")
        await match_embedding_dimensions(engine, settings.EMBEDDING_DIMENSIONS)
        # The documents' files only live as long as the run.
        with tempfile.TemporaryDirectory(prefix="mini-rag-eval-") as files:
            async with create_session_factory(engine)() as session:
                uow = SqlUnitOfWork(session)
                storage = FileStorage(root=Path(files))
                search = SearchService(uow=uow, embedder=embedder)
                service = EvaluationService(
                    uow=uow,
                    upload=UploadService(storage=storage, uow=uow,
                                         allowed_types=settings.FILE_ALLOWED_TYPES,
                                         max_bytes=settings.max_upload_bytes,
                                         read_size=settings.FILE_DEFAULT_CHUNK_SIZE),
                    processing=ProcessingService(storage=storage,
                                                 loaders=default_loader_registry(), uow=uow),
                    indexing=IndexingService(uow=uow, embedder=embedder,
                                             batch_size=settings.EMBEDDING_BATCH_SIZE),
                    search=search)
                run = await service.run_retrieval(dataset, top_k=args.top_k,
                                                  chunk_size=args.chunk_size,
                                                  overlap_size=args.overlap_size)
    except EmbeddingDimensionsMismatch as exc:
        raise _Failure(str(exc)) from exc
    finally:
        await embedder.aclose()
        await engine.dispose()

    return build_report(dataset=dataset, parameters=_parameters(settings, args, dataset),
                        results=run.results, chunks=run.chunks, seconds=run.seconds,
                        version=settings.APP_VERSION)


def _parameters(settings: Settings, args: argparse.Namespace, dataset: Dataset) -> dict:
    return {
        "dataset": dataset.label,
        "embedding_model": settings.EMBEDDING_MODEL,
        "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
        "top_k": args.top_k,
        "chunk_size": args.chunk_size,
        "overlap_size": args.overlap_size,
        "min_score": settings.ANSWER_MIN_SCORE if args.min_score is None else args.min_score,
    }


class _Failure(Exception):
    """The evaluation could not run; the message says why."""


def _percent(value: float | None) -> str:
    return "     –" if value is None else f"{value:6.1%}"


def _print_summary(report: dict) -> None:
    parameters, metrics, dataset = report["parameters"], report["metrics"], report["dataset"]
    print(f"Retrieval on {parameters['dataset']}: {dataset['cases']} questions "
          f"({metrics['answerable']} answerable), {dataset['documents']} documents in "
          f"{dataset['chunks']} chunks")
    print(f"{parameters['embedding_model']} ({parameters['embedding_dimensions']} dimensions), "
          f"top {parameters['top_k']}, chunks of {parameters['chunk_size']} with "
          f"{parameters['overlap_size']} overlap, min score {parameters['min_score']}")
    print()
    rows = [("hit rate", "hit_rate", "answerable questions with a relevant result"),
            (f"recall@{parameters['top_k']}", "recall", "expected sources found"),
            ("MRR", "mrr", "1 / rank of the first relevant result, averaged"),
            ("above min score", "above_min_score", "answerable questions that would be answered"),
            ("rejected", "rejected", "unanswerable questions with no result at min score")]
    for label, key, meaning in rows:
        print(f"  {label:<16}{_percent(metrics[key])}   {meaning}")
    suggestion = report["suggested_min_score"]
    if suggestion:
        print(f"\n  A min score of {suggestion['min_score']} would answer "
              f"{suggestion['above_min_score']:.0%} of the answerable questions and reject "
              f"{suggestion['rejected']:.0%} of the others.")
    if report["metrics_by_tag"]:
        print(f"\n  {'tag':<14}{'questions':>10}{'hit rate':>10}{'MRR':>8}")
        for tag, values in report["metrics_by_tag"].items():
            print(f"  {tag:<14}{values['answerable'] + values['unanswerable']:>10}"
                  f"{_percent(values['hit_rate']):>10}{_percent(values['mrr']):>8}")
    missed = [case for case in report["cases"]
              if case["answerable"] and case["first_relevant_rank"] is None]
    if missed:
        print(f"\n  No relevant result in the top {parameters['top_k']}:")
        for case in missed:
            print(f"    {case['id']}: {case['question']}")
    seconds = report["seconds"]
    print(f"\n  Took {seconds['processing']} s to process, {seconds['indexing']} s to index "
          f"and {seconds['search']} s to search.")


def _read_baseline(path: Path) -> dict:
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise _Failure(f"The baseline {path} cannot be read ({exc.strerror}). Create it "
                       f"with --save-baseline.") from exc
    except json.JSONDecodeError as exc:
        raise _Failure(f"The baseline {path} is not valid JSON ({exc}).") from exc
    if not isinstance(baseline.get("parameters"), dict) or not isinstance(
            baseline.get("metrics"), dict):
        raise _Failure(f"The baseline {path} needs 'parameters' and 'metrics'.")
    return baseline


def _check_baseline(report: dict, baseline: dict, path: Path, tolerance: float) -> int:
    try:
        comparisons = compare(report, baseline)
    except BaselineMismatch as exc:
        raise _Failure(f"The baseline {path} cannot be compared: {exc}") from exc
    print(f"\nCompared with {path} (a drop of more than {tolerance:.1%} fails):")
    regressed = False
    for comparison in comparisons:
        worse = comparison.change < -tolerance
        regressed |= worse
        verdict = "lower" if worse else "better" if comparison.change > tolerance else "ok"
        print(f"  {comparison.metric:<16}{_percent(comparison.baseline)} → "
              f"{_percent(comparison.current)}   {verdict}")
    if regressed:
        print("Retrieval got worse than the baseline.")
        return REGRESSED
    if any(comparison.change > tolerance for comparison in comparisons):
        print("Retrieval got better: update the baseline with --save-baseline to keep it.")
    return PASSED


async def _evaluate(args: argparse.Namespace) -> int:
    settings = get_settings()
    try:
        dataset = load_dataset(args.dataset)
        baseline = None
        if args.baseline:
            baseline = _read_baseline(args.baseline)
            # Fail before the run when its parameters cannot match.
            compare({"parameters": _parameters(settings, args, dataset), "metrics": {}},
                    {**baseline, "metrics": {}})
        report = await _run_retrieval(settings, args, dataset)
        _print_summary(report)
        if args.output:
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                   encoding="utf-8")
            print(f"\nReport written to {args.output}.")
        if args.save_baseline:
            args.save_baseline.write_text(json.dumps(baseline_from(report), indent=2) + "\n",
                                          encoding="utf-8")
            print(f"Baseline written to {args.save_baseline}.")
        if baseline is not None:
            return _check_baseline(report, baseline, args.baseline, args.tolerance)
        return PASSED
    except BaselineMismatch as exc:
        print(f"The baseline {args.baseline} cannot be compared: {exc}", file=sys.stderr)
        return FAILED
    except (DatasetError, _Failure) as exc:
        print(exc, file=sys.stderr)
        return FAILED
    except AppError as exc:
        # For example the embedding model failing; its cause says why.
        cause = f" ({exc.__cause__})" if exc.__cause__ else ""
        print(f"The evaluation failed: {exc}{cause}", file=sys.stderr)
        return FAILED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mini-rag", description="Mini RAG maintenance commands.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    commands.add_parser(
        "resize-embeddings",
        help="change the stored vector size to EMBEDDING_DIMENSIONS, for an embedding model "
             "with vectors of another length; clears the stored vectors",
        description="Change the database's vector size to EMBEDDING_DIMENSIONS. Stored vectors "
                    "are cleared, because vectors of another model cannot be compared with new "
                    "ones; the chunks stay, and indexing embeds them again.")
    evaluate = commands.add_parser(
        "eval",
        help="measure how well search finds the sources that answer a dataset's questions",
        description="Upload, split and index a dataset's documents in a temporary project, "
                    "search for each of its questions, and report how well the expected "
                    "sources were found. Uses the configured embedding model and database; "
                    "the temporary project is deleted afterwards. Exits with 1 when a metric "
                    "falls below --baseline, and 2 when the evaluation cannot run.")
    evaluate.add_argument("dataset", type=Path, help="the dataset folder, e.g. evals/handbook/v1")
    evaluate.add_argument("--top-k", type=_positive, default=5,
                          help="results per question (default 5, as for answers)")
    evaluate.add_argument("--chunk-size", type=_positive, default=1000,
                          help="characters per chunk (default 1000, as for uploads)")
    evaluate.add_argument("--overlap-size", type=_non_negative, default=200,
                          help="characters of overlap between chunks (default 200)")
    evaluate.add_argument("--min-score", type=float,
                          help="the minimum score for an answer (default ANSWER_MIN_SCORE)")
    evaluate.add_argument("--output", type=Path, help="write the full JSON report here")
    evaluate.add_argument("--baseline", type=Path,
                          help="fail when a metric is lower than in this baseline")
    evaluate.add_argument("--tolerance", type=float, default=0.02,
                          help="how much lower a metric may be than the baseline (default 0.02)")
    evaluate.add_argument("--save-baseline", type=Path,
                          help="write this run's parameters and metrics as a baseline")
    args = parser.parse_args(argv)
    if args.command == "eval":
        if args.overlap_size >= args.chunk_size:
            parser.error("--overlap-size must be smaller than --chunk-size")
        return asyncio.run(_evaluate(args))
    return asyncio.run(_resize_embeddings())


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def _non_negative(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return number


if __name__ == "__main__":
    sys.exit(main())
