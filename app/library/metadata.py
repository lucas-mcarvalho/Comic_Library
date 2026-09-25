"""Metadados de uma HQ: ComicInfo.xml, metadados do PDF e nome do arquivo."""

import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass


@dataclass
class Metadata:
    series: str = ""
    number: str = ""
    year: int | None = None
    writer: str = ""
    publisher: str = ""
    summary: str = ""


def _int_or_none(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None


def parse_comic_info(xml: bytes) -> Metadata:
    """Lê o ComicInfo.xml (padrão do ComicRack) que vem dentro de muitos CBZ/CBR."""
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return Metadata()

    def text(tag: str) -> str:
        return (root.findtext(tag) or "").strip()

    return Metadata(
        series=text("Series") or text("Title"),
        number=text("Number"),
        year=_int_or_none(text("Year")),
        writer=text("Writer"),
        publisher=text("Publisher"),
        summary=text("Summary"),
    )


def parse_pdf_metadata(info: dict) -> Metadata:
    date = info.get("creationDate") or ""  # formato "D:AAAAMMDD..."
    return Metadata(
        series=(info.get("title") or "").strip(),
        year=_int_or_none(date[2:6]) if date.startswith("D:") else None,
        writer=(info.get("author") or "").strip(),
        summary=(info.get("subject") or "").strip(),
    )


def parse_filename(title: str) -> Metadata:
    """Extrai série, número e ano de nomes como 'The Flash v3 #01 (2016) (Grupo)'."""
    year_match = re.search(r"\((\d{4})\)", title)
    name = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", title)  # remove (ano), (grupo de scan), [tags]

    number_match = re.search(r"#\s*(\d+(?:\.\d+)?)", name) or re.search(r"\s(\d{1,4})\s*$", name)
    series = name[: number_match.start()] if number_match else name
    series = re.sub(r"\s+v(?:ol\.?)?\s*\d+\s*$", "", series.strip(), flags=re.IGNORECASE)

    number = (number_match.group(1).lstrip("0") or "0") if number_match else ""
    return Metadata(
        series=re.sub(r"\s+", " ", series).strip(" -_"),
        number=number,
        year=int(year_match.group(1)) if year_match else None,
    )
