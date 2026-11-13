"""Mede o desempenho da interface da Pokédex.

Uso:
    python scripts/benchmark_ui.py                # dados falsos, sem rede
    python scripts/benchmark_ui.py --primeiro-uso # PokéAPI de verdade,
                                                  # cache vazio temporário

Modo padrão (dados falsos: 151 Pokémon, sem rede):
- quantos widgets do CustomTkinter existem;
- tempo para montar a lista;
- tempo de ctk.set_appearance_mode até o fim de update_idletasks(), nos
  dois sentidos, e da troca pelo botão até a foto começar a esmaecer;
- tempo de filtrar ("char") e de limpar a busca.

Modo --primeiro-uso (rede de verdade, cache numa pasta temporária):
- tempo até a lista aparecer e até os 151 ícones aparecerem;
- tempo do clique até o card "Carregando..." e até o card completo, para
  Pokémon fora do cache e para um que já está no cache.

Os tempos usam time.perf_counter. Rode na mesma máquina antes e depois de
cada otimização. O script lê o settings.json, mas nunca o grava.
"""

import argparse
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import customtkinter as ctk  # noqa: E402
from customtkinter.windows.widgets.core_widget_classes import (  # noqa: E402
    CTkBaseClass,
)
from PIL import Image  # noqa: E402

from pokedex import ui  # noqa: E402
from pokedex.models import PokedexEntry, Pokemon  # noqa: E402
from pokedex.theme import TYPES  # noqa: E402

REPEAT = 5  # repetições de cada medida no modo padrão
FIRST_USE_TIMEOUT_S = 300
CLICK_SAMPLES = (150, 94, 6)  # Pokémon fora do cache no primeiro uso


# --- Dados falsos -----------------------------------------------------------

SYLLABLES = ("bul", "ba", "saur", "ivy", "pi", "ka", "chu", "mew", "ti", "ra")


def fake_name(number: int) -> str:
    """Nome falso, de tamanho variado. 4, 5 e 6 começam com "Char"."""
    if number in (4, 5, 6):
        return ("Charmander", "Charmeleon", "Charizard")[number - 4]
    parts = [SYLLABLES[(number * k) % len(SYLLABLES)] for k in (1, 3, 7)]
    return "".join(parts[: 2 + number % 2]).title()


def png(size: tuple[int, int], color: str) -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


class FakeRepository:
    """151 Pokémon inventados, sem rede e sem cache."""

    def __init__(self) -> None:
        self._artwork = png((475, 475), "#7ac74c")
        self._icon = png((40, 30), "#6390f0")
        self._types = list(TYPES)

    def list_entries(self) -> list[PokedexEntry]:
        return [PokedexEntry(n, fake_name(n)) for n in range(1, 152)]

    def get_pokemon(self, number: int) -> Pokemon:
        return Pokemon(
            number=number,
            name=fake_name(number),
            types=[self._types[number % len(self._types)]],
            stats={
                "hp": 45, "attack": 49, "defense": 49,
                "special-attack": 65, "special-defense": 65, "speed": 45,
            },
            abilities=["Overgrow"],
            hidden_ability="Chlorophyll",
            artwork_url="",
            height=0.7,
            weight=6.9,
        )

    def get_artwork(self, pokemon: Pokemon) -> bytes:
        return self._artwork

    def get_icon(self, number: int) -> bytes:
        return self._icon


# --- Ajudantes ---------------------------------------------------------------


def count_widgets(widget) -> tuple[int, int]:
    """(widgets do CustomTkinter, widgets do Tk no total), recursivo."""
    ctk_count = tk_count = 0
    for child in widget.winfo_children():
        tk_count += 1
        ctk_count += isinstance(child, CTkBaseClass)
        sub_ctk, sub_tk = count_widgets(child)
        ctk_count += sub_ctk
        tk_count += sub_tk
    return ctk_count, tk_count


def wait_until(root, condition: Callable[[], bool], timeout: float) -> bool:
    """Roda o laço do Tk até `condition` ser verdadeira ou estourar o tempo."""
    limit = time.perf_counter() + timeout
    while time.perf_counter() < limit:
        root.update()
        if condition():
            return True
        time.sleep(0.005)
    return False


def timed(action: Callable[[], None], root) -> tuple[float, float]:
    """Milissegundos de `action` até o fim de update_idletasks() e até o
    fim de update(), que também processa a pintura da janela no Windows."""
    start = time.perf_counter()
    action()
    root.update_idletasks()
    idle = (time.perf_counter() - start) * 1000
    root.update()
    return idle, (time.perf_counter() - start) * 1000


def summary(values: list[float]) -> str:
    return (
        f"{statistics.median(values):8.1f} ms  "
        f"(mín. {min(values):.1f}, máx. {max(values):.1f}, n={len(values)})"
    )


def summary_pair(pairs: list[tuple[float, float]]) -> str:
    idle = [first for first, _ in pairs]
    full = [second for _, second in pairs]
    return f"{summary(idle)} | com update(): {summary(full)}"


def open_window(repository) -> "ui.PokedexWindow":
    ui.save_theme = lambda *_: None  # a troca pelo botão não grava o tema
    window = ui.PokedexWindow(repository)
    window._root.geometry("+40+40")
    return window


# --- Modo padrão --------------------------------------------------------------


def benchmark_fake() -> None:
    build_times: list[float] = []
    original_show_entries = ui.PokedexWindow._show_entries

    def timed_show_entries(self, entries):
        start = time.perf_counter()
        original_show_entries(self, entries)
        self._root.update_idletasks()
        build_times.append((time.perf_counter() - start) * 1000)

    ui.PokedexWindow._show_entries = timed_show_entries
    window = open_window(FakeRepository())
    root = window._root
    try:
        assert wait_until(root, lambda: window._list.total == 151, 30)
        # Espera os ícones e o primeiro Pokémon, para medir com a tela pronta.
        wait_until(
            root,
            lambda: window._shown is not None
            and window._list.icon_count() == 151,
            30,
        )
        root.update()
        ctk_widgets, tk_widgets = count_widgets(root)
        list_ctk, list_tk = count_widgets(window._list.frame)

        to_dark, to_light, filter_times, clear_times = [], [], [], []
        button = []
        for _ in range(REPEAT):
            ctk.set_appearance_mode("light")
            root.update()
            to_dark.append(timed(lambda: ctk.set_appearance_mode("dark"), root))
            root.update()
            to_light.append(
                timed(lambda: ctk.set_appearance_mode("light"), root)
            )
            root.update()
            # Pelo botão: foto por cima, troca e começo do esmaecimento.
            button.append(timed(window._toggle_theme, root))
            wait_until(root, lambda: False, (ui.FADE_MS + 100) / 1000)

            window._search.delete(0, "end")
            window._search.insert(0, "char")
            filter_times.append(timed(window._apply_filter, root))
            shown = len(window._list.visible_numbers())
            root.update()
            clear_times.append(timed(window._clear_search, root))
            root.update()

        print("Benchmark da interface (dados falsos, 151 Pokémon, sem rede)")
        print(f"Python {sys.version.split()[0]}, CustomTkinter {ctk.__version__}")
        print()
        print(f"Widgets do CustomTkinter: {ctk_widgets} "
              f"({list_ctk} na lista)")
        print(f"Widgets do Tk no total:   {tk_widgets} ({list_tk} na lista)")
        print(f"Montar a lista:           {summary(build_times)}")
        print(f"Linhas da lista:          itens de um canvas só "
              f"({window._list.total} linhas)")
        print("Medida: até o fim de update_idletasks() | até o fim de update()")
        print(f"Tema claro -> escuro:     {summary_pair(to_dark)}")
        print(f"Tema escuro -> claro:     {summary_pair(to_light)}")
        print(f"Tema pelo botão:          {summary_pair(button)}")
        print(f"  (depois, a foto do tema antigo esmaece em {ui.FADE_MS} ms)")
        print(f"Filtrar \"char\" ({shown} res.): {summary_pair(filter_times)}")
        print(f"Limpar a busca:           {summary_pair(clear_times)}")
    finally:
        ui.PokedexWindow._show_entries = original_show_entries
        window._close()


# --- Modo primeiro uso ---------------------------------------------------------


def benchmark_first_use() -> None:
    from pokedex.cache import FileCache
    from pokedex.pokeapi import PokeApiRepository

    shown_at: dict[int, float] = {}
    loading_at: dict[int, float] = {}
    original_show_pokemon = ui.PokedexWindow._show_pokemon
    original_show_loading = ui.PokedexWindow._show_loading_card

    def timed_show_pokemon(self, result):
        original_show_pokemon(self, result)
        self._root.update_idletasks()
        shown_at[result[0].number] = time.perf_counter()

    def timed_show_loading(self, entry, message):
        original_show_loading(self, entry, message)
        self._root.update_idletasks()
        loading_at[entry.number] = time.perf_counter()

    ui.PokedexWindow._show_pokemon = timed_show_pokemon
    ui.PokedexWindow._show_loading_card = timed_show_loading
    with tempfile.TemporaryDirectory() as directory:
        start = time.perf_counter()
        window = open_window(PokeApiRepository(FileCache(Path(directory))))
        root = window._root
        try:
            listed = wait_until(
                root, lambda: window._list.total == 151, FIRST_USE_TIMEOUT_S
            )
            list_s = time.perf_counter() - start

            def icons_shown() -> int:
                return window._list.icon_count()

            first_icon_s = None
            limit = time.perf_counter() + FIRST_USE_TIMEOUT_S
            while time.perf_counter() < limit and icons_shown() < 151:
                root.update()
                if first_icon_s is None and icons_shown():
                    first_icon_s = time.perf_counter() - start
                time.sleep(0.005)
            all_icons_s = time.perf_counter() - start
            icons = icons_shown()

            clicks = []
            for number in (*CLICK_SAMPLES, CLICK_SAMPLES[0]):
                # O último repete o primeiro: já está no cache.
                entry = window._list.entry(number)
                before = time.perf_counter()
                window._select(entry)
                wait_until(
                    root,
                    lambda n=number, t=before: shown_at.get(n, 0) > t,
                    FIRST_USE_TIMEOUT_S,
                )
                loading = loading_at.get(number, 0)
                clicks.append((
                    number,
                    (loading - before) * 1000 if loading > before else None,
                    (shown_at[number] - before) * 1000,
                ))

            print("Benchmark do primeiro uso (PokéAPI de verdade, cache vazio)")
            print()
            print(f"Lista na tela:          {list_s:6.1f} s "
                  f"{'' if listed else '(estourou o tempo)'}")
            print(f"Primeiro ícone:         {first_icon_s or float('nan'):6.1f} s")
            print(f"Ícones na tela:         {icons} de 151 em {all_icons_s:.1f} s")
            for index, (number, loading_ms, ms) in enumerate(clicks):
                cached = index == len(clicks) - 1
                waiting = (
                    "sem card de espera" if loading_ms is None
                    else f'"Carregando..." em {loading_ms:.0f} ms'
                )
                print(f"Clique -> card #{number:03} "
                      f"({'em cache' if cached else 'sem cache'}): {ms:7.0f} ms"
                      f"  ({waiting})")
        finally:
            ui.PokedexWindow._show_pokemon = original_show_pokemon
            ui.PokedexWindow._show_loading_card = original_show_loading
            window._close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--primeiro-uso", action="store_true",
        help="mede com a PokéAPI de verdade e cache vazio",
    )
    if parser.parse_args().primeiro_uso:
        benchmark_first_use()
    else:
        benchmark_fake()


if __name__ == "__main__":
    main()
