"""Varre uma pasta em busca de HQs (PDF, CBR, CBZ)."""

from dataclasses import dataclass
from pathlib import Path

SUPPORTED_EXTENSIONS = {".pdf", ".cbr", ".cbz"}


@dataclass(frozen=True)
class Comic:
    title: str
    path: Path
    size_bytes: int


def scan_folder(folder: str | Path, recursive: bool = True) -> list[Comic]:
    """Retorna a lista de HQs encontradas em `folder`, ordenada pelo título."""
    root = Path(folder).expanduser()
    if not root.is_dir():
        raise NotADirectoryError(f"Pasta inválida: {root}")

    files = root.rglob("*") if recursive else root.iterdir()
    comics = [
        Comic(title=file.stem, path=file, size_bytes=file.stat().st_size)
        for file in files
        if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(comics, key=lambda comic: comic.title.lower())
