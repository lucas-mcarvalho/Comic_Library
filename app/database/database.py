"""Persistência da biblioteca em SQLite: capas, metadados e progresso de leitura.

Usado só pela thread da interface; o trabalho pesado (renderizar capas, buscar online)
acontece em outras threads, que devolvem o resultado para ser gravado aqui.
"""

import sqlite3
import time
from dataclasses import astuple, dataclass, fields
from pathlib import Path

from app.library.metadata import Metadata
from app.library.scanner import Comic

SCHEMA_VERSION = 2

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS comics (
    path          TEXT PRIMARY KEY,
    size          INTEGER NOT NULL,
    modified      REAL NOT NULL,
    cover         BLOB,
    page_count    INTEGER,
    last_page     INTEGER NOT NULL DEFAULT 0,
    last_read_at  REAL,
    -- NULL enquanto os metadados do arquivo não foram lidos; depois 'file', 'manual', 'gcd', 'comicvine'…
    metadata_source TEXT,
    series        TEXT NOT NULL DEFAULT '',
    number        TEXT NOT NULL DEFAULT '',
    year          INTEGER,
    writer        TEXT NOT NULL DEFAULT '',
    publisher     TEXT NOT NULL DEFAULT '',
    summary       TEXT NOT NULL DEFAULT ''
);
"""

# Versão 2: capa e página da HQ vindas da busca online
SCHEMA_V2 = """
ALTER TABLE comics ADD COLUMN online_cover BLOB;
ALTER TABLE comics ADD COLUMN use_online_cover INTEGER NOT NULL DEFAULT 0;
ALTER TABLE comics ADD COLUMN source_url TEXT NOT NULL DEFAULT '';
ALTER TABLE comics ADD COLUMN looked_up_at REAL;
"""

# Mesma ordem dos campos de Metadata, para usar astuple() nas consultas
METADATA_FIELDS = tuple(field.name for field in fields(Metadata))


@dataclass
class ComicRecord:
    path: Path
    cover: bytes | None
    page_count: int | None
    last_page: int
    last_read_at: float | None
    metadata_source: str | None
    metadata: Metadata
    online_cover: bytes | None
    use_online_cover: bool
    source_url: str
    looked_up_at: float | None

    @property
    def needs_scan(self) -> bool:
        """Capa, total de páginas ou metadados do arquivo ainda não foram extraídos."""
        return self.cover is None or self.page_count is None or self.metadata_source is None

    @property
    def display_cover(self) -> bytes | None:
        return self.online_cover if self.use_online_cover and self.online_cover else self.cover

    @property
    def started(self) -> bool:
        return self.last_read_at is not None

    @property
    def finished(self) -> bool:
        return self.started and self.page_count is not None and self.last_page >= self.page_count - 1

    @property
    def progress(self) -> float:
        if not self.started or not self.page_count:
            return 0.0
        return min(1.0, (self.last_page + 1) / self.page_count)


class Library:
    def __init__(self, db_path: str | Path):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(db_path)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode = WAL")
        version = self._db.execute("PRAGMA user_version").fetchone()[0]
        for number, script in enumerate((SCHEMA_V1, SCHEMA_V2), start=1):
            if version < number:
                self._db.executescript(f"BEGIN; {script} PRAGMA user_version = {number}; COMMIT;")

    def close(self):
        self._db.close()

    @staticmethod
    def _record(row: sqlite3.Row) -> ComicRecord:
        return ComicRecord(
            path=Path(row["path"]),
            cover=row["cover"],
            page_count=row["page_count"],
            last_page=row["last_page"],
            last_read_at=row["last_read_at"],
            metadata_source=row["metadata_source"],
            metadata=Metadata(**{field: row[field] for field in METADATA_FIELDS}),
            online_cover=row["online_cover"],
            use_online_cover=bool(row["use_online_cover"]),
            source_url=row["source_url"],
            looked_up_at=row["looked_up_at"],
        )

    def get(self, path: Path) -> ComicRecord | None:
        row = self._db.execute("SELECT * FROM comics WHERE path = ?", (str(path),)).fetchone()
        return self._record(row) if row else None

    def sync(self, comics: list[Comic]) -> dict[Path, ComicRecord]:
        """Registra as HQs encontradas na pasta e devolve o registro de cada uma.

        Se o arquivo mudou desde a última vez, a capa e os metadados lidos dele são
        descartados para serem extraídos de novo; progresso e edições manuais ficam.
        """
        with self._db:
            for comic in comics:
                self._db.execute(
                    """
                    INSERT INTO comics (path, size, modified) VALUES (?, ?, ?)
                    ON CONFLICT (path) DO UPDATE SET
                        cover = NULL,
                        page_count = NULL,
                        metadata_source = CASE WHEN metadata_source = 'file' THEN NULL ELSE metadata_source END,
                        size = excluded.size,
                        modified = excluded.modified
                    WHERE size != excluded.size OR modified != excluded.modified
                    """,
                    (str(comic.path), comic.size_bytes, comic.modified),
                )

        records = {}
        paths = [str(comic.path) for comic in comics]
        # Consulta em lotes para respeitar o limite de parâmetros do SQLite
        for start in range(0, len(paths), 500):
            batch = paths[start : start + 500]
            placeholders = ",".join("?" * len(batch))
            for row in self._db.execute(f"SELECT * FROM comics WHERE path IN ({placeholders})", batch):
                record = self._record(row)
                records[record.path] = record
        return records

    def save_scan(self, path: Path, cover: bytes, page_count: int, metadata: Metadata):
        """Grava o que foi extraído do arquivo; metadados editados ou buscados online têm prioridade."""
        with self._db:
            self._db.execute(
                "UPDATE comics SET cover = ?, page_count = ? WHERE path = ?", (cover, page_count, str(path))
            )
            self._db.execute(
                f"""
                UPDATE comics SET metadata_source = 'file', {", ".join(f"{field} = ?" for field in METADATA_FIELDS)}
                WHERE path = ? AND metadata_source IS NULL
                """,
                (*astuple(metadata), str(path)),
            )

    def save_metadata(self, path: Path, metadata: Metadata, source: str):
        with self._db:
            self._db.execute(
                f"""
                UPDATE comics SET metadata_source = ?, {", ".join(f"{field} = ?" for field in METADATA_FIELDS)}
                WHERE path = ?
                """,
                (source, *astuple(metadata), str(path)),
            )

    def save_online(self, path: Path, metadata: Metadata, source: str, source_url: str, cover: bytes | None):
        """Grava o resultado de uma busca online; a capa online só é trocada se veio uma nova."""
        self.save_metadata(path, metadata, source)
        with self._db:
            self._db.execute(
                """
                UPDATE comics SET source_url = ?, online_cover = COALESCE(?, online_cover), looked_up_at = ?
                WHERE path = ?
                """,
                (source_url, cover, time.time(), str(path)),
            )

    def mark_looked_up(self, path: Path):
        """Registra uma busca sem resultado, para o 'Buscar todas' não repetir a mesma HQ."""
        with self._db:
            self._db.execute("UPDATE comics SET looked_up_at = ? WHERE path = ?", (time.time(), str(path)))

    def set_use_online_cover(self, path: Path, use: bool):
        with self._db:
            self._db.execute("UPDATE comics SET use_online_cover = ? WHERE path = ?", (int(use), str(path)))

    def save_progress(self, path: Path, page: int, page_count: int):
        with self._db:
            self._db.execute(
                "UPDATE comics SET last_page = ?, page_count = ?, last_read_at = ? WHERE path = ?",
                (page, page_count, time.time(), str(path)),
            )
