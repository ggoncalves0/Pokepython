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
from pokedex.theme import (
    DARK_TEXT_COLOR,
    ELEVATED_COLOR,
    MIN_BAR_CONTRAST,
    MIN_TEXT_CONTRAST,
    TEXT_COLOR,
    TYPES,
    badge_text_color,
    bar_color,
    contrast_ratio,
    hero_number_color,
    mix_colors,
    pastel,
    readable_text_color,
)
from pokedex.ui import (
    ability_rows,
    bar_fraction,
    format_measure,
    stat_rows,
    type_styles,
)

ARTWORK_URL = "https://exemplo.com/25.png"

# Recorte da resposta real de https://pokeapi.co/api/v2/pokemon/25
PIKACHU_RESPONSE = {
    "id": 25,
    "name": "pikachu",
    "height": 4,
    "weight": 60,
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
        self.assertEqual(pikachu.height, 0.4)
        self.assertEqual(pikachu.weight, 6.0)


class DisplayTest(unittest.TestCase):
    def test_shows_types_stats_and_abilities_in_portuguese(self) -> None:
        pikachu = parse_pokemon(PIKACHU_RESPONSE)

        self.assertEqual(
            [style.label for style in type_styles(pikachu)], ["Elétrico"]
        )
        self.assertEqual(
            stat_rows(pikachu),
            [
                ("HP", 35),
                ("Ataque", 55),
                ("Defesa", 40),
                ("Ataque Esp.", 50),
                ("Defesa Esp.", 50),
                ("Velocidade", 90),
            ],
        )
        self.assertEqual(
            ability_rows(pikachu), [("Static", False), ("Lightning Rod", True)]
        )

    def test_bars_fill_at_180_and_stop_full(self) -> None:
        self.assertEqual(bar_fraction(45), 0.25)
        self.assertEqual(bar_fraction(180), 1)
        self.assertEqual(bar_fraction(250), 1)  # HP do Chansey

    def test_formats_measures_with_comma(self) -> None:
        self.assertEqual(format_measure(0.4, "m"), "0,4 m")
        self.assertEqual(format_measure(460.0, "kg"), "460,0 kg")

    def test_card_uses_pastel_of_type_color(self) -> None:
        self.assertEqual(mix_colors("#000000", "#ffffff", 0.5), "#808080")
        fire = pastel(TYPES["fire"].color)
        self.assertEqual(fire, "#f7c6a2")
        # Os tons pastel são claros: o texto sobre eles fica escuro.
        for style in TYPES.values():
            self.assertEqual(
                readable_text_color(pastel(style.color)), DARK_TEXT_COLOR
            )

    def test_text_contrasts_with_type_color(self) -> None:
        self.assertEqual(
            readable_text_color(TYPES["electric"].color), DARK_TEXT_COLOR
        )
        self.assertEqual(
            readable_text_color(TYPES["dragon"].color), TEXT_COLOR
        )


class ThemeTest(unittest.TestCase):
    # Tipos escuros: só neles o selo usa texto branco e a barra é clareada.
    DARK_TYPES = {"fighting", "poison", "ghost", "dragon", "dark"}

    def test_contrast_ratio_follows_wcag(self) -> None:
        self.assertAlmostEqual(contrast_ratio("#000000", "#ffffff"), 21)
        self.assertAlmostEqual(contrast_ratio("#ffffff", "#000000"), 21)
        self.assertAlmostEqual(contrast_ratio("#777777", "#777777"), 1)

    def test_every_type_meets_minimum_contrast(self) -> None:
        for name, style in TYPES.items():
            with self.subTest(tipo=name):
                background = pastel(style.color)
                for text in (
                    readable_text_color(background),
                    hero_number_color(background),
                ):
                    self.assertGreaterEqual(
                        contrast_ratio(text, background), MIN_TEXT_CONTRAST
                    )
                self.assertGreaterEqual(
                    contrast_ratio(badge_text_color(style.color), style.color),
                    MIN_TEXT_CONTRAST,
                )
                self.assertGreaterEqual(
                    contrast_ratio(bar_color(style.color), ELEVATED_COLOR),
                    MIN_BAR_CONTRAST,
                )

    def test_only_dark_types_get_white_badge_text_and_lighter_bars(
        self,
    ) -> None:
        for name, style in TYPES.items():
            with self.subTest(tipo=name):
                is_dark = name in self.DARK_TYPES
                self.assertEqual(
                    badge_text_color(style.color) == TEXT_COLOR, is_dark
                )
                self.assertEqual(bar_color(style.color) != style.color, is_dark)


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
