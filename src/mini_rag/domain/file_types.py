"""The file types documents can be read from, by extension and content type."""

from pathlib import PurePath

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

CONTENT_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
    ".pdf": "application/pdf",
    ".docx": DOCX,
}

# What clients send when they don't know a file's type.
_GENERIC = {"", "application/octet-stream"}
# Other names for the same types.
_ALIASES = {"text/x-markdown": "text/markdown", "application/xhtml+xml": "text/html"}


def content_type_for(file_name: str, declared: str | None) -> str | None:
    """The content type of an upload: the declared one, or the extension's.

    Browsers often send no type, or a generic one, for Markdown files;
    the extension decides then.
    """
    declared = (declared or "").split(";")[0].strip().lower()
    if declared in _GENERIC:
        return CONTENT_TYPES.get(PurePath(file_name).suffix.lower(), declared or None)
    return _ALIASES.get(declared, declared)
