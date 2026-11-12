"""Acesso à PokéAPI (https://pokeapi.co): download, conversão e cache."""

import json
from collections.abc import Callable
from dataclasses import asdict
from typing import Any
from urllib.request import Request, urlopen

from .cache import FileCache
from .models import PokedexEntry, Pokemon

API_URL = "https://pokeapi.co/api/v2"
POKEDEX_SIZE = 151
REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = "PokePython (projeto de estudo)"
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


def download(url: str) -> bytes:
    """Baixa o conteúdo de uma URL."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read()


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
    e permite usar offline os Pokémon que já foram vistos.
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
        data = self._cached_json(
            f"{POKEMON_CACHE_DIR}/{number}.json",
            lambda: asdict(self._fetch_pokemon(number)),
        )
        return Pokemon(**data)

    def get_artwork(self, pokemon: Pokemon) -> bytes:
        return self._cache.get_or_create(
            f"artwork/{pokemon.number}.png",
            lambda: self._fetch(pokemon.artwork_url),
        )

    def _fetch_names(self) -> list[str]:
        data = self._fetch_json(f"{API_URL}/pokemon?limit={POKEDEX_SIZE}")
        return [format_name(item["name"]) for item in data["results"]]

    def _fetch_pokemon(self, number: int) -> Pokemon:
        return parse_pokemon(self._fetch_json(f"{API_URL}/pokemon/{number}"))

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _cached_json(self, name: str, create: Callable[[], Any]) -> Any:
        """Lê `name` do cache; se não existir, gera com `create` e salva.

        Guardamos só os campos usados: a resposta completa da API para
        um Pokémon tem cerca de 300 KB.
        """
        content = self._cache.get_or_create(
            name,
            lambda: json.dumps(create(), ensure_ascii=False).encode("utf-8"),
        )
        return json.loads(content)
