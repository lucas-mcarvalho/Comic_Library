"""Leitura e renderização de páginas de PDF com PyMuPDF."""

from pathlib import Path

import pymupdf

from app.library.metadata import Metadata, parse_pdf_metadata

# Altura em pixels com que cada página é renderizada para leitura
RENDER_HEIGHT = 2000


class PdfDocument:
    def __init__(self, path: str | Path):
        self._document = pymupdf.open(path)

    @property
    def page_count(self) -> int:
        return self._document.page_count

    def page(self, index: int) -> bytes:
        """Renderiza a página `index` e retorna a imagem em PPM."""
        page = self._document.load_page(index)
        zoom = RENDER_HEIGHT / page.rect.height
        return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("ppm")

    def close(self):
        self._document.close()


def read_details(path: str | Path, max_width: int) -> tuple[bytes, int, Metadata]:
    """Capa em JPEG, total de páginas e os metadados do PDF."""
    with pymupdf.open(path) as document:
        page = document.load_page(0)
        zoom = max_width / page.rect.width
        cover = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("jpeg", jpg_quality=88)
        return cover, document.page_count, parse_pdf_metadata(document.metadata or {})
