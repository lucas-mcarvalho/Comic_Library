"""Leitura de HQs compactadas (CBR/CBZ) com libarchive."""

import os
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    _dll_dir = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
    os.environ.setdefault("LIBARCHIVE", str(_dll_dir / "archive.dll"))

import libarchive

from app.library.images import thumbnail
from app.library.metadata import Metadata, parse_comic_info

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


def read_page(path: str | Path, name: str) -> bytes:
    """Retorna os bytes da imagem `name` dentro do arquivo."""
    with libarchive.file_reader(str(path)) as archive:
        for entry in archive:
            if entry.pathname == name:
                return b"".join(entry.get_blocks())
    raise KeyError(f"Página não encontrada: {name}")


def read_details(path: str | Path, max_width: int) -> tuple[bytes, int, Metadata | None]:
    """Capa em JPEG, total de páginas e o ComicInfo.xml (se houver), lendo o arquivo só duas vezes."""
    pages = []
    metadata = None
    with libarchive.file_reader(str(path)) as archive:
        for entry in archive:
            if _is_image(entry):
                pages.append(entry.pathname)
            elif entry.isfile and Path(entry.pathname).name.lower() == "comicinfo.xml":
                metadata = parse_comic_info(b"".join(entry.get_blocks()))
    if not pages:
        raise ValueError(f"Nenhuma imagem em {path}")

    cover_name = min(pages, key=_natural_key)
    return thumbnail(read_page(path, cover_name), max_width), len(pages), metadata
