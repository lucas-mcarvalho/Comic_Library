"""Busca de descrição e capa online: primeiro no GCD (grátis, sem chave), depois no ComicVine."""

from app.library.online import comicvine, gcd
from app.library.online.common import OnlineError, OnlineResult, RateLimitError
from app.library.online.comicvine import InvalidKeyError
from app.library.online.gcd import InvalidLoginError

__all__ = ["SOURCE_NAMES", "InvalidKeyError", "InvalidLoginError", "OnlineError", "OnlineResult", "RateLimitError", "lookup"]

SOURCE_NAMES = {"gcd": "Grand Comics Database", "comicvine": "ComicVine"}


def lookup(
    series: str,
    number: str,
    year: int | None,
    local_cover: bytes | None = None,
    comicvine_key: str = "",
    gcd_login: tuple[str, str] | None = None,
) -> OnlineResult | None:
    """Procura a HQ online. O ComicVine só é usado se houver chave e o GCD não trouxer a sinopse."""
    result, gcd_error = None, None
    try:
        result = gcd.lookup(series, number, year, local_cover, gcd_login)
    except InvalidLoginError:
        raise
    except OnlineError as error:
        gcd_error = error

    if comicvine_key and (result is None or not result.metadata.summary):
        try:
            extra = comicvine.lookup(comicvine_key, series, number, year)
        except InvalidKeyError:
            raise
        except OnlineError:
            if result is None and gcd_error is None:
                raise
            extra = None
        if extra is not None and result is None:
            result = extra
        elif extra is not None:
            # O GCD achou a edição, mas sem sinopse: completa com o que veio do ComicVine
            result.metadata.summary = extra.metadata.summary
            result.metadata.publisher = result.metadata.publisher or extra.metadata.publisher
            result.cover = result.cover or extra.cover
            if extra.metadata.summary:
                result.source = "gcd+comicvine"

    if result is None and gcd_error is not None:
        raise gcd_error
    return result
