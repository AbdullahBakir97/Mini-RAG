import logging

import pytest
from pydantic import ValidationError

from mini_rag.core.config import Settings
from mini_rag.core.logging_config import _handler, configure_logging


@pytest.fixture(autouse=True)
def restore_logging():
    root, app = logging.getLogger(), logging.getLogger("mini_rag")
    saved = root.level, list(root.handlers), app.level
    yield
    root.setLevel(saved[0])
    root.handlers[:] = saved[1]
    app.setLevel(saved[2])


def test_adds_one_formatted_handler_however_often_called(capsys):
    configure_logging("INFO")
    configure_logging("INFO")  # e.g. once per app in tests

    assert logging.getLogger().handlers.count(_handler) == 1

    logging.getLogger("mini_rag.services.example").warning("disk almost full")

    line = capsys.readouterr().err.strip()
    assert line.endswith("WARNING  mini_rag.services.example: disk almost full")
    assert line[:4].isdigit()  # starts with a timestamp


def test_app_logs_follow_the_configured_level(capsys):
    configure_logging("DEBUG")
    logging.getLogger("mini_rag.x").debug("shown")
    configure_logging("ERROR")
    logging.getLogger("mini_rag.x").warning("hidden")

    err = capsys.readouterr().err
    assert "shown" in err and "hidden" not in err


def test_third_party_logs_are_formatted_and_limited_to_warnings(capsys):
    configure_logging("DEBUG")

    logging.getLogger("pypdf._reader").info("noise")
    logging.getLogger("pypdf._reader").warning("invalid pdf header")

    err = capsys.readouterr().err
    assert "noise" not in err
    assert "WARNING  pypdf._reader: invalid pdf header" in err


def test_invalid_log_level_is_rejected(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "LOUD")

    with pytest.raises(ValidationError):
        Settings()
