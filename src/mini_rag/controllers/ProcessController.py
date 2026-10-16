import os
from dataclasses import dataclass, field

from pypdf import PdfReader

from mini_rag.helpers.text_splitter import RecursiveTextSplitter
from mini_rag.models import ProcessingEnum
from mini_rag.storage.file_storage import FileStorage


@dataclass
class Document:
    text: str
    metadata: dict = field(default_factory=dict)


class ProcessController:

    def __init__(self, storage: FileStorage):
        self.storage = storage

    def is_supported(self, file_id: str):
        extension = os.path.splitext(file_id)[-1].lower()
        return extension in {item.value for item in ProcessingEnum}

    def load_documents(self, file_path: str, file_id: str):
        extension = os.path.splitext(file_id)[-1].lower()

        if extension == ProcessingEnum.TXT.value:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                return [Document(text=f.read(), metadata={"source": file_id})]

        if extension == ProcessingEnum.PDF.value:
            reader = PdfReader(file_path)
            return [
                Document(
                    text=page.extract_text() or "",
                    metadata={"source": file_id, "page": page_number},
                )
                for page_number, page in enumerate(reader.pages, start=1)
            ]

        raise ValueError(f"Unsupported file type: {extension}")

    def process_file(self, file_path: str, file_id: str,
                     chunk_size: int, overlap_size: int):
        splitter = RecursiveTextSplitter(chunk_size=chunk_size, overlap_size=overlap_size)

        chunks = []
        for document in self.load_documents(file_path=file_path, file_id=file_id):
            for text in splitter.split(document.text):
                chunks.append(Document(
                    text=text,
                    metadata={**document.metadata, "chunk_index": len(chunks)},
                ))
        return chunks
