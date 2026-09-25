"""Tipos e acesso HTTP compartilhados pelas fontes online."""

import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from app.library.metadata import Metadata

USER_AGENT = "ComicLibrary/1.0 (leitor de HQs para desktop)"
TIMEOUT = 20


class OnlineError(Exception):
    pass


class RateLimitError(OnlineError):
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after  # segundos até o serviço aceitar buscas de novo


@dataclass
class OnlineResult:
    metadata: Metadata
    source: str  # "gcd" ou "comicvine"
    source_url: str = ""  # página da HQ no site da fonte
    cover_url: str = ""
    cover: bytes | None = None  # capa já baixada e reduzida


def basic_auth(user: str, password: str) -> dict:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def fetch(url: str, params: dict | None = None, service: str = "servidor", headers: dict | None = None) -> bytes:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        if error.code in (401, 404):
            raise  # quem chamou decide: chave inválida ou "não encontrado"
        if error.code in (420, 429):
            retry_after = error.headers.get("Retry-After", "")
            wait = int(retry_after) if retry_after.isdigit() else None
            when = f"em {max(1, round(wait / 60))} min" if wait else "daqui a pouco"
            raise RateLimitError(f"Limite de buscas do {service} atingido; tente de novo {when}.", wait) from error
        raise OnlineError(f"O {service} respondeu com erro {error.code}.") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise OnlineError(f"Não foi possível conectar ao {service}. Verifique a internet.") from error


def fetch_json(url: str, params: dict | None = None, service: str = "servidor", headers: dict | None = None) -> dict:
    try:
        return json.loads(fetch(url, params, service, headers))
    except json.JSONDecodeError as error:
        raise OnlineError(f"Resposta inválida do {service}.") from error


def normalize(name: str) -> str:
    """Compara nomes de série ignorando maiúsculas, pontuação e o artigo inicial."""
    name = re.sub(r"[^\w]+", " ", name.casefold()).strip()
    return re.sub(r"^(the|a|o|os|as) ", "", name)
