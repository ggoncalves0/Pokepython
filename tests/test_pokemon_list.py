"""Testes da lista em canvas (pokedex/pokemon_list.py).

A regra do desenho dos cantos é pura. Os testes da lista abrem uma
janela de verdade, fora da tela; sem Tk, são pulados.
"""

import tkinter
import unittest

import customtkinter as ctk
from PIL import Image

from pokedex.models import PokedexEntry
from pokedex.pixel import PixelImage
from pokedex.pokemon_list import PokemonList, rounded_rect_bands


def cancel_pending_jobs(root: tkinter.Misc) -> None:
    """Cancela os after() pendentes, inclusive os internos do CustomTkinter.

    Sem isso, eles disparam depois que o teste fecha a janela e enchem a
    saída de "invalid command name".
    """
    for job in root.tk.splitlist(root.tk.call("after", "info")):
        root.after_cancel(job)


def covered(bands: list[tuple[int, int, int, int]], x: int, y: int) -> bool:
    return any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in bands)


class RoundedRectTest(unittest.TestCase):
    def test_corners_step_like_pixel_art(self) -> None:
        bands = rounded_rect_bands(0, 0, 20, 10, 4)
        # Primeira linha: recuo de 2 px; segunda: 1 px; depois, cheia.
        row_insets = []
        for y in range(4):
            first = next(x for x in range(20) if covered(bands, x, y))
            row_insets.append(first)
        self.assertEqual(row_insets, [2, 1, 0, 0])
        # Simétrico: a última linha tem o mesmo recuo da primeira.
        self.assertFalse(covered(bands, 1, 9))
        self.assertTrue(covered(bands, 2, 9))
        self.assertFalse(covered(bands, 18, 0))
        self.assertTrue(covered(bands, 17, 0))

    def test_radius_zero_is_one_rectangle(self) -> None:
        self.assertEqual(rounded_rect_bands(0, 0, 20, 10, 0), [(0, 0, 20, 10)])


ENTRIES = [
    PokedexEntry(1, "Bulbasaur"),
    PokedexEntry(4, "Charmander"),
    PokedexEntry(5, "Charmeleon"),
    PokedexEntry(29, "Nidoran♀"),
    PokedexEntry(25, "Pikachu"),
]


class PokemonListTest(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = ctk.CTk()
        except tkinter.TclError as error:
            self.skipTest(f"sem Tk: {error}")
        self.root.geometry("260x200+-3000+-3000")
        self.clicks: list[PokedexEntry] = []
        pixel = Image.new("RGBA", (4, 7), "#000000")
        self.list = PokemonList(
            self.root,
            number_font=ctk.CTkFont(size=18),
            name_font=ctk.CTkFont(size=24),
            message_font=ctk.CTkFont(size=18),
            split_name=lambda name: (
                (name[:-1], name[-1]) if name.endswith("♀") else (name, None)
            ),
            cursor_image=lambda _color: PixelImage(pixel, pixel),
            symbol_image=lambda _symbol, _color: PixelImage(pixel, pixel),
            on_click=self.clicks.append,
        )
        self.list.frame.pack(fill="both", expand=True)
        self.list.set_entries(ENTRIES)
        self.root.update()

    def tearDown(self) -> None:
        cancel_pending_jobs(self.root)
        self.root.destroy()

    def test_filter_by_name_or_number(self) -> None:
        self.assertEqual(self.list.filter("char"), 2)
        self.assertEqual(self.list.matching_numbers(), [4, 5])
        self.assertEqual(self.list.filter("#025"), 1)
        self.assertEqual(self.list.filter("xyz"), 0)
        self.assertEqual(self.list.filter(""), 5)
        self.assertEqual(self.list.matching_numbers(), [1, 4, 5, 29, 25])

    def test_click_selects_row_under_pointer(self) -> None:
        self.list.filter("char")
        second_row = self.list.row_pitch + self.list.row_pitch // 2
        self.list.click_at(second_row)
        self.assertEqual([entry.number for entry in self.clicks], [5])

    def test_click_on_empty_area_selects_nothing(self) -> None:
        self.list.filter("char")
        self.list.click_at(self.list.row_pitch * 3)
        self.assertEqual(self.clicks, [])

    def test_icons_arrive_later(self) -> None:
        self.assertEqual(self.list.icon_count(), 0)
        self.list.set_icon(25, Image.new("RGBA", (28, 24)))
        self.assertEqual(self.list.icon_count(), 1)


if __name__ == "__main__":
    unittest.main()
