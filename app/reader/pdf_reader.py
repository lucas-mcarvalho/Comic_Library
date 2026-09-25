"""Leitura e renderização de páginas de PDF com PyMuPDF."""

from pathlib import Path

import pymupdf

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


def render_cover(path: str | Path, max_width: int = 200) -> bytes:
    """Renderiza a primeira página do PDF e retorna a imagem em PNG."""
    with pymupdf.open(path) as document:
        page = document.load_page(0)
        zoom = max_width / page.rect.width
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        return pixmap.tobytes("png")
