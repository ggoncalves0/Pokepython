"""Acesso à PokéAPI (https://pokeapi.co): download, conversão e cache."""

import http.client
import json
import logging
import threading
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from .cache import FileCache
from .models import PokedexEntry, Pokemon

logger = logging.getLogger(__name__)

API_URL = "https://pokeapi.co/api/v2"
POKEDEX_SIZE = 151
ICON_URL = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/"
    "pokemon/versions/generation-vii/icons/{number}.png"
)
REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = "PokePython (projeto de estudo)"
BACKOFF_SECONDS = (0.5, 1.0, 2.0)
# Política de uso justo da PokéAPI: no máximo 6 pedidos ao mesmo tempo.
MAX_CONNECTIONS = 6
MAX_REDIRECTS = 3
REDIRECT_STATUSES = (301, 302, 303, 307, 308)
PNG_SIGNATURE = bytes([0x89]) + b"PNG" + bytes([13, 10, 26, 10])
# Mude sempre que o modelo Pokemon ganhar ou perder campos: assim os
# arquivos antigos do cache, sem os campos novos, deixam de ser lidos.
POKEMON_CACHE_DIR = "pokemon-v2"

# Nomes que não ficam certos só trocando "-" por espaço e capitalizando.
SPECIAL_NAMES = {
    "nidoran-f": "Nidoran♀",
    "nidoran-m": "Nidoran♂",
    "farfetchd": "Farfetch'd",
    "mr-mime": "Mr. Mime",
}


class DownloadError(OSError):
    def __init__(self, url: str, status: int) -> None:
        super().__init__(f"HTTP {status} em {url}")
        self.status = status


# As conexões do http.client não podem ser usadas por duas threads ao
# mesmo tempo: cada thread guarda as suas, uma por servidor.
_connections = threading.local()
_slots = threading.BoundedSemaphore(MAX_CONNECTIONS)


def _connection(host: str) -> http.client.HTTPSConnection:
    pool: dict[str, http.client.HTTPSConnection] = _connections.__dict__
    connection = pool.get(host)
    if connection is None:
        connection = http.client.HTTPSConnection(
            host, timeout=REQUEST_TIMEOUT_SECONDS
        )
        pool[host] = connection
    return connection


def _drop_connection(host: str) -> None:
    connection = _connections.__dict__.pop(host, None)
    if connection is not None:
        connection.close()


def _request(url: str) -> tuple[int, bytes, str | None]:
    parts = urllib.parse.urlsplit(url)
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    connection = _connection(parts.netloc)
    try:
        connection.request("GET", path, headers={"User-Agent": USER_AGENT})
        response = connection.getresponse()
        body = response.read()
    except (OSError, http.client.HTTPException) as error:
        # Conexão caiu ou o servidor a fechou: abre outra na próxima.
        _drop_connection(parts.netloc)
        raise OSError(f"Falha de rede em {url}: {error}") from error
    return response.status, body, response.getheader("Location")


def _get_once(url: str) -> bytes:
    redirects = 0
    while True:
        status, body, location = _request(url)
        if status in REDIRECT_STATUSES and redirects < MAX_REDIRECTS:
            url = urllib.parse.urljoin(url, location)
            redirects += 1
            continue
        if status != 200:
            raise DownloadError(url, status)
        return body


def _get_once_within_limit(url: str) -> bytes:
    with _slots:
        return _get_once(url)


def _worth_retrying(error: OSError) -> bool:
    # Um erro do pedido (404 e os outros 4xx) não muda tentando de novo;
    # o 429 só pede para esperar.
    if isinstance(error, DownloadError):
        return error.status >= 500 or error.status == 429
    return True


def download(url: str) -> bytes:
    for wait in BACKOFF_SECONDS:
        try:
            return _get_once_within_limit(url)
        except OSError as error:
            if not _worth_retrying(error):
                raise
            logger.info("Tentando de novo em %.1f s: %s", wait, error)
            time.sleep(wait)
    return _get_once_within_limit(url)


def format_name(api_name: str) -> str:
    return SPECIAL_NAMES.get(api_name, api_name.replace("-", " ").title())


def parse_pokemon(data: dict[str, Any]) -> Pokemon:
    """`data` é a resposta de /pokemon/{número}."""
    abilities = []
    hidden_ability = None
    for item in data["abilities"]:
        name = format_name(item["ability"]["name"])
        if item["is_hidden"]:
            hidden_ability = name
        else:
            abilities.append(name)

    artwork = data["sprites"]["other"]["official-artwork"]
    return Pokemon(
        number=data["id"],
        name=format_name(data["name"]),
        types=[item["type"]["name"] for item in data["types"]],
        stats={
            item["stat"]["name"]: item["base_stat"] for item in data["stats"]
        },
        abilities=abilities,
        hidden_ability=hidden_ability,
        artwork_url=artwork["front_default"],
        # A API usa decímetros e hectogramas.
        height=data["height"] / 10,
        weight=data["weight"] / 10,
    )


def _require_png(content: bytes, source: str) -> bytes:
    if not content.startswith(PNG_SIGNATURE):
        raise ValueError(f"{source} não é uma imagem PNG.")
    return content


def _as_json(create: Callable[[], Any]) -> Callable[[], bytes]:
    return lambda: json.dumps(create(), ensure_ascii=False).encode("utf-8")


class PokeApiRepository:
    """Busca os Pokémon na PokéAPI e guarda em cache tudo o que baixa.

    O cache atende à política de uso da API ("cache resources locally")
    e permite usar offline os Pokémon que já foram vistos.
    """

    def __init__(
        self, cache: FileCache, fetch: Callable[[str], bytes] = download
    ) -> None:
        self._cache = cache
        self._fetch = fetch

    def list_entries(self) -> list[PokedexEntry]:
        names: list[str] = self._cached(
            "pokedex.json", _as_json(self._fetch_names), json.loads
        )
        return [
            PokedexEntry(number, name)
            for number, name in enumerate(names, start=1)
        ]

    def get_pokemon(self, number: int) -> Pokemon:
        # Guarda só os campos do modelo: a resposta completa da API tem
        # cerca de 300 KB por Pokémon.
        return self._cached(
            f"{POKEMON_CACHE_DIR}/{number}.json",
            _as_json(lambda: asdict(self._fetch_pokemon(number))),
            lambda content: Pokemon(**json.loads(content)),
        )

    def get_artwork(self, pokemon: Pokemon) -> bytes:
        return self._cached_png(
            f"artwork/{pokemon.number}.png", pokemon.artwork_url
        )

    def get_icon(self, number: int) -> bytes:
        return self._cached_png(
            f"icons/{number}.png", ICON_URL.format(number=number)
        )

    def _fetch_names(self) -> list[str]:
        data = self._fetch_json(f"{API_URL}/pokemon?limit={POKEDEX_SIZE}")
        return [format_name(item["name"]) for item in data["results"]]

    def _fetch_pokemon(self, number: int) -> Pokemon:
        return parse_pokemon(self._fetch_json(f"{API_URL}/pokemon/{number}"))

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _cached_png(self, name: str, url: str) -> bytes:
        return self._cached(
            name,
            lambda: _require_png(self._fetch(url), url),
            lambda content: _require_png(content, name),
        )

    def _cached[T](
        self,
        name: str,
        create: Callable[[], bytes],
        read: Callable[[bytes], T],
    ) -> T:
        content = self._cache.get_or_create(name, create)
        try:
            return read(content)
        except (ValueError, TypeError, KeyError):
            # Arquivo corrompido, ou gravado por uma versão antiga do modelo.
            logger.warning(
                "Item %s inválido no cache; baixando de novo.", name
            )
            self._cache.discard(name)
            return read(self._cache.get_or_create(name, create))
