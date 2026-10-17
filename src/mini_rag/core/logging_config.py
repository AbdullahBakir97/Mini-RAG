import logging
import sys

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
THIRD_PARTY_LEVEL = logging.WARNING


class _StderrHandler(logging.StreamHandler):
    """Writes to whatever sys.stderr is at the time of each record."""

    def __init__(self):
        super().__init__()
        self.setFormatter(logging.Formatter(LOG_FORMAT))

    @property
    def stream(self):
        return sys.stderr

    @stream.setter
    def stream(self, value):
        pass


_handler = _StderrHandler()


def configure_logging(level: str) -> None:
    """Format all logs and set the application's log level.

    The handler goes on the root logger so third-party libraries (such as
    pypdf) share the format; they are limited to warnings and above, while
    the ``mini_rag`` loggers use ``level``. Uvicorn keeps its own handlers.
    Safe to call repeatedly, e.g. once per app in tests.
    """
    root = logging.getLogger()
    if _handler not in root.handlers:
        root.addHandler(_handler)
    root.setLevel(THIRD_PARTY_LEVEL)
    logging.getLogger("mini_rag").setLevel(level)
