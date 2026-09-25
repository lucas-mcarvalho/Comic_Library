"""Leitura de HQs compactadas (CBR/CBZ) com libarchive."""

import io
import os
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    _dll_dir = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    os.environ.setdefault("LIBARCHIVE", str(_dll_dir / "archive.dll"))

import libarchive
from PIL import Image

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


def _natural_key(name: str):
    """Ordena 'pag2' antes de 'pag10'."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def _is_image(entry) -> bool:
    return entry.isfile and Path(entry.pathname).suffix.lower() in IMAGE_EXTENSIONS


class ArchiveDocument:
    """Carrega todas as páginas na memória de uma vez: RAR é lento para acesso aleatório."""

    def __init__(self, path: str | Path):
        with libarchive.file_reader(str(path)) as archive:
            images = {entry.pathname: b"".join(entry.get_blocks()) for entry in archive if _is_image(entry)}
        self._pages = [images[name] for name in sorted(images, key=_natural_key)]

    @property
    def page_count(self) -> int:
        return len(self._pages)

    def page(self, index: int) -> bytes:
        return self._pages[index]

    def close(self):
        self._pages.clear()


def list_pages(path: str | Path) -> list[str]:
    """Retorna os nomes das imagens do arquivo, na ordem de leitura."""
    with libarchive.file_reader(str(path)) as archive:
        names = [entry.pathname for entry in archive if _is_image(entry)]
    return sorted(names, key=_natural_key)


def read_page(path: str | Path, name: str) -> bytes:
    """Retorna os bytes da imagem `name` dentro do arquivo."""
    with libarchive.file_reader(str(path)) as archive:
        for entry in archive:
            if entry.pathname == name:
                return b"".join(entry.get_blocks())
    raise KeyError(f"Página não encontrada: {name}")


def render_cover(path: str | Path, max_width: int = 200) -> bytes:
    """Retorna a primeira página do arquivo reduzida, em PNG."""
    pages = list_pages(path)
    if not pages:
        raise ValueError(f"Nenhuma imagem em {path}")

    image = Image.open(io.BytesIO(read_page(path, pages[0])))
    image.thumbnail((max_width, max_width * 3))
    output = io.BytesIO()
    image.convert("RGB").save(output, "PNG")
    return output.getvalue()
