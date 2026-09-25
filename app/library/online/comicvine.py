"""Busca de descrições no ComicVine (https://comicvine.gamespot.com/api/, chave gratuita)."""

import re
import urllib.error
from html.parser import HTMLParser

from app.library.images import thumbnail
from app.library.metadata import Metadata
from app.library.online.common import OnlineError, OnlineResult, fetch, fetch_json, normalize

API_URL = "https://comicvine.gamespot.com/api"
SERVICE = "ComicVine"


class _TextExtractor(HTMLParser):
    """Converte a descrição em HTML do ComicVine em texto, ignorando tabelas e imagens."""

    BLOCKS = {"p", "br", "li", "h1", "h2", "h3", "h4", "div"}
    SKIPPED = {"table", "figure", "script", "style"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIPPED:
            self.skip_depth += 1
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIPPED:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data)


def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    parser = _TextExtractor()
    parser.feed(html)
    text = "".join(parser.parts)
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


class InvalidKeyError(OnlineError):
    pass


def _get(api_key: str, endpoint: str, **params) -> list[dict]:
    try:
        data = fetch_json(f"{API_URL}/{endpoint}/", {"api_key": api_key, "format": "json", **params}, SERVICE)
    except urllib.error.HTTPError as error:
        if error.code == 401:
            raise InvalidKeyError("Chave da API do ComicVine inválida.") from error
        raise OnlineError(f"O ComicVine respondeu com erro {error.code}.") from error

    if data.get("status_code") == 100:
        raise InvalidKeyError("Chave da API do ComicVine inválida.")
    if data.get("status_code") != 1:
        raise OnlineError(data.get("error") or "Erro desconhecido do ComicVine.")
    return data.get("results") or []


def _best_volume(volumes: list[dict], series: str, year: int | None) -> dict | None:
    """Prefere nome idêntico, depois a série iniciada mais perto (antes) do ano da edição, depois a mais longa."""
    wanted = normalize(series)

    def score(volume):
        exact = normalize(volume.get("name") or "") == wanted
        start = int(volume.get("start_year") or 0) if str(volume.get("start_year") or "").isdigit() else 0
        distance = year - start if year and start and start <= year else 9999
        return (not exact, distance, -(volume.get("count_of_issues") or 0))

    return min(volumes, key=score) if volumes else None


def lookup(api_key: str, series: str, number: str, year: int | None) -> OnlineResult | None:
    """Procura a série e a edição no ComicVine. Retorna None se nada for encontrado."""
    if not series:
        return None

    volumes = _get(
        api_key,
        "search",
        resources="volume",
        query=series,
        limit=10,
        field_list="id,name,start_year,count_of_issues,publisher,deck,description,image,site_detail_url",
    )
    volume = _best_volume(volumes, series, year)
    if volume is None:
        return None

    issue = {}
    if number:
        issues = _get(
            api_key,
            "issues",
            filter=f"volume:{volume['id']},issue_number:{number}",
            field_list="issue_number,cover_date,deck,description,image,site_detail_url",
        )
        issue = issues[0] if issues else {}

    # Muitas edições não têm sinopse; nesse caso usa a descrição da série
    summary = (
        html_to_text(issue.get("description"))
        or (issue.get("deck") or "").strip()
        or (volume.get("deck") or "").strip()
        or html_to_text(volume.get("description"))
    )
    cover_date = issue.get("cover_date") or ""
    cover_url = ((issue or volume).get("image") or {}).get("medium_url") or ""
    cover = None
    if cover_url:
        try:
            cover = thumbnail(fetch(cover_url, service=SERVICE), 400)
        except (OnlineError, urllib.error.HTTPError, OSError):
            pass

    return OnlineResult(
        metadata=Metadata(
            series=volume.get("name") or series,
            number=issue.get("issue_number") or number,
            year=int(cover_date[:4]) if cover_date[:4].isdigit() else year,
            publisher=(volume.get("publisher") or {}).get("name", ""),
            summary=summary,
        ),
        source="comicvine",
        source_url=(issue or volume).get("site_detail_url") or "",
        cover_url=cover_url,
        cover=cover,
    )
