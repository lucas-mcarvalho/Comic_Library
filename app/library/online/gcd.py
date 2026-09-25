"""Busca no Grand Comics Database (https://www.comics.org), gratuito e sem chave.

Os dados do GCD são licenciados sob CC BY-SA 4.0, por isso o app mostra a fonte.
"""

import re
import urllib.error
import urllib.parse

from app.library.images import cover_hash, hash_distance, thumbnail
from app.library.metadata import Metadata
from app.library.online.common import OnlineError, OnlineResult, basic_auth, fetch, fetch_json, normalize

API_URL = "https://www.comics.org/api"
SERVICE = "Grand Comics Database"
# O acesso anônimo à API tem um limite baixo de requisições por hora (login dá um limite maior),
# então cada busca faz o mínimo possível: busca + detalhes, e só compara capas quando há dúvida.
MAX_SEARCH_PAGES = 2
MAX_COVER_COMPARISONS = 4


class InvalidLoginError(OnlineError):
    pass


def _api(url: str, auth: dict | None) -> dict:
    try:
        return fetch_json(url, {"format": "json"} if "format=" not in url else None, SERVICE, auth)
    except urllib.error.HTTPError as error:
        if error.code == 401:
            raise InvalidLoginError("E-mail ou senha do Grand Comics Database incorretos.") from error
        raise


def _search(series: str, number: str, year: int | None, auth: dict | None) -> list[dict]:
    """Edições com esse número em séries cujo nome é exatamente `series`."""
    path = f"series/name/{urllib.parse.quote(series, safe='')}/issue/{urllib.parse.quote(number, safe='')}/"
    if year:
        path += f"year/{year}/"

    wanted = normalize(series)
    url, matches = f"{API_URL}/{path}", []
    for _ in range(MAX_SEARCH_PAGES):
        try:
            page = _api(url, auth)
        except urllib.error.HTTPError:
            break  # 404: nenhuma série com esse nome
        for issue in page.get("results", []):
            # series_name vem como "The Flash (2010 series)"
            match = re.fullmatch(r"(.*) \((\d{4}) series\)", issue.get("series_name", ""))
            name, began = (match.group(1), int(match.group(2))) if match else (issue.get("series_name", ""), 0)
            if normalize(name) == wanted:
                matches.append({**issue, "name": name, "began": began})
        url = page.get("next")
        if not url:
            break
    return matches


def _cover_distance(issue: dict, local_hash: int) -> int:
    cover_url = issue.get("cover") or ""
    if not cover_url:
        return 64
    try:
        return hash_distance(local_hash, cover_hash(fetch(cover_url.replace("/w400/", "/w100/"), service=SERVICE)))
    except (OnlineError, urllib.error.HTTPError, OSError):
        return 64


def _choose_issue(candidates: list[dict], year: int | None, local_cover: bytes | None, auth: dict | None) -> dict:
    """Entre várias séries com o mesmo nome (The Flash de 1987, 2010, 2016…), escolhe a edição certa."""
    # Prefere a edição normal às variantes de capa
    originals = [issue for issue in candidates if not issue["variant_of"]] or candidates
    originals.sort(key=lambda issue: (abs(year - issue["began"]) if year else -issue["began"]))
    if len(originals) == 1 or not local_cover:
        return _api(originals[0]["api_url"], auth)

    # Sem como decidir pelo nome, compara a capa do arquivo com a de cada candidata
    local_hash = cover_hash(local_cover)
    details = [_api(issue["api_url"], auth) for issue in originals[:MAX_COVER_COMPARISONS]]
    return min(details, key=lambda issue: _cover_distance(issue, local_hash))


def _clean_credit(credit: str) -> list[str]:
    """'Geoff Johns (credited); Fulano?' -> ['Geoff Johns', 'Fulano']"""
    credit = re.sub(r"\s*[\(\[][^)\]]*[\)\]]", "", credit or "")
    return [name.strip(" ?") for name in credit.split(";") if name.strip(" ?")]


def _summary(stories: list[dict]) -> str:
    stories = [story for story in stories if story.get("type") in ("comic story", "text story")]
    with_synopsis = [story for story in stories if (story.get("synopsis") or "").strip()]
    if len(with_synopsis) == 1:
        return with_synopsis[0]["synopsis"].strip()
    # Várias histórias na mesma edição: um parágrafo para cada, com o título
    return "\n\n".join(
        f"{story['title']}: {story['synopsis'].strip()}" if story.get("title") else story["synopsis"].strip()
        for story in with_synopsis
    )


def lookup(
    series: str,
    number: str,
    year: int | None,
    local_cover: bytes | None = None,
    login: tuple[str, str] | None = None,
) -> OnlineResult | None:
    """`login` (e-mail, senha) de uma conta gratuita do comics.org aumenta o limite de buscas."""
    if not series or not number:
        return None

    auth = basic_auth(*login) if login else None
    candidates = _search(series, number, year, auth)
    if not candidates and year:
        # O ano do nome do arquivo às vezes é o da edição brasileira ou da coletânea
        candidates = _search(series, number, None, auth)
    if not candidates:
        return None

    issue = _choose_issue(candidates, year, local_cover, auth)
    match = re.fullmatch(r"(.*) \((\d{4}) series\)", issue.get("series_name", ""))
    year_match = re.search(r"\d{4}", issue.get("key_date") or issue.get("publication_date") or "")

    writers = []
    for story in issue.get("story_set", []):
        if story.get("type") == "comic story":
            writers += [name for name in _clean_credit(story.get("script")) if name not in writers]

    issue_id = re.search(r"/issue/(\d+)/", issue["api_url"]).group(1)
    cover_url = issue.get("cover") or ""
    cover = None
    if cover_url:
        try:
            cover = thumbnail(fetch(cover_url, service=SERVICE), 400)
        except (OnlineError, urllib.error.HTTPError, OSError):
            pass  # a capa é opcional; os textos já valem a busca

    return OnlineResult(
        metadata=Metadata(
            series=match.group(1) if match else series,
            number=issue.get("number") or number,
            year=int(year_match.group()) if year_match else (int(match.group(2)) if match else year),
            writer=", ".join(writers),
            publisher=issue.get("indicia_publisher") or "",
            summary=_summary(issue.get("story_set", [])),
        ),
        source="gcd",
        source_url=f"https://www.comics.org/issue/{issue_id}/",
        cover_url=cover_url,
        cover=cover,
    )
