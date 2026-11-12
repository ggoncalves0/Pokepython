import json
import tempfile
import unittest
from pathlib import Path

from pokedex.cache import FileCache
from pokedex.models import PokedexEntry
from pokedex.pokeapi import (
    API_URL,
    ICON_URL,
    PokeApiRepository,
    format_name,
    parse_pokemon,
)
from pokedex.icons import (
    CURSOR,
    LIST_CAP_TOP,
    LIST_LINE,
    cursor_icon,
    in_line,
    list_symbol,
)
from pokedex.pixel import (
    FONT_FILES,
    FONTS_DIR,
    pixel_font_size,
    pixel_scale,
    render_title,
)
from pokedex.settings import DEFAULT_THEME, load_theme, save_theme
from pokedex.theme import (
    APP_BACKGROUND,
    BLACK,
    CONTRAST_STEP,
    DARK_TEXT_COLOR,
    ELEVATED_COLOR,
    LIGHT_TEXT_COLOR,
    MIN_BAR_CONTRAST,
    MIN_TEXT_CONTRAST,
    TYPES,
    WHITE,
    adjust_contrast,
    badge_text_color,
    bar_color,
    contrast_ratio,
    hero_border_color,
    hero_number_color,
    mix_colors,
    pastel,
    readable_text_color,
)
from pokedex.ui import (
    ability_rows,
    bar_fraction,
    format_measure,
    split_symbol,
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
            readable_text_color(TYPES["dragon"].color), LIGHT_TEXT_COLOR
        )


class ThemeTest(unittest.TestCase):
    # Tipos escuros: só neles o selo usa texto branco e a barra é clareada
    # no tema escuro. No claro, são os únicos que não escurecem.
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
                # Barras contra o trilho, em cada tema.
                for bar, track in zip(bar_color(style.color), ELEVATED_COLOR):
                    self.assertGreaterEqual(
                        contrast_ratio(bar, track), MIN_BAR_CONTRAST
                    )
                # No claro, o contorno separa o hero do fundo da janela.
                light_border, _ = hero_border_color(style.color)
                self.assertGreaterEqual(
                    contrast_ratio(light_border, APP_BACKGROUND[0]),
                    MIN_BAR_CONTRAST,
                )

    def test_dark_types_get_white_badge_text_and_keep_light_bars(
        self,
    ) -> None:
        for name, style in TYPES.items():
            with self.subTest(tipo=name):
                is_dark = name in self.DARK_TYPES
                self.assertEqual(
                    badge_text_color(style.color) == LIGHT_TEXT_COLOR, is_dark
                )
                light_bar, dark_bar = bar_color(style.color)
                self.assertEqual(light_bar == style.color, is_dark)
                self.assertEqual(dark_bar != style.color, is_dark)

    def test_adjust_contrast_keeps_color_that_already_passes(self) -> None:
        self.assertEqual(adjust_contrast("#C22E28", "#e4e7ef"), "#C22E28")

    def test_adjust_contrast_stops_at_first_step_that_passes(self) -> None:
        # Elétrico escurece no trilho claro; Dragão clareia no escuro.
        cases = (
            (TYPES["electric"].color, ELEVATED_COLOR[0], BLACK),
            (TYPES["dragon"].color, ELEVATED_COLOR[1], WHITE),
        )
        for color, background, target in cases:
            with self.subTest(cor=color, fundo=background):
                adjusted = adjust_contrast(color, background)
                self.assertGreaterEqual(
                    contrast_ratio(adjusted, background), MIN_BAR_CONTRAST
                )
                step = next(
                    s for s in range(1, 21)
                    if mix_colors(color, target, s * CONTRAST_STEP)
                    == adjusted
                )
                previous = mix_colors(color, target, (step - 1) * CONTRAST_STEP)
                self.assertLess(
                    contrast_ratio(previous, background), MIN_BAR_CONTRAST
                )

    def test_light_theme_darkens_electric_and_ice_by_40_percent(self) -> None:
        for name in ("electric", "ice"):
            color = TYPES[name].color
            self.assertEqual(
                bar_color(color)[0], mix_colors(color, BLACK, 0.40)
            )


class PixelFontTest(unittest.TestCase):
    def test_font_files_are_in_assets(self) -> None:
        for name in (*FONT_FILES, "OFL.txt"):
            self.assertTrue((FONTS_DIR / name).is_file(), name)

    def test_press_start_lands_on_multiples_of_8(self) -> None:
        for scaling in (1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5):
            for size in (16, 24):
                with self.subTest(escala=scaling, tamanho=size):
                    requested = pixel_font_size(size, scaling)
                    # O CustomTkinter arredonda tamanho × escala.
                    on_screen = round(requested * scaling)
                    self.assertEqual(on_screen % 8, 0)
                    # 250% é o único caso em que o múltiplo mais próximo
                    # não dá para alcançar com um tamanho inteiro.
                    limit = 12 if scaling == 2.5 else 4
                    self.assertLessEqual(
                        abs(on_screen - size * scaling), limit
                    )

    def test_ties_go_down_at_125_percent(self) -> None:
        # 16 × 1,25 = 20, no meio de 16 e 24: fica em 16.
        self.assertEqual(round(pixel_font_size(16, 1.25) * 1.25), 16)
        self.assertEqual(round(pixel_font_size(24, 1.25) * 1.25), 32)

    def test_pixel_art_follows_the_font(self) -> None:
        for scaling in (1.0, 1.25, 1.5, 2.5):
            for scale in (2, 3):
                with self.subTest(escala=scaling, fator=scale):
                    font = round(pixel_font_size(scale * 8, scaling) * scaling)
                    self.assertEqual(pixel_scale(scale, scaling) * 8, font)

    def test_keeps_size_at_100_percent(self) -> None:
        self.assertEqual(pixel_font_size(24, 1.0), 24)
        self.assertEqual(pixel_font_size(16, 1.0), 16)


class RenderTitleTest(unittest.TestCase):
    def test_title_has_only_ink_or_background(self) -> None:
        # Sem suavização: cada pixel é transparente ou da cor do texto.
        image = render_title("Pokédex #001", 16, "#1c1d26")
        self.assertEqual(image.height, 16)
        alphas = {alpha for *_, alpha in image.getdata()}
        self.assertEqual(alphas, {0, 255})


class PixelArtTest(unittest.TestCase):
    def test_splits_symbol_from_name(self) -> None:
        self.assertEqual(split_symbol("Nidoran♀"), ("Nidoran", "♀"))
        self.assertEqual(split_symbol("Nidoran♂"), ("Nidoran", "♂"))
        self.assertEqual(split_symbol("Mr. Mime"), ("Mr. Mime", None))
        self.assertEqual(split_symbol(""), ("", None))

    def test_in_line_pads_drawing_to_line_box(self) -> None:
        rows = in_line(["XX", "X."], height=5, top=1, left=1, right=2)
        self.assertEqual(
            rows, [".....", ".XX..", ".X...", ".....", "....."]
        )

    def test_drawings_fill_a_whole_text_line(self) -> None:
        # Com a altura da linha, o Tk alinha imagem e letras sozinho.
        self.assertEqual(
            cursor_icon("#000000").size, (len(CURSOR[0]), len(CURSOR))
        )
        for symbol in ("♀", "♂"):
            with self.subTest(simbolo=symbol):
                image = list_symbol(symbol, "#000000")
                self.assertEqual(image.height, LIST_LINE)
                # O desenho começa na altura das maiúsculas.
                self.assertEqual(image.getbbox()[1], LIST_CAP_TOP)


class SettingsTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_dir.cleanup)
        self.path = Path(temporary_dir.name) / "settings.json"

    def test_opens_light_without_saved_choice(self) -> None:
        self.assertEqual(load_theme(self.path), DEFAULT_THEME)
        self.assertEqual(DEFAULT_THEME, "light")

    def test_restores_saved_theme(self) -> None:
        save_theme(self.path, "light")
        self.assertEqual(load_theme(self.path), "light")

    def test_ignores_broken_file(self) -> None:
        for content in ("{", "[]", '{"theme": "roxo"}', '"dark"'):
            with self.subTest(conteudo=content):
                self.path.write_text(content, encoding="utf-8")
                self.assertEqual(load_theme(self.path), DEFAULT_THEME)


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
            ICON_URL.format(number=25): b"icone",
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

    def test_downloads_each_icon_only_once(self) -> None:
        for _ in range(2):
            repository = PokeApiRepository(self.cache, self.api)
            self.assertEqual(repository.get_icon(25), b"icone")

        self.assertEqual(self.api.requests, [ICON_URL.format(number=25)])


if __name__ == "__main__":
    unittest.main()
