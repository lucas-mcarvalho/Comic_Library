"""Escolhe o leitor certo de acordo com o formato da HQ."""

from pathlib import Path

from app.reader import archive_reader, pdf_reader


def _is_pdf(path: str | Path) -> bool:
    return Path(path).suffix.lower() == ".pdf"


def open_document(path: str | Path):
    """Abre a HQ; o objeto retornado tem `page_count`, `page(index)` e `close()`."""
    if _is_pdf(path):
        return pdf_reader.PdfDocument(path)
    return archive_reader.ArchiveDocument(path)


def render_cover(path: str | Path, max_width: int = 200) -> bytes:
    if _is_pdf(path):
        return pdf_reader.render_cover(path, max_width)
    return archive_reader.render_cover(path, max_width)
