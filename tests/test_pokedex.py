import json
import tempfile
import unittest
from pathlib import Path

from pokedex.cache import FileCache
from pokedex.models import PokedexEntry
from pokedex.pokeapi import (
    API_URL,
    PokeApiRepository,
    format_name,
    parse_pokemon,
)
from pokedex.ui import format_abilities, format_stats, format_types

ARTWORK_URL = "https://exemplo.com/25.png"

# Recorte da resposta real de https://pokeapi.co/api/v2/pokemon/25
PIKACHU_RESPONSE = {
    "id": 25,
    "name": "pikachu",
    "types": [{"slot": 1, "type": {"name": "electric"}}],
    "stats": [
        {"base_stat": 35, "stat": {"name": "hp"}},
        {"base_stat": 55, "stat": {"name": "attack"}},
        {"base_stat": 40, "stat": {"name": "defense"}},
        {"base_stat": 50, "stat": {"name": "special-attack"}},
        {"base_stat": 50, "stat": {"name": "special-defense"}},
        {"base_stat": 90, "stat": {"name": "speed"}},
    ],
    "abilities": [
        {"ability": {"name": "static"}, "is_hidden": False},
        {"ability": {"name": "lightning-rod"}, "is_hidden": True},
    ],
    "sprites": {"other": {"official-artwork": {"front_default": ARTWORK_URL}}},
}


class FakeApi:
    """Substitui a internet nos testes e anota cada URL pedida."""

    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses
        self.requests: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.requests.append(url)
        return self.responses[url]


class FormatNameTest(unittest.TestCase):
    def test_capitalizes_each_word(self) -> None:
        self.assertEqual(format_name("bulbasaur"), "Bulbasaur")
        self.assertEqual(format_name("lightning-rod"), "Lightning Rod")

    def test_uses_official_spelling_for_special_names(self) -> None:
        self.assertEqual(format_name("nidoran-f"), "Nidoran♀")
        self.assertEqual(format_name("mr-mime"), "Mr. Mime")
        self.assertEqual(format_name("farfetchd"), "Farfetch'd")


class ParsePokemonTest(unittest.TestCase):
    def test_converts_api_response(self) -> None:
        pikachu = parse_pokemon(PIKACHU_RESPONSE)

        self.assertEqual(pikachu.number, 25)
        self.assertEqual(pikachu.name, "Pikachu")
        self.assertEqual(pikachu.types, ["electric"])
        self.assertEqual(pikachu.stats["hp"], 35)
        self.assertEqual(pikachu.total, 320)
        self.assertEqual(pikachu.abilities, ["Static"])
        self.assertEqual(pikachu.hidden_ability, "Lightning Rod")
        self.assertEqual(pikachu.artwork_url, ARTWORK_URL)


class FormatForDisplayTest(unittest.TestCase):
    def test_shows_types_stats_and_abilities_in_portuguese(self) -> None:
        pikachu = parse_pokemon(PIKACHU_RESPONSE)

        self.assertEqual(format_types(pikachu), "Elétrico")
        self.assertEqual(
            format_stats(pikachu),
            "HP: 35\nAtaque: 55\nDefesa: 40\nAtaque Esp.: 50\n"
            "Defesa Esp.: 50\nVelocidade: 90\nTotal: 320",
        )
        self.assertEqual(
            format_abilities(pikachu), "Static\nLightning Rod (oculta)"
        )


class PokeApiRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_dir.cleanup)
        self.cache = FileCache(Path(temporary_dir.name))
        pokedex = {"results": [{"name": "bulbasaur"}, {"name": "ivysaur"}]}
        self.api = FakeApi({
            f"{API_URL}/pokemon?limit=151": json.dumps(pokedex).encode(),
            f"{API_URL}/pokemon/25": json.dumps(PIKACHU_RESPONSE).encode(),
            ARTWORK_URL: b"imagem",
        })

    def test_lists_entries_numbered_in_api_order(self) -> None:
        entries = PokeApiRepository(self.cache, self.api).list_entries()

        self.assertEqual(
            entries, [PokedexEntry(1, "Bulbasaur"), PokedexEntry(2, "Ivysaur")]
        )

    def test_downloads_each_resource_only_once(self) -> None:
        # Um repositório novo a cada volta simula abrir o programa de novo.
        for _ in range(2):
            repository = PokeApiRepository(self.cache, self.api)
            pikachu = repository.get_pokemon(25)
            self.assertEqual(repository.get_artwork(pikachu), b"imagem")

        self.assertEqual(pikachu, parse_pokemon(PIKACHU_RESPONSE))
        self.assertEqual(
            self.api.requests, [f"{API_URL}/pokemon/25", ARTWORK_URL]
        )


if __name__ == "__main__":
    unittest.main()
