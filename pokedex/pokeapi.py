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
# Ícones dos menus dos jogos (7ª geração), 40 x 30 px, usados na lista.
ICON_URL = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/"
    "pokemon/versions/generation-vii/icons/{number}.png"
)
REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = "PokePython (projeto de estudo)"
# Novas tentativas depois de uma falha de rede ou de servidor, com espera
# crescente entre elas.
RETRIES = 3
BACKOFF_SECONDS = (0.5, 1.0, 2.0)
# Política de uso justo da PokéAPI: no máximo 6 pedidos ao mesmo tempo.
MAX_CONNECTIONS = 6
MAX_REDIRECTS = 3
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
    """Resposta HTTP com erro (404, 500...)."""

    def __init__(self, url: str, status: int) -> None:
        super().__init__(f"HTTP {status} em {url}")
        self.status = status


_connections = threading.local()  # uma conexão por thread e por servidor
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


def _get_once(url: str) -> bytes:
    """Um pedido GET, reaproveitando a conexão desta thread com o servidor."""
    for _ in range(MAX_REDIRECTS + 1):
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
        if response.status in (301, 302, 303, 307, 308):
            url = urllib.parse.urljoin(url, response.getheader("Location"))
            continue
        if response.status != 200:
            raise DownloadError(url, response.status)
        return body
    raise DownloadError(url, 310)


def _worth_retrying(error: OSError) -> bool:
    """Falha de rede ou de servidor: vale tentar de novo. 404 e outros
    erros do pedido, não."""
    if isinstance(error, DownloadError):
        return error.status >= 500 or error.status == 429
    return True


def download(url: str) -> bytes:
    """Baixa o conteúdo de uma URL.

    Reaproveita conexões, tem timeout e User-Agent, limita os pedidos
    simultâneos e tenta de novo até RETRIES vezes, com espera crescente.
    """
    for attempt in range(RETRIES + 1):
        try:
            with _slots:
                return _get_once(url)
        except OSError as error:
            if attempt == RETRIES or not _worth_retrying(error):
                raise
            logger.info("Tentando de novo (%d): %s", attempt + 1, error)
            time.sleep(BACKOFF_SECONDS[attempt])
    raise AssertionError("inalcançável")


def format_name(api_name: str) -> str:
    """Converte um nome da API: "lightning-rod" vira "Lightning Rod"."""
    return SPECIAL_NAMES.get(api_name, api_name.replace("-", " ").title())


def parse_pokemon(data: dict[str, Any]) -> Pokemon:
    """Converte a resposta de /pokemon/{número} no modelo Pokemon."""
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


class PokeApiRepository:
    """Busca os Pokémon na PokéAPI e guarda em cache tudo o que baixa.

    O cache atende à política de uso da API ("cache resources locally")
    e permite usar offline os Pokémon que já foram vistos. Um item
    corrompido no cache é apagado e baixado de novo.
    """

    def __init__(
        self, cache: FileCache, fetch: Callable[[str], bytes] = download
    ) -> None:
        self._cache = cache
        self._fetch = fetch

    def list_entries(self) -> list[PokedexEntry]:
        names = self._cached_json("pokedex.json", self._fetch_names)
        return [
            PokedexEntry(number, name)
            for number, name in enumerate(names, start=1)
        ]

    def get_pokemon(self, number: int) -> Pokemon:
        name = f"{POKEMON_CACHE_DIR}/{number}.json"

        def fetch() -> dict[str, Any]:
            return asdict(self._fetch_pokemon(number))

        try:
            return Pokemon(**self._cached_json(name, fetch))
        except (TypeError, KeyError):
            # Item de uma versão antiga do modelo: baixa de novo.
            logger.warning("Item %s fora do formato; baixando de novo.", name)
            self._cache.discard(name)
            return Pokemon(**self._cached_json(name, fetch))

    def get_artwork(self, pokemon: Pokemon) -> bytes:
        return self._cached_png(
            f"artwork/{pokemon.number}.png", pokemon.artwork_url
        )

    def get_icon(self, number: int) -> bytes:
        """Ícone pequeno do Pokémon, para a lista."""
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

    def _fetch_png(self, url: str) -> bytes:
        content = self._fetch(url)
        if not content.startswith(PNG_SIGNATURE):
            raise ValueError(f"{url} não devolveu uma imagem PNG.")
        return content

    def _cached_png(self, name: str, url: str) -> bytes:
        """Imagem do cache; se estiver corrompida, apaga e baixa de novo."""
        content = self._cache.get_or_create(name, lambda: self._fetch_png(url))
        if content.startswith(PNG_SIGNATURE):
            return content
        logger.warning("Imagem %s corrompida; baixando de novo.", name)
        self._cache.discard(name)
        return self._cache.get_or_create(name, lambda: self._fetch_png(url))

    def _cached_json(self, name: str, create: Callable[[], Any]) -> Any:
        """Lê `name` do cache; se não existir, gera com `create` e salva.

        Guardamos só os campos usados: a resposta completa da API para
        um Pokémon tem cerca de 300 KB. Um arquivo corrompido é apagado e
        gerado de novo.
        """

        def encode() -> bytes:
            return json.dumps(create(), ensure_ascii=False).encode("utf-8")

        try:
            return json.loads(self._cache.get_or_create(name, encode))
        except ValueError:
            logger.warning("Item %s corrompido; gerando de novo.", name)
            self._cache.discard(name)
            return json.loads(self._cache.get_or_create(name, encode))
