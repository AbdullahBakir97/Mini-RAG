import pytest

from mini_rag.core.errors import UnsupportedFileType
from mini_rag.loaders.pdf_loader import PdfLoader
from mini_rag.loaders.registry import LoaderRegistry, default_loader_registry
from mini_rag.loaders.text_loader import TextLoader


@pytest.mark.parametrize(("file_name", "loader_type"), [
    ("abc_notes.txt", TextLoader),
    ("abc_NOTES.TXT", TextLoader),
    ("abc_report.pdf", PdfLoader),
    ("abc_report.Pdf", PdfLoader),
])
def test_default_registry_picks_loader_by_extension(file_name, loader_type):
    assert isinstance(default_loader_registry().get(file_name), loader_type)


@pytest.mark.parametrize("file_name", ["abc_notes.md", "abc_notes", "abc_archive.txt.zip", ".."])
def test_registry_rejects_unknown_extensions(file_name):
    with pytest.raises(UnsupportedFileType):
        default_loader_registry().get(file_name)


def test_new_file_types_only_need_registering():
    class MarkdownLoader:
        def load(self, path, source):
            return []

    markdown = MarkdownLoader()
    registry = LoaderRegistry({".MD": markdown})

    assert registry.get("x_readme.md") is markdown
    assert registry.extensions == {".md"}


def test_text_loader_reads_utf8_and_replaces_bad_bytes(tmp_path):
    path = tmp_path / "a.txt"
    path.write_bytes("café ".encode() + b"\xff")

    [document] = TextLoader().load(path, source="a.txt")

    assert document.text == "café �"
    assert document.metadata == {"source": "a.txt"}


def test_pdf_loader_returns_one_document_per_page(tmp_path, make_pdf):
    path = tmp_path / "a.pdf"
    path.write_bytes(make_pdf(["First page.", "", "Third page."]))

    documents = PdfLoader().load(path, source="a.pdf")

    assert [(d.text.strip(), d.metadata) for d in documents] == [
        ("First page.", {"source": "a.pdf", "page": 1}),
        ("", {"source": "a.pdf", "page": 2}),
        ("Third page.", {"source": "a.pdf", "page": 3}),
    ]
