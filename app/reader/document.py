"""Escolhe o leitor certo de acordo com o formato da HQ."""

from pathlib import Path

from app.library.metadata import Metadata, parse_filename
from app.reader import archive_reader, pdf_reader


def _is_pdf(path: str | Path) -> bool:
    return Path(path).suffix.lower() == ".pdf"


def open_document(path: str | Path):
    """Abre a HQ; o objeto retornado tem `page_count`, `page(index)` e `close()`."""
    if _is_pdf(path):
        return pdf_reader.PdfDocument(path)
    return archive_reader.ArchiveDocument(path)


def read_details(path: str | Path, max_width: int = 200) -> tuple[bytes, int, Metadata]:
    """Capa (JPEG), total de páginas e metadados; o que faltar no arquivo vem do nome dele."""
    reader = pdf_reader if _is_pdf(path) else archive_reader
    cover, page_count, metadata = reader.read_details(path, max_width)

    from_name = parse_filename(Path(path).stem)
    metadata = metadata or Metadata()
    metadata.series = metadata.series or from_name.series
    metadata.number = metadata.number or from_name.number
    metadata.year = metadata.year or from_name.year
    return cover, page_count, metadata
