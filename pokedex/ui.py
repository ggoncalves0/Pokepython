"""Janela da Pokédex, com visual moderno feito com CustomTkinter."""

import tkinter as tk
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from io import BytesIO
from typing import NamedTuple

import customtkinter as ctk
from PIL import Image

from .models import PokedexEntry, Pokemon, PokemonRepository

APP_BACKGROUND = "#16171d"
SIDEBAR_COLOR = "#1f2029"
CARD_COLOR = "#262834"
HOVER_COLOR = "#323545"
TEXT_COLOR = "#f1f1f4"
MUTED_COLOR = "#9a9cb0"
DARK_TEXT_COLOR = "#1c1c1c"
WHITE = "#ffffff"
ERROR_COLOR = "#ff6b6b"

PASTEL_AMOUNT = 0.55  # quanto de branco entra na cor do tipo para o card
MUTED_AMOUNT = 0.35  # quanto o número no card se mistura com o fundo
ARTWORK_SIZE = 230
MAX_BASE_STAT = 255  # maior valor que um stat base pode ter nos jogos
CHECK_INTERVAL_MS = 50
CONNECTION_ERROR = "Sem conexão com a PokéAPI."


class TypeStyle(NamedTuple):
    label: str
    color: str


class ListRow(NamedTuple):
    """Linha clicável da lista: número em negrito e nome."""

    frame: ctk.CTkFrame
    number: ctk.CTkLabel
    name: ctk.CTkLabel
    search_text: str


TYPES = {
    "normal": TypeStyle("Normal", "#A8A77A"),
    "fire": TypeStyle("Fogo", "#EE8130"),
    "water": TypeStyle("Água", "#6390F0"),
    "electric": TypeStyle("Elétrico", "#F7D02C"),
    "grass": TypeStyle("Planta", "#7AC74C"),
    "ice": TypeStyle("Gelo", "#96D9D6"),
    "fighting": TypeStyle("Lutador", "#C22E28"),
    "poison": TypeStyle("Venenoso", "#A33EA1"),
    "ground": TypeStyle("Terrestre", "#E2BF65"),
    "flying": TypeStyle("Voador", "#A98FF3"),
    "psychic": TypeStyle("Psíquico", "#F95587"),
    "bug": TypeStyle("Inseto", "#A6B91A"),
    "rock": TypeStyle("Pedra", "#B6A136"),
    "ghost": TypeStyle("Fantasma", "#735797"),
    "dragon": TypeStyle("Dragão", "#6F35FC"),
    "dark": TypeStyle("Sombrio", "#705746"),
    "steel": TypeStyle("Aço", "#B7B7CE"),
    "fairy": TypeStyle("Fada", "#D685AD"),
}

STAT_NAMES = {
    "hp": "HP",
    "attack": "Ataque",
    "defense": "Defesa",
    "special-attack": "Ataque Esp.",
    "special-defense": "Defesa Esp.",
    "speed": "Velocidade",
}


def format_number(number: int) -> str:
    return f"#{number:03}"


def format_measure(value: float, unit: str) -> str:
    """Formata no padrão brasileiro: 6.0 vira "6,0 kg"."""
    return f"{value:.1f} {unit}".replace(".", ",")


def mix_colors(color: str, other: str, amount: float) -> str:
    """Mistura duas cores "#rrggbb"; `amount` é quanto entra de `other`."""
    channels = [
        round(int(color[i:i + 2], 16) * (1 - amount)
              + int(other[i:i + 2], 16) * amount)
        for i in (1, 3, 5)
    ]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def pastel(color: str) -> str:
    """Versão clara e suave da cor, misturada com branco."""
    return mix_colors(color, WHITE, PASTEL_AMOUNT)


def type_styles(pokemon: Pokemon) -> list[TypeStyle]:
    return [TYPES[name] for name in pokemon.types]


def stat_rows(pokemon: Pokemon) -> list[tuple[str, int]]:
    return [(label, pokemon.stats[name]) for name, label in STAT_NAMES.items()]


def ability_rows(pokemon: Pokemon) -> list[tuple[str, bool]]:
    """Habilidades na ordem de exibição, indicando qual é a oculta."""
    rows = [(name, False) for name in pokemon.abilities]
    if pokemon.hidden_ability:
        rows.append((pokemon.hidden_ability, True))
    return rows


def readable_text_color(background: str) -> str:
    """Escolhe texto claro ou escuro, o que contrastar mais com o fundo.

    Usa a luminância relativa da WCAG: acima de ~0,18 o texto escuro tem
    mais contraste que o branco.
    """
    channels = [int(background[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    red, green, blue = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        for c in channels
    ]
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return DARK_TEXT_COLOR if luminance > 0.18 else TEXT_COLOR


def clear(frame: tk.Misc) -> None:
    for child in frame.winfo_children():
        child.destroy()


class PokedexWindow:
    """Janela principal: detalhes à esquerda, busca e lista à direita."""

    def __init__(self, repository: PokemonRepository) -> None:
        ctk.set_appearance_mode("dark")
        self._root = ctk.CTk(fg_color=APP_BACKGROUND)
        self._repository = repository
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._rows: dict[int, ListRow] = {}
        self._selected: int | None = None
        self._pending: Future | None = None

        self._title_font = ctk.CTkFont(size=30, weight="bold")
        self._heading_font = ctk.CTkFont(size=17, weight="bold")
        self._body_font = ctk.CTkFont(size=14)
        self._bold_font = ctk.CTkFont(size=14, weight="bold")
        self._small_font = ctk.CTkFont(size=12, weight="bold")

        self._root.title("PokePython")
        self._root.geometry("920x680")
        self._root.minsize(920, 680)
        self._root.protocol("WM_DELETE_WINDOW", self._close)
        self._root.grid_columnconfigure(0, weight=1)
        self._root.grid_rowconfigure(0, weight=1)

        self._build_details()
        self._build_sidebar()
        self._set_status("Carregando a Pokédex...")
        self._run_in_background(repository.list_entries, self._show_entries)

    def run(self) -> None:
        self._root.mainloop()

    # --- Montagem da tela ---------------------------------------------

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(
            self._root, width=260, corner_radius=0, fg_color=SIDEBAR_COLOR
        )
        sidebar.grid(row=0, column=1, sticky="ns")
        sidebar.grid_rowconfigure(3, weight=1)

        title = self._label(sidebar, "Pokédex", self._title_font)
        title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 0))
        self._subtitle = self._label(sidebar, "", color=MUTED_COLOR)
        self._subtitle.grid(row=1, column=0, sticky="w", padx=20)

        self._search = ctk.CTkEntry(
            sidebar,
            placeholder_text="Buscar nome ou número",
            height=38,
            corner_radius=10,
            border_width=0,
            fg_color=CARD_COLOR,
            font=self._body_font,
        )
        self._search.grid(row=2, column=0, sticky="ew", padx=16, pady=16)
        self._search.bind("<KeyRelease>", self._apply_filter)

        self._list = ctk.CTkScrollableFrame(
            sidebar, width=210, fg_color="transparent"
        )
        self._list.grid(row=3, column=0, sticky="nsew", padx=8)
        self._list.grid_columnconfigure(0, weight=1)

        self._status = self._label(
            sidebar, "", color=MUTED_COLOR, wraplength=220, justify="left"
        )
        self._status.grid(row=4, column=0, sticky="w", padx=20, pady=12)

    def _build_details(self) -> None:
        details = ctk.CTkFrame(self._root, fg_color="transparent")
        details.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)
        details.grid_columnconfigure(0, weight=3, uniform="cards")
        details.grid_columnconfigure(1, weight=2, uniform="cards")
        details.grid_rowconfigure(2, weight=1)  # cards ocupam o espaço livre

        # Card em tom pastel da cor do tipo principal, com nome, número e
        # tipos no topo.
        self._hero = ctk.CTkFrame(
            details, corner_radius=24, fg_color=CARD_COLOR
        )
        self._hero.grid(row=0, column=0, columnspan=2, sticky="ew")
        header = self._container(self._hero)
        header.pack(fill="x", padx=24, pady=(18, 0))
        self._name = self._label(header, "", self._title_font)
        self._name.pack(side="left")
        self._number = self._label(header, "", self._heading_font)
        self._number.pack(side="left", padx=12, pady=(6, 0))
        self._badges = self._container(header)
        self._badges.pack(side="right")
        self._artwork = ctk.CTkLabel(
            self._hero, text="", width=ARTWORK_SIZE, height=ARTWORK_SIZE
        )
        self._artwork.pack(pady=(0, 16))

        # Esquerda: stats. Direita: habilidades e, embaixo, peso e altura.
        stats_card = self._card(details)
        stats_card.grid(
            row=1, column=0, rowspan=2, sticky="nsew",
            padx=(0, 8), pady=(14, 0),
        )
        self._build_stats(stats_card)

        abilities_card = self._card(details)
        abilities_card.grid(
            row=1, column=1, sticky="nsew", padx=(8, 0), pady=(14, 8)
        )
        abilities_title = self._label(
            abilities_card, "Habilidades", self._heading_font
        )
        abilities_title.pack(anchor="w", padx=20, pady=(16, 4))
        self._abilities = self._container(abilities_card)
        self._abilities.pack(fill="x", padx=20, pady=(0, 14))

        measures_card = self._card(details)
        measures_card.grid(row=2, column=1, sticky="nsew", padx=(8, 0))
        self._build_measures(measures_card)

    def _build_measures(self, card: ctk.CTkFrame) -> None:
        card.grid_columnconfigure(1, weight=1)
        title = self._label(card, "Medidas", self._heading_font)
        title.grid(
            row=0, column=0, columnspan=2, sticky="w", padx=20, pady=(16, 4)
        )
        self._measures: list[ctk.CTkLabel] = []
        for row, label in enumerate(("Altura", "Peso"), start=1):
            name = self._label(card, label, color=MUTED_COLOR)
            name.grid(row=row, column=0, sticky="w", padx=(20, 12))
            value = self._label(card, "", self._bold_font)
            value.grid(row=row, column=1, sticky="w", padx=(0, 20))
            self._measures.append(value)

    def _build_stats(self, card: ctk.CTkFrame) -> None:
        card.grid_columnconfigure(2, weight=1)
        title = self._label(card, "Stats base", self._heading_font)
        title.grid(
            row=0, column=0, columnspan=3, sticky="w", padx=20, pady=(16, 8)
        )

        # Cada linha: nome do stat, valor e barra (criadas uma vez só).
        self._stat_widgets: list[tuple[ctk.CTkLabel, ctk.CTkProgressBar]] = []
        for row, label in enumerate(STAT_NAMES.values(), start=1):
            name = self._label(card, label, color=MUTED_COLOR)
            name.grid(row=row, column=0, sticky="w", padx=(20, 8))
            value = self._label(card, "", self._bold_font, width=36)
            value.grid(row=row, column=1, sticky="e")
            bar = ctk.CTkProgressBar(
                card, height=8,
                fg_color=HOVER_COLOR, progress_color=HOVER_COLOR,
            )
            bar.set(0)
            bar.grid(row=row, column=2, sticky="ew", padx=(12, 20))
            self._stat_widgets.append((value, bar))

        total_row = len(STAT_NAMES) + 1
        total = self._label(card, "Total", self._bold_font)
        total.grid(row=total_row, column=0, sticky="w", padx=20, pady=(4, 16))
        self._total = self._label(card, "", self._bold_font, width=36)
        self._total.grid(row=total_row, column=1, sticky="e", pady=(4, 16))

    def _label(
        self,
        parent: tk.Misc,
        text: str,
        font: ctk.CTkFont | None = None,
        color: str = TEXT_COLOR,
        **options,
    ) -> ctk.CTkLabel:
        return ctk.CTkLabel(
            parent,
            text=text,
            font=font or self._body_font,
            text_color=color,
            anchor="w",
            **options,
        )

    def _pill(
        self, parent: tk.Misc, text: str, background: str
    ) -> ctk.CTkLabel:
        """Etiqueta arredondada, usada nos tipos e na habilidade oculta."""
        return ctk.CTkLabel(
            parent,
            text=text,
            font=self._small_font,
            fg_color=background,
            text_color=readable_text_color(background),
            corner_radius=12,
            height=26,
            padx=10,
        )

    @staticmethod
    def _card(parent: tk.Misc) -> ctk.CTkFrame:
        return ctk.CTkFrame(parent, corner_radius=18, fg_color=CARD_COLOR)

    @staticmethod
    def _container(parent: tk.Misc) -> ctk.CTkFrame:
        """Frame invisível que só agrupa widgets.

        Tamanho inicial zero: vazio, o padrão do CTkFrame (200x200)
        empurraria o resto da tela.
        """
        return ctk.CTkFrame(
            parent, width=0, height=0, fg_color="transparent"
        )

    # --- Lista e busca -------------------------------------------------

    def _show_entries(self, entries: list[PokedexEntry]) -> None:
        self._subtitle.configure(text=f"{len(entries)} Pokémon")
        for position, entry in enumerate(entries):
            row = self._make_row(entry)
            row.frame.grid(row=position, column=0, sticky="ew", pady=1)
            self._rows[entry.number] = row
        self._select(entries[0])

    def _make_row(self, entry: PokedexEntry) -> ListRow:
        # O CTkButton só aceita uma fonte para o texto todo; com dois
        # labels, o número pode ficar em negrito e o nome não.
        frame = ctk.CTkFrame(
            self._list, corner_radius=8, fg_color="transparent"
        )
        number_text = format_number(entry.number)
        number = self._label(frame, number_text, self._bold_font, width=44)
        number.pack(side="left", padx=(12, 6), pady=3)
        name = self._label(frame, entry.name)
        name.pack(side="left", pady=3)

        for widget in (frame, number, name):
            widget.configure(cursor="hand2")
            widget.bind(
                "<Button-1>", lambda _event, e=entry: self._select(e)
            )
            widget.bind(
                "<Enter>", lambda _event, n=entry.number: self._hover(n)
            )
            widget.bind(
                "<Leave>", lambda _event, n=entry.number: self._hover(n)
            )
        return ListRow(frame, number, name, f"{number_text} {entry.name}")

    def _hover(self, number: int) -> None:
        """Destaca a linha enquanto o mouse estiver sobre ela.

        Ao passar do fundo da linha para um dos textos, o Tk avisa que o
        mouse saiu da linha; por isso conferimos onde o mouse está de fato.
        """
        if number == self._selected:
            return
        frame = self._rows[number].frame
        x, y = self._root.winfo_pointerxy()
        under = str(self._root.winfo_containing(x, y))
        inside = under == str(frame) or under.startswith(f"{frame}.")
        frame.configure(fg_color=HOVER_COLOR if inside else "transparent")

    def _paint_row(
        self, number: int, background: str, text_color: str = TEXT_COLOR
    ) -> None:
        row = self._rows[number]
        row.frame.configure(fg_color=background)
        row.number.configure(text_color=text_color)
        row.name.configure(text_color=text_color)

    def _apply_filter(self, _event: tk.Event) -> None:
        query = self._search.get().strip().lower()
        for row in self._rows.values():
            if query in row.search_text.lower():
                row.frame.grid()  # volta para a mesma posição de antes
            else:
                row.frame.grid_remove()
        # Volta ao topo; senão, com a lista rolada, os resultados ficam fora
        # da vista. O CTkScrollableFrame não tem método público para isso.
        self._list._parent_canvas.yview_moveto(0)

    def _select(self, entry: PokedexEntry) -> None:
        if self._selected is not None:
            self._paint_row(self._selected, "transparent")
        self._selected = entry.number
        # Cinza enquanto carrega; ao terminar, ganha o pastel do card.
        self._paint_row(entry.number, HOVER_COLOR)
        self._load(entry)

    # --- Carregamento e exibição do Pokémon ----------------------------

    def _load(self, entry: PokedexEntry) -> None:
        if self._pending is not None:
            # Descarta o pedido anterior se ele ainda não começou.
            self._pending.cancel()
        self._set_status(f"Carregando {entry.name}...")
        self._pending = self._run_in_background(
            lambda: self._fetch(entry.number), self._show_pokemon
        )

    def _fetch(self, number: int) -> tuple[Pokemon, Image.Image]:
        """Roda fora da thread da interface: baixa dados e prepara a imagem."""
        pokemon = self._repository.get_pokemon(number)
        image = Image.open(BytesIO(self._repository.get_artwork(pokemon)))
        image.thumbnail((ARTWORK_SIZE, ARTWORK_SIZE))
        return pokemon, image

    def _show_pokemon(self, result: tuple[Pokemon, Image.Image]) -> None:
        pokemon, image = result
        color = type_styles(pokemon)[0].color
        background = pastel(color)
        text_color = readable_text_color(background)

        self._hero.configure(fg_color=background)
        self._artwork.configure(image=ctk.CTkImage(image, size=image.size))
        self._name.configure(text=pokemon.name, text_color=text_color)
        self._number.configure(
            text=format_number(pokemon.number),
            text_color=mix_colors(text_color, background, MUTED_AMOUNT),
        )
        if pokemon.number == self._selected:
            self._paint_row(pokemon.number, background, text_color)

        height_label, weight_label = self._measures
        height_label.configure(text=format_measure(pokemon.height, "m"))
        weight_label.configure(text=format_measure(pokemon.weight, "kg"))

        clear(self._badges)
        for style in type_styles(pokemon):
            badge = self._pill(self._badges, style.label, style.color)
            badge.pack(side="left", padx=(8, 0))

        stats = zip(self._stat_widgets, stat_rows(pokemon))
        for (value_label, bar), (_, value) in stats:
            value_label.configure(text=str(value))
            bar.configure(progress_color=color)
            bar.set(value / MAX_BASE_STAT)
        self._total.configure(text=str(pokemon.total))

        clear(self._abilities)
        for name, hidden in ability_rows(pokemon):
            row = ctk.CTkFrame(self._abilities, fg_color="transparent")
            row.pack(fill="x", pady=3)
            self._label(row, name).pack(side="left")
            if hidden:
                self._pill(row, "oculta", HOVER_COLOR).pack(
                    side="left", padx=8
                )
        self._set_status("")

    # --- Execução em segundo plano -------------------------------------

    def _run_in_background[T](
        self, task: Callable[[], T], on_success: Callable[[T], None]
    ) -> Future:
        """Executa `task` em outra thread para a janela não travar."""
        future = self._executor.submit(task)
        self._wait_for(future, on_success)
        return future

    def _wait_for[T](
        self, future: Future, on_success: Callable[[T], None]
    ) -> None:
        """Confere o resultado de tempos em tempos.

        O Tkinter não é thread-safe: só a thread da interface pode mexer
        nos widgets, por isso o resultado é tratado aqui, e não na thread
        que fez o download.
        """
        if not future.done():
            self._root.after(
                CHECK_INTERVAL_MS, self._wait_for, future, on_success
            )
            return
        if future.cancelled():
            return
        try:
            result = future.result()
        except (OSError, ValueError):  # sem rede, erro HTTP, JSON inválido
            self._set_status(CONNECTION_ERROR, ERROR_COLOR)
        else:
            on_success(result)

    def _set_status(self, text: str, color: str = MUTED_COLOR) -> None:
        self._status.configure(text=text, text_color=color)

    def _close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._root.destroy()
