"""Command-line tools. Run `mini-rag --help`."""

import argparse
import asyncio
import sys

from mini_rag.core.config import get_settings
from mini_rag.persistence.database import (
    create_engine,
    resize_embeddings,
    stored_embedding_dimensions,
)


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
    parser.parse_args(argv)
    # resize-embeddings is the only command so far.
    return asyncio.run(_resize_embeddings())


if __name__ == "__main__":
    sys.exit(main())
