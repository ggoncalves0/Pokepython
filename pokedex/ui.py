"""Janela da Pokédex, com visual moderno feito com CustomTkinter."""

import threading
import tkinter as tk
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial
from io import BytesIO
from pathlib import Path
from queue import Empty, Queue
from typing import NamedTuple

import customtkinter as ctk
from PIL import Image

from .icons import (
    TITLE_SYMBOLS,
    close_icon,
    cursor_icon,
    list_symbol,
    moon_icon,
    search_icon,
    sun_icon,
    title_symbol,
)
from .models import PokedexEntry, Pokemon, PokemonRepository
from .pixel import (
    PIXEL_GRID,
    TEXT_FAMILY,
    TITLE_FAMILY,
    PixelImage,
    fonts_available,
    load_pixel_fonts,
    pixel_font_size,
)
from .settings import load_theme, save_theme
from .theme import (
    APP_BACKGROUND,
    ARTWORK_MAX_SIZE,
    ARTWORK_MIN_SIZE,
    BAR_HEIGHT,
    BORDER_COLOR,
    BORDER_WIDTH,
    CARD_BORDER_COLOR,
    CARD_BORDER_WIDTH,
    CARD_COLOR,
    CARD_GAP,
    CARD_PADDING,
    CARD_RADIUS,
    CLEAR_BUTTON_SIZE,
    CLEAR_ICON_SIZE,
    CONTROL_PADDING,
    CONTROL_RADIUS,
    CURSOR_SCALE,
    CURSOR_X,
    ELEVATED_COLOR,
    ERROR_COLOR,
    FOCUS_BORDER_WIDTH,
    FONT_BADGE,
    FONT_BODY,
    FONT_HERO,
    FONT_LIST_NAME,
    FONT_LIST_NUMBER,
    FONT_TAG,
    FONT_TITLE,
    HERO_NUMBER_NUDGE,
    ICON_BUTTON_RADIUS,
    ICON_SIZE,
    ITEM_GAP,
    LABEL_HEIGHT,
    LIST_ICON_SIZE,
    LIST_TEXT_HEIGHT,
    LIST_WIDTH,
    MIN_WINDOW_SIZE,
    MUTED_COLOR,
    NUMBER_NUDGE,
    NUMBER_WIDTH,
    PILL_HEIGHT,
    PILL_PADDING,
    PILL_RADIUS,
    ROW_GAP,
    ROW_HEIGHT,
    ROW_RADIUS,
    SCROLLBAR_COLOR,
    SCROLLBAR_HOVER_COLOR,
    SCROLLBAR_WIDTH,
    SEARCH_HEIGHT,
    SIDEBAR_COLOR,
    SIDEBAR_WIDTH,
    STAT_VALUE_WIDTH,
    TEXT_COLOR,
    THEME_BUTTON_SIZE,
    TITLE_GAP,
    TYPES,
    WIDE_GAP,
    WINDOW_MARGIN,
    WINDOW_SIZE,
    ThemeColor,
    TypeStyle,
    badge_text_color,
    bar_color,
    hero_border_color,
    hero_number_color,
    pastel,
    readable_text_color,
)

# Valor que enche a barra. Quase todo stat base fica abaixo disso; os
# poucos acima (como o HP 250 do Chansey) enchem a barra, e o número ao
# lado mostra o valor exato. Com o máximo real (255), 45 e 65 pareciam
# quase iguais.
STAT_BAR_MAX = 180
CHECK_INTERVAL_MS = 50
STATUS_DELAY_MS = 300  # só avisa que está carregando se demorar
RESIZE_DELAY_MS = 60  # espera a janela parar de mudar antes de redesenhar
CONNECTION_ERROR = "Sem conexão com a PokéAPI."
NO_RESULTS = "Nenhum Pokémon encontrado"
# Um Pokémon tem no máximo 2 habilidades normais e 1 oculta. O card
# reserva sempre as 3 linhas, para não mudar de altura entre Pokémon.
MAX_ABILITIES = 3
PROJECT_DIR = Path(__file__).resolve().parent.parent
ICON_PATH = PROJECT_DIR / "assets" / "icon.ico"
# Miolo do ícone de 40 x 30 px, onde fica o Pokémon (LIST_ICON_SIZE).
LIST_ICON_CROP = (6, 4, 6 + LIST_ICON_SIZE[0], 4 + LIST_ICON_SIZE[1])
SETTINGS_PATH = PROJECT_DIR / "settings.json"  # tema escolhido


class ListRow(NamedTuple):
    """Linha clicável da lista: ícone, número, nome e, se houver, ♀/♂."""

    entry: PokedexEntry
    frame: ctk.CTkFrame
    number: ctk.CTkLabel
    name: ctk.CTkLabel
    icon: ctk.CTkLabel
    symbol: ctk.CTkLabel | None
    search_text: str


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


def type_styles(pokemon: Pokemon) -> list[TypeStyle]:
    return [TYPES[name] for name in pokemon.types]


def stat_rows(pokemon: Pokemon) -> list[tuple[str, int]]:
    return [(label, pokemon.stats[name]) for name, label in STAT_NAMES.items()]


def bar_fraction(value: int) -> float:
    """Quanto da barra de status fica preenchido, de 0 a 1."""
    return min(value / STAT_BAR_MAX, 1)


def ability_rows(pokemon: Pokemon) -> list[tuple[str, bool]]:
    """Habilidades na ordem de exibição, indicando qual é a oculta."""
    rows = [(name, False) for name in pokemon.abilities]
    if pokemon.hidden_ability:
        rows.append((pokemon.hidden_ability, True))
    return rows


def clear(frame: tk.Misc) -> None:
    for child in frame.winfo_children():
        child.destroy()


def split_symbol(name: str) -> tuple[str, str | None]:
    """Separa ♀/♂ do fim do nome: "Nidoran♀" vira ("Nidoran", "♀").

    As fontes pixeladas não têm esses caracteres; eles viram desenhos.
    """
    if name[-1:] in TITLE_SYMBOLS:
        return name[:-1], name[-1]
    return name, None


def pixel_image(
    draw: Callable[[str], Image.Image],
    color: str | ThemeColor,
    scale: int = 1,
    snap: bool = False,
) -> PixelImage:
    """Pixel art numa cor; com um par de cores, uma versão por tema."""
    light, dark = (color, color) if isinstance(color, str) else color
    return PixelImage(draw(light), draw(dark), scale, snap)


def themed_icon(
    draw: Callable[[str, int], Image.Image], color: ThemeColor, size: int
) -> ctk.CTkImage:
    """Ícone com uma versão para cada tema; o CTkImage troca sozinho."""
    light, dark = color
    return ctk.CTkImage(
        light_image=draw(light, size),
        dark_image=draw(dark, size),
        size=(size, size),
    )


class PokedexWindow:
    """Janela principal: detalhes à esquerda, busca e lista à direita."""

    def __init__(self, repository: PokemonRepository) -> None:
        # "system" (o padrão) segue o tema do Windows, inclusive se ele
        # mudar com o app aberto.
        ctk.set_appearance_mode(load_theme(SETTINGS_PATH))
        # As fontes precisam ser registradas antes de criar os widgets.
        fonts_loaded = load_pixel_fonts()
        self._root = ctk.CTk(fg_color=APP_BACKGROUND)
        self._pixel_fonts = fonts_loaded and fonts_available(self._root)
        self._repository = repository
        self._executor = ThreadPoolExecutor(max_workers=1)
        # Os ícones da lista vêm em outra fila, para não atrasar o Pokémon
        # escolhido; _closing interrompe o download ao fechar a janela.
        self._icon_executor = ThreadPoolExecutor(max_workers=1)
        self._closing = threading.Event()
        self._rows: dict[int, ListRow] = {}
        self._selected: int | None = None
        self._shown: int | None = None  # Pokémon exibido nos cards
        self._hovered: int | None = None  # linha sob o mouse
        # Fundo e texto da linha selecionada: cinza enquanto carrega, pastel
        # depois.
        self._selected_background: str | ThemeColor = ELEVATED_COLOR
        self._selected_text: str | ThemeColor = TEXT_COLOR
        self._list_focused = False
        self._pending: Future | None = None
        self._count_text = ""  # "151 Pokémon", depois que a lista chega
        self._query = ""  # busca aplicada à lista
        self._search_focused = False
        self._accent = MUTED_COLOR  # cor de destaque do tipo atual
        self._artwork_image: Image.Image | None = None  # arte original
        self._artwork_job: str | None = None
        self._status_job: str | None = None
        self._images: dict[tuple, PixelImage] = {}  # cursor, ♀ e ♂ por cor

        self._create_fonts()

        width, height = WINDOW_SIZE
        self._root.title("PokePython")
        self._root.geometry(f"{width}x{height}")
        self._root.minsize(*MIN_WINDOW_SIZE)
        self._set_window_icon()
        self._root.protocol("WM_DELETE_WINDOW", self._close)
        self._root.grid_columnconfigure(0, weight=1)
        self._root.grid_rowconfigure(0, weight=1)

        self._build_details()
        self._build_sidebar()
        # Teclado: setas trocam o Pokémon (com o foco na lista ou na busca)
        # e Ctrl+F leva à busca.
        self._root.bind("<Up>", lambda _event: self._move_selection(-1))
        self._root.bind("<Down>", lambda _event: self._move_selection(1))
        for key in ("<Control-f>", "<Control-F>"):
            self._root.bind(key, lambda _event: self._focus_search())
        self._show_status("Carregando a Pokédex...")
        self._run_in_background(repository.list_entries, self._show_entries)

    def run(self) -> None:
        self._root.mainloop()

    def _create_fonts(self) -> None:
        """Press Start 2P nos títulos, números e valores; Jersey 10 no resto.

        Se as fontes não carregarem, usa a fonte padrão do CustomTkinter,
        com títulos e selos em negrito.
        """
        if self._pixel_fonts:
            # As duas têm um peso só; um negrito falso borraria os pixels.
            title, text, weight = TITLE_FAMILY, TEXT_FAMILY, "normal"
        else:
            title, text, weight = None, None, "bold"
        self._hero_font = ctk.CTkFont(
            family=title, size=FONT_HERO, weight=weight
        )
        self._title_font = ctk.CTkFont(
            family=title, size=FONT_TITLE, weight=weight
        )
        self._list_number_font = ctk.CTkFont(
            family=text, size=FONT_LIST_NUMBER, weight=weight
        )
        self._body_font = ctk.CTkFont(family=text, size=FONT_BODY)
        self._list_name_font = ctk.CTkFont(family=text, size=FONT_LIST_NAME)
        self._badge_font = ctk.CTkFont(
            family=text, size=FONT_BADGE, weight=weight
        )
        self._tag_font = ctk.CTkFont(family=text, size=FONT_TAG, weight=weight)
        # Fontes da Press Start 2P e o tamanho de cada uma em 100%.
        self._grid_fonts = (
            (self._hero_font, FONT_HERO),
            (self._title_font, FONT_TITLE),
        )
        scaling = ctk.ScalingTracker.get_widget_scaling(self._root)
        self._snap_title_fonts(scaling)
        # Se a janela for para um monitor com outra escala, ajusta de novo.
        ctk.ScalingTracker.add_widget(self._snap_title_fonts, self._root)

    def _snap_title_fonts(self, widget_scaling: float, *_args) -> None:
        """Mantém a Press Start 2P em múltiplos de 8 px na tela."""
        for font, size in self._grid_fonts:
            font.configure(size=pixel_font_size(size, widget_scaling))

    def _split_name(self, name: str) -> tuple[str, str | None]:
        """Separa ♀/♂ do nome, se a fonte em uso não os tiver."""
        return split_symbol(name) if self._pixel_fonts else (name, None)

    def _cursor_image(self, color: str | ThemeColor) -> PixelImage:
        """▶ da linha selecionada, na cor do texto dela."""
        key = ("cursor", color)
        if key not in self._images:
            # Acompanha o nome da lista (Jersey 10), que segue a escala
            # exata da tela.
            self._images[key] = pixel_image(cursor_icon, color, CURSOR_SCALE)
        return self._images[key]

    def _symbol_image(
        self, symbol: str, color: str | ThemeColor, title: bool
    ) -> PixelImage:
        """♀ ou ♂ na cor do nome: no card principal (title) ou na lista."""
        key = (symbol, color, title)
        if key not in self._images:
            if title:
                self._images[key] = pixel_image(
                    partial(title_symbol, symbol), color,
                    FONT_HERO // PIXEL_GRID, snap=True,
                )
            else:  # desenhado para os nomes da lista (FONT_LIST_NAME)
                self._images[key] = pixel_image(
                    partial(list_symbol, symbol), color
                )
        return self._images[key]

    # --- Montagem da tela ---------------------------------------------

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(
            self._root, width=SIDEBAR_WIDTH, corner_radius=0,
            fg_color=SIDEBAR_COLOR,
        )
        sidebar.grid(row=0, column=1, sticky="ns")
        sidebar.grid_propagate(False)  # largura fixa, veja SIDEBAR_WIDTH
        sidebar.grid_rowconfigure(3, weight=1)
        sidebar.grid_columnconfigure(0, weight=1)

        # Título, busca e lista começam na mesma borda esquerda; o botão de
        # tema termina na mesma borda direita da busca.
        header = self._container(sidebar)
        header.grid(
            row=0, column=0, sticky="ew",
            padx=WINDOW_MARGIN, pady=(WINDOW_MARGIN, 0),
        )
        # Menor que o nome do Pokémon, para não disputar atenção com ele.
        title = self._label(header, "Pokédex", self._title_font)
        title.pack(side="left")
        self._build_theme_button(header).pack(side="right")
        # Mostra quantos Pokémon há e, quando preciso, avisos de
        # carregamento ou de erro.
        self._status = self._label(
            sidebar, "", color=MUTED_COLOR, wraplength=LIST_WIDTH,
            justify="left",
        )
        self._status.grid(row=1, column=0, sticky="w", padx=WINDOW_MARGIN)

        self._search_box = self._build_search(sidebar)
        self._search_box.grid(
            row=2, column=0, sticky="ew", padx=WINDOW_MARGIN, pady=CARD_GAP
        )

        # Sem canto arredondado: com ele, o CTkScrollableFrame recua o
        # conteúdo e as linhas saem do alinhamento com a busca.
        self._list = ctk.CTkScrollableFrame(
            sidebar, width=LIST_WIDTH, corner_radius=0,
            fg_color="transparent",
            scrollbar_button_color=SCROLLBAR_COLOR,
            scrollbar_button_hover_color=SCROLLBAR_HOVER_COLOR,
        )
        self._list.grid(
            row=3, column=0, sticky="nsew",
            padx=WINDOW_MARGIN, pady=(0, WINDOW_MARGIN),
        )
        self._list.grid_columnconfigure(0, weight=1)
        self._list._scrollbar.configure(width=SCROLLBAR_WIDTH)
        # A lista recebe o foco com um clique numa linha ou com Tab. Com
        # foco, a linha selecionada ganha um anel na cor do tipo.
        tk.Frame.configure(self._list, takefocus=True)
        self._list.bind("<FocusIn>", lambda _event: self._set_list_focus(True))
        self._list.bind(
            "<FocusOut>", lambda _event: self._set_list_focus(False)
        )
        # A barra de rolagem some quando a lista cabe inteira. Confere de
        # novo quando muda o conteúdo (busca) ou a altura (janela).
        self._list.bind("<Configure>", self._update_scrollbar, add="+")
        self._list._parent_canvas.bind(
            "<Configure>", self._update_scrollbar, add="+"
        )
        self._no_results = self._label(
            self._list, NO_RESULTS, color=MUTED_COLOR,
            wraplength=LIST_WIDTH, justify="left",
        )
        # Cursor ▶ da linha selecionada. É um só: _paint_row o coloca na
        # linha da vez, no recuo à esquerda do número.
        self._cursor = ctk.CTkLabel(self._list, text="", width=0, height=0)
        self._cursor.configure(cursor="hand2")
        self._cursor.bind("<Button-1>", lambda _event: self._list.focus_set())

    def _build_theme_button(self, parent: ctk.CTkFrame) -> ctk.CTkButton:
        """Botão que alterna entre os temas claro e escuro.

        O ícone mostra para onde o clique leva: lua no tema claro, sol no
        escuro. O CTkImage troca de versão sozinho quando o tema muda.
        """
        light, dark = MUTED_COLOR
        return ctk.CTkButton(
            parent,
            text="",
            image=PixelImage(moon_icon(light), sun_icon(dark)),
            width=THEME_BUTTON_SIZE,
            height=THEME_BUTTON_SIZE,
            corner_radius=ICON_BUTTON_RADIUS,
            fg_color="transparent",
            hover_color=ELEVATED_COLOR,
            command=self._toggle_theme,
        )

    def _build_search(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        """Campo de busca com lupa, borda de foco e botão para limpar.

        O CTkEntry não aceita ícone; por isso uma moldura com borda leva
        a lupa, o campo e o "×" lado a lado.
        """
        box = ctk.CTkFrame(
            parent,
            width=LIST_WIDTH,
            height=SEARCH_HEIGHT,
            corner_radius=CONTROL_RADIUS,
            fg_color=CARD_COLOR,
            border_width=BORDER_WIDTH,
            border_color=BORDER_COLOR,
        )
        box.grid_propagate(False)  # mesma altura com borda de 1 ou 2 px
        box.grid_rowconfigure(0, weight=1)
        box.grid_columnconfigure(1, weight=1)

        icon = ctk.CTkLabel(
            box,
            text="",
            image=themed_icon(search_icon, MUTED_COLOR, ICON_SIZE),
            width=ICON_SIZE,
            height=ICON_SIZE,
        )
        icon.grid(row=0, column=0, padx=(CONTROL_PADDING, ITEM_GAP // 2))

        self._search = ctk.CTkEntry(
            box,
            placeholder_text="Nome ou número",  # a lupa já indica a busca
            placeholder_text_color=MUTED_COLOR,
            text_color=TEXT_COLOR,
            fg_color=CARD_COLOR,
            border_width=0,
            corner_radius=0,
            font=self._body_font,
        )
        # Recuo à direita: sem ele, com o "×" escondido, o fundo do campo
        # cobriria a borda arredondada da moldura.
        self._search.grid(row=0, column=1, sticky="ew", padx=(0, ITEM_GAP))

        self._clear_button = ctk.CTkButton(
            box,
            text="",
            image=themed_icon(close_icon, MUTED_COLOR, CLEAR_ICON_SIZE),
            width=CLEAR_BUTTON_SIZE,
            height=CLEAR_BUTTON_SIZE,
            corner_radius=ICON_BUTTON_RADIUS,
            fg_color="transparent",
            hover_color=ELEVATED_COLOR,
            command=self._clear_search,
        )
        self._clear_button.grid(row=0, column=2, padx=(0, ITEM_GAP))
        self._clear_button.grid_remove()  # só aparece quando há texto

        # Clicar na lupa ou na moldura também leva ao campo.
        for widget in (box, icon):
            widget.bind("<Button-1>", lambda _event: self._search.focus_set())
        self._search.bind("<KeyRelease>", self._apply_filter)
        self._search.bind("<Escape>", lambda _event: self._clear_search())
        for key in ("<Return>", "<KP_Enter>"):
            self._search.bind(key, lambda _event: self._open_first_result())
        self._search.bind(
            "<FocusIn>", lambda _event: self._paint_search_border(True)
        )
        self._search.bind(
            "<FocusOut>", lambda _event: self._paint_search_border(False)
        )
        return box

    def _build_details(self) -> None:
        details = ctk.CTkFrame(self._root, fg_color="transparent")
        details.grid(
            row=0, column=0, sticky="nsew",
            padx=WINDOW_MARGIN, pady=WINDOW_MARGIN,
        )
        details.grid_columnconfigure(0, weight=3, uniform="cards")
        details.grid_columnconfigure(1, weight=2, uniform="cards")
        # A altura que sobra vai para o hero; os cards de baixo ficam com a
        # altura do próprio conteúdo.
        details.grid_rowconfigure(0, weight=1)

        # Card em tom pastel da cor do tipo principal, com nome, número e
        # tipos no topo. O contorno aparece só no tema claro (veja
        # hero_border_color).
        self._hero = ctk.CTkFrame(
            details, corner_radius=CARD_RADIUS, fg_color=CARD_COLOR,
            border_width=CARD_BORDER_WIDTH, border_color=CARD_BORDER_COLOR,
        )
        self._hero.grid(row=0, column=0, columnspan=2, sticky="nsew")
        header = self._container(self._hero)
        header.pack(fill="x", padx=CARD_PADDING, pady=(CARD_PADDING, 0))
        self._name = self._label(header, "", self._hero_font)
        self._name.pack(side="left")
        # ♀ ou ♂ em pixel art, logo depois do nome; só aparece nos Nidoran.
        self._name_symbol = ctk.CTkLabel(header, text="", width=0, height=0)
        self._number = self._label(header, "", self._title_font)
        self._number.pack(
            side="left", padx=WIDE_GAP, pady=(HERO_NUMBER_NUDGE, 0)
        )
        self._badges = self._container(header)
        self._badges.pack(side="right")
        # A área da arte ocupa o resto do hero. A arte fica centralizada
        # com place(), que não muda o tamanho da área: assim ela pode
        # acompanhar o hero sem empurrar o layout.
        self._art_area = ctk.CTkFrame(
            self._hero,
            width=ARTWORK_MIN_SIZE,
            height=ARTWORK_MIN_SIZE,
            fg_color="transparent",
        )
        self._art_area.pack(
            fill="both", expand=True,
            padx=CARD_PADDING, pady=(0, CARD_PADDING),
        )
        self._artwork = ctk.CTkLabel(
            self._art_area, text="", width=0, height=0
        )
        self._artwork.place(relx=0.5, rely=0.5, anchor="center")
        self._art_area.bind("<Configure>", self._schedule_artwork_resize)

        # Esquerda: status. Direita: habilidades e, embaixo, peso e altura.
        half_gap = CARD_GAP // 2
        stats_card = self._card(details)
        stats_card.grid(
            row=1, column=0, sticky="nsew",
            padx=(0, half_gap), pady=(CARD_GAP, 0),
        )
        self._build_stats(stats_card)

        right_column = self._container(details)
        right_column.grid(
            row=1, column=1, sticky="nsew",
            padx=(half_gap, 0), pady=(CARD_GAP, 0),
        )
        abilities_card = self._card(right_column)
        abilities_card.pack(fill="x")
        self._card_title(abilities_card, "Habilidades").pack(
            anchor="w", padx=CARD_PADDING, pady=(CARD_PADDING, TITLE_GAP)
        )
        abilities = self._container(abilities_card)
        abilities.pack(fill="x", padx=CARD_PADDING, pady=(0, CARD_PADDING))
        # Linhas fixas: com menos habilidades, as de baixo ficam vazias e a
        # sobra aparece no fim do card, sem mexer no resto da tela.
        self._ability_rows: list[tuple[ctk.CTkLabel, ctk.CTkLabel]] = []
        for _ in range(MAX_ABILITIES):
            row = self._container(abilities)
            row.pack(fill="x")
            name = self._label(row, "")
            name.pack(side="left")
            # Rótulo simples, sem fundo: um selo arredondado parecia um
            # botão. Só aparece na habilidade oculta.
            tag = self._label(row, "OCULTA", self._tag_font, MUTED_COLOR)
            self._ability_rows.append((name, tag))

        # Medidas tem sempre o mesmo conteúdo, logo a mesma altura.
        measures_card = self._card(right_column)
        measures_card.pack(fill="x", pady=(CARD_GAP, 0))
        self._build_measures(measures_card)

    def _build_measures(self, card: ctk.CTkFrame) -> None:
        card.grid_columnconfigure(1, weight=1)
        self._card_title(card, "Medidas").grid(
            row=0, column=0, columnspan=2, sticky="w",
            padx=CARD_PADDING, pady=(CARD_PADDING, TITLE_GAP),
        )
        labels = ("Altura", "Peso")
        self._measures: list[ctk.CTkLabel] = []
        for row, label in enumerate(labels, start=1):
            bottom = CARD_PADDING if row == len(labels) else 0
            name = self._label(card, label, color=MUTED_COLOR)
            name.grid(
                row=row, column=0, sticky="w",
                padx=(CARD_PADDING, WIDE_GAP), pady=(0, bottom),
            )
            value = self._value_label(card)
            value.grid(
                row=row, column=1, sticky="w",
                padx=(0, CARD_PADDING), pady=(NUMBER_NUDGE, bottom),
            )
            self._measures.append(value)

    def _build_stats(self, card: ctk.CTkFrame) -> None:
        card.grid_columnconfigure(2, weight=1)
        self._card_title(card, "Status base").grid(
            row=0, column=0, columnspan=3, sticky="w",
            padx=CARD_PADDING, pady=(CARD_PADDING, TITLE_GAP),
        )

        # Cada linha: nome do stat, valor e barra (criadas uma vez só).
        self._stat_widgets: list[tuple[ctk.CTkLabel, ctk.CTkProgressBar]] = []
        for row, label in enumerate(STAT_NAMES.values(), start=1):
            name = self._label(card, label, color=MUTED_COLOR)
            name.grid(
                row=row, column=0, sticky="w", padx=(CARD_PADDING, ITEM_GAP)
            )
            value = self._value_label(card, width=STAT_VALUE_WIDTH)
            value.grid(row=row, column=1, sticky="e", pady=(NUMBER_NUDGE, 0))
            bar = ctk.CTkProgressBar(
                card, height=BAR_HEIGHT,
                fg_color=ELEVATED_COLOR, progress_color=ELEVATED_COLOR,
            )
            bar.set(0)
            bar.grid(
                row=row, column=2, sticky="ew", padx=(WIDE_GAP, CARD_PADDING)
            )
            self._stat_widgets.append((value, bar))

        divider_row = len(STAT_NAMES) + 1
        # O desenho padrão do CustomTkinter no Windows (com fontes) não pinta
        # formas de 1 px; com polígonos a linha aparece.
        divider = ctk.CTkFrame(
            card, height=1, corner_radius=0, fg_color=ELEVATED_COLOR,
            overwrite_preferred_drawing_method="polygon_shapes",
        )
        divider.grid(
            row=divider_row, column=0, columnspan=3, sticky="ew",
            padx=CARD_PADDING, pady=ITEM_GAP // 2,
        )

        total_row = divider_row + 1
        # Rótulo e valor na mesma fonte: aqui não há linha de base a acertar.
        total = self._label(card, "Total", self._title_font)
        total.grid(
            row=total_row, column=0, sticky="w",
            padx=(CARD_PADDING, ITEM_GAP), pady=(0, CARD_PADDING),
        )
        self._total = self._label(
            card, "", self._title_font, width=STAT_VALUE_WIDTH
        )
        self._total.grid(
            row=total_row, column=1, sticky="e", pady=(0, CARD_PADDING)
        )

    def _value_label(self, parent: tk.Misc, **options) -> ctk.CTkLabel:
        """Valor de status ou medida, em Press Start 2P.

        Fica NUMBER_NUDGE px mais baixo que o rótulo ao lado, para as linhas
        de base baterem; no grid, use pady=(NUMBER_NUDGE, ...). Com a altura
        reduzida na mesma medida, o passo das linhas continua o mesmo.
        """
        return self._label(
            parent, "", self._title_font,
            height=LABEL_HEIGHT - NUMBER_NUDGE, **options,
        )

    def _card_title(self, card: ctk.CTkFrame, text: str) -> ctk.CTkLabel:
        return self._label(card, text, self._title_font)

    def _label(
        self,
        parent: tk.Misc,
        text: str,
        font: ctk.CTkFont | None = None,
        color: str | ThemeColor = TEXT_COLOR,
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

    def _type_badge(
        self, parent: tk.Misc, style: TypeStyle
    ) -> ctk.CTkLabel:
        """Selo arredondado com o nome do tipo, na cor dele."""
        return ctk.CTkLabel(
            parent,
            text=style.label,
            font=self._badge_font,
            fg_color=style.color,
            text_color=badge_text_color(style.color),
            corner_radius=PILL_RADIUS,
            height=PILL_HEIGHT,
            padx=PILL_PADDING,
        )

    @staticmethod
    def _card(parent: tk.Misc) -> ctk.CTkFrame:
        return ctk.CTkFrame(
            parent, corner_radius=CARD_RADIUS, fg_color=CARD_COLOR,
            border_width=CARD_BORDER_WIDTH, border_color=CARD_BORDER_COLOR,
        )

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
        for position, entry in enumerate(entries):
            row = self._make_row(entry)
            row.frame.grid(
                row=position, column=0, sticky="ew", pady=(0, ROW_GAP)
            )
            self._rows[entry.number] = row
        # Aviso de busca sem resultado, logo abaixo das linhas (que somem).
        self._no_results.grid(
            row=len(entries), column=0, sticky="w", padx=CONTROL_PADDING
        )
        self._no_results.grid_remove()
        self._show_count(len(entries))
        self._select(entries[0])
        self._load_icons(entries)

    def _load_icons(self, entries: Iterable[PokedexEntry]) -> None:
        """Baixa os ícones da lista em segundo plano, em ordem.

        Cada ícone aparece assim que chega. Sem conexão, para no primeiro
        erro: as linhas ficam sem ícone até a próxima vez que o app abrir.
        """
        arrived: Queue[tuple[int, bytes] | None] = Queue()

        def download_all() -> None:
            for entry in entries:
                if self._closing.is_set():
                    break
                try:
                    arrived.put((entry.number, self._repository.get_icon(
                        entry.number
                    )))
                except OSError:  # sem rede ou erro HTTP
                    break
            arrived.put(None)  # acabou

        self._icon_executor.submit(download_all)
        self._show_icons(arrived)

    def _show_icons(self, arrived: Queue) -> None:
        """Põe na lista os ícones que já chegaram e confere de novo depois."""
        while True:
            try:
                item = arrived.get_nowait()
            except Empty:
                break
            if item is None:
                return
            number, data = item
            try:
                image = Image.open(BytesIO(data)).convert("RGBA")
            except OSError:
                continue  # arquivo estragado: a linha fica sem ícone
            image = image.crop(LIST_ICON_CROP)
            self._rows[number].icon.configure(image=PixelImage(image, image))
        self._root.after(CHECK_INTERVAL_MS, self._show_icons, arrived)

    def _show_count(self, shown: int) -> None:
        """"151 Pokémon" sem busca; "2 de 151" durante a busca."""
        total = len(self._rows)
        self._count_text = (
            f"{shown} de {total}" if self._query else f"{total} Pokémon"
        )
        self._show_status(self._count_text)

    def _update_scrollbar(self, _event: tk.Event | None = None) -> None:
        """Mostra a barra de rolagem só quando a lista não cabe inteira."""
        # O CTkScrollableFrame não tem acesso público à barra.
        scrollbar = self._list._scrollbar
        visible_height = self._list._parent_canvas.winfo_height()
        fits = self._list.winfo_reqheight() <= visible_height
        if fits and scrollbar.winfo_manager():
            scrollbar.grid_remove()
        elif not fits and not scrollbar.winfo_manager():
            scrollbar.grid()

    def _make_row(self, entry: PokedexEntry) -> ListRow:
        # O CTkButton só aceita uma fonte para o texto todo; com dois
        # labels, o número e o nome podem ter fontes diferentes.
        frame = ctk.CTkFrame(
            self._list, corner_radius=ROW_RADIUS, fg_color="transparent"
        )
        # Textos mais baixos que a linha, para não cobrirem o anel de foco
        # desenhado na borda dela.
        inset = (ROW_HEIGHT - LIST_TEXT_HEIGHT) // 2
        # Mini foto, número e nome. A foto começa alinhada com a lupa da
        # busca; o cursor ▶ fica no recuo antes dela. Até o ícone chegar,
        # o espaço fica vazio, do mesmo tamanho.
        icon_width, icon_height = LIST_ICON_SIZE
        icon = ctk.CTkLabel(
            frame, text="", width=icon_width, height=icon_height
        )
        icon.pack(side="left", padx=(CONTROL_PADDING, ITEM_GAP // 2))
        number_text = format_number(entry.number)
        number = self._label(
            frame, number_text, self._list_number_font,
            width=NUMBER_WIDTH, height=LIST_TEXT_HEIGHT,
        )
        number.pack(side="left", padx=(0, ITEM_GAP), pady=inset)
        name_text, symbol_char = self._split_name(entry.name)
        name = self._label(
            frame, name_text, self._list_name_font, height=LIST_TEXT_HEIGHT
        )
        name.pack(side="left", pady=inset)
        widgets = [frame, icon, number, name]
        symbol = None
        if symbol_char is not None:
            symbol = ctk.CTkLabel(
                frame, text="", width=0, height=0,
                image=self._symbol_image(symbol_char, TEXT_COLOR, False),
            )
            symbol.pack(side="left")
            widgets.append(symbol)

        for widget in widgets:
            widget.configure(cursor="hand2")
            widget.bind(
                "<Button-1>", lambda _event, e=entry: self._click_row(e)
            )
            widget.bind(
                "<Enter>", lambda _event, n=entry.number: self._hover(n)
            )
            widget.bind(
                "<Leave>", lambda _event, n=entry.number: self._hover(n)
            )
        search_text = f"{number_text} {entry.name}".lower()
        return ListRow(
            entry, frame, number, name, icon, symbol, search_text
        )

    def _click_row(self, entry: PokedexEntry) -> None:
        self._list.focus_set()  # as setas seguem daqui, com anel de foco
        self._select(entry)

    def _hover(self, number: int) -> None:
        """Destaca a linha enquanto o mouse estiver sobre ela.

        Ao passar do fundo da linha para um dos textos, o Tk avisa que o
        mouse saiu da linha; por isso conferimos onde o mouse está de fato.
        """
        frame = self._rows[number].frame
        x, y = self._root.winfo_pointerxy()
        under = str(self._root.winfo_containing(x, y))
        if under == str(frame) or under.startswith(f"{frame}."):
            self._hovered = number
        elif self._hovered == number:
            self._hovered = None
        self._paint_row(number)

    def _paint_row(self, number: int) -> None:
        """Pinta a linha conforme o estado: selecionada, sob o mouse ou não.

        A selecionada usa o pastel do Pokémon (cinza enquanto carrega) e o
        cursor ▶, que a marca mesmo quando o pastel quase some no tema
        claro. Com a lista em foco, ganha um anel de 2 px na cor do tipo.
        """
        row = self._rows[number]
        border = 0
        background, text_color = "transparent", TEXT_COLOR
        if number == self._selected:
            background = self._selected_background
            text_color = self._selected_text
            if self._list_focused:
                border = FOCUS_BORDER_WIDTH
            self._place_cursor(row, background, text_color)
        elif number == self._hovered:
            background = ELEVATED_COLOR
        row.frame.configure(
            fg_color=background, border_width=border,
            border_color=self._accent,
        )
        row.number.configure(text_color=text_color)
        row.name.configure(text_color=text_color)
        if row.symbol is not None:
            symbol = split_symbol(row.entry.name)[1]
            row.symbol.configure(
                image=self._symbol_image(symbol, text_color, False)
            )

    def _place_cursor(
        self,
        row: ListRow,
        background: str | ThemeColor,
        color: str | ThemeColor,
    ) -> None:
        """Põe o cursor ▶ na linha, centralizado na altura dela."""
        self._cursor.configure(
            fg_color=background, image=self._cursor_image(color)
        )
        # Com in_, o cursor acompanha a linha: some quando a busca a esconde.
        self._cursor.place(in_=row.frame, x=CURSOR_X, rely=0.5, anchor="w")
        self._cursor.lift()  # na frente da linha, criada depois dele

    def _set_list_focus(self, focused: bool) -> None:
        self._list_focused = focused
        if self._selected is not None:
            self._paint_row(self._selected)

    def _visible_numbers(self) -> list[int]:
        """Números das linhas que a busca deixou à mostra, em ordem."""
        return [
            number for number, row in self._rows.items()
            if row.frame.winfo_manager()  # "" quando escondida pela busca
        ]

    def _move_selection(self, step: int) -> str:
        """Seta para cima (-1) ou para baixo (+1): seleciona o vizinho."""
        visible = self._visible_numbers()
        if visible:
            if self._selected in visible:
                index = visible.index(self._selected) + step
                index = max(0, min(index, len(visible) - 1))
            else:
                index = 0  # a seleção sumiu na busca: vai ao primeiro
            self._select(self._rows[visible[index]].entry)
        return "break"  # a tecla já foi tratada

    def _open_first_result(self) -> str:
        visible = self._visible_numbers()
        if visible:
            self._select(self._rows[visible[0]].entry)
        return "break"

    def _focus_search(self) -> str:
        self._search.focus_set()
        self._search.select_range(0, "end")  # digitar substitui a busca
        return "break"

    def _scroll_to(self, number: int) -> None:
        """Rola a lista só o necessário para a linha ficar inteira à vista."""
        self._root.update_idletasks()  # posições em dia depois de filtrar
        frame = self._rows[number].frame
        # O CTkScrollableFrame não tem método público para rolar.
        canvas = self._list._parent_canvas
        content_height = self._list.winfo_height()
        if content_height <= 1:
            return  # a lista ainda não foi desenhada
        top = frame.winfo_y()
        bottom = top + frame.winfo_height()
        view_top, view_bottom = (
            fraction * content_height for fraction in canvas.yview()
        )
        if top < view_top:
            canvas.yview_moveto(top / content_height)
        elif bottom > view_bottom:
            canvas.yview_moveto(
                (bottom - (view_bottom - view_top)) / content_height
            )

    def _apply_filter(self, _event: tk.Event | None = None) -> None:
        text = self._search.get()
        if text:
            self._clear_button.grid()
        else:
            self._clear_button.grid_remove()

        query = text.strip().lower()
        if query == self._query:
            return  # teclas como as setas não mudam o texto
        self._query = query
        shown = 0
        for row in self._rows.values():
            if query in row.search_text:
                row.frame.grid()  # volta para a mesma posição de antes
                shown += 1
            else:
                row.frame.grid_remove()
        if shown:
            self._no_results.grid_remove()
        else:
            self._no_results.grid()
        self._show_count(shown)
        # Volta ao topo; senão, com a lista rolada, os resultados ficam fora
        # da vista. O CTkScrollableFrame não tem método público para isso.
        self._list._parent_canvas.yview_moveto(0)

    def _clear_search(self) -> None:
        self._search.delete(0, "end")
        self._search.focus_set()
        self._apply_filter()

    def _paint_search_border(self, focused: bool | None = None) -> None:
        """Borda de 2 px na cor do tipo atual quando o campo tem foco."""
        if focused is not None:
            self._search_focused = focused
        if self._search_focused:
            self._search_box.configure(
                border_width=FOCUS_BORDER_WIDTH, border_color=self._accent
            )
        else:
            self._search_box.configure(
                border_width=BORDER_WIDTH, border_color=BORDER_COLOR
            )

    def _select(self, entry: PokedexEntry) -> None:
        self._scroll_to(entry.number)
        if entry.number == self._selected == self._shown:
            return  # já está na tela
        previous, self._selected = self._selected, entry.number
        # Cinza enquanto carrega; ao terminar, ganha o pastel do card.
        self._selected_background = ELEVATED_COLOR
        self._selected_text = TEXT_COLOR
        if previous is not None:
            self._paint_row(previous)
        self._paint_row(entry.number)
        self._load(entry)

    # --- Carregamento e exibição do Pokémon ----------------------------

    def _load(self, entry: PokedexEntry) -> None:
        if self._pending is not None:
            # Descarta o pedido anterior se ele ainda não começou.
            self._pending.cancel()
        self._cancel_status_delay()
        self._status_job = self._root.after(
            STATUS_DELAY_MS, self._show_status, f"Carregando {entry.name}..."
        )
        self._pending = self._run_in_background(
            lambda: self._fetch(entry.number), self._show_pokemon
        )

    def _fetch(self, number: int) -> tuple[Pokemon, Image.Image]:
        """Roda fora da thread da interface: baixa dados e prepara a imagem."""
        pokemon = self._repository.get_pokemon(number)
        image = Image.open(BytesIO(self._repository.get_artwork(pokemon)))
        image.thumbnail((ARTWORK_MAX_SIZE, ARTWORK_MAX_SIZE))
        return pokemon, image

    def _show_pokemon(self, result: tuple[Pokemon, Image.Image]) -> None:
        pokemon, image = result
        if pokemon.number != self._selected:
            return  # chegou tarde: o usuário já escolheu outro Pokémon
        self._shown = pokemon.number
        color = type_styles(pokemon)[0].color
        background = pastel(color)
        text_color = readable_text_color(background)

        self._hero.configure(
            fg_color=background, border_color=hero_border_color(color)
        )
        self._artwork_image = image
        self._render_artwork()
        name, symbol = self._split_name(pokemon.name)
        self._name.configure(text=name, text_color=text_color)
        if symbol is not None:
            self._name_symbol.configure(
                image=self._symbol_image(symbol, text_color, True)
            )
            self._name_symbol.pack(side="left", after=self._name)
        else:
            self._name_symbol.pack_forget()
        self._number.configure(
            text=format_number(pokemon.number),
            text_color=hero_number_color(background),
        )
        self._accent = bar_color(color)
        self._selected_background = background
        self._selected_text = text_color
        self._paint_row(pokemon.number)
        self._paint_search_border()

        height_label, weight_label = self._measures
        height_label.configure(text=format_measure(pokemon.height, "m"))
        weight_label.configure(text=format_measure(pokemon.weight, "kg"))

        clear(self._badges)
        for style in type_styles(pokemon):
            badge = self._type_badge(self._badges, style)
            badge.pack(side="left", padx=(ITEM_GAP, 0))

        stats = zip(self._stat_widgets, stat_rows(pokemon))
        for (value_label, bar), (_, value) in stats:
            value_label.configure(text=str(value))
            bar.configure(progress_color=self._accent)
            bar.set(bar_fraction(value))
        self._total.configure(text=str(pokemon.total))

        abilities = ability_rows(pokemon)
        for index, (name_label, tag) in enumerate(self._ability_rows):
            name, hidden = (
                abilities[index] if index < len(abilities) else ("", False)
            )
            name_label.configure(text=name)
            if hidden:
                tag.pack(side="left", padx=ITEM_GAP)
            else:
                tag.pack_forget()
        self._show_status(self._count_text)

    def _toggle_theme(self) -> None:
        """Troca entre claro e escuro e guarda a escolha para a próxima vez."""
        theme = "light" if ctk.get_appearance_mode() == "Dark" else "dark"
        ctk.set_appearance_mode(theme)
        save_theme(SETTINGS_PATH, theme)

    def _set_window_icon(self) -> None:
        """Troca o ícone padrão do CustomTkinter pelo da Pokédex.

        Precisa vir logo depois de criar a janela: o CustomTkinter só põe
        o ícone dele se ninguém tiver chamado iconbitmap antes.
        """
        try:
            self._root.iconbitmap(str(ICON_PATH))
        except tk.TclError:
            pass  # fora do Windows o .ico pode não ser aceito

    def _schedule_artwork_resize(self, _event: tk.Event) -> None:
        """Redesenha a arte quando o hero muda de tamanho.

        Arrastar a borda da janela gera dezenas de eventos; espera um
        instante e redesenha uma vez só.
        """
        if self._artwork_job is not None:
            self._root.after_cancel(self._artwork_job)
        self._artwork_job = self._root.after(
            RESIZE_DELAY_MS, self._render_artwork
        )

    def _render_artwork(self) -> None:
        """Ajusta a arte ao maior quadrado que cabe na área dela."""
        self._artwork_job = None
        if self._artwork_image is None:
            return
        # winfo_* mede em pixels da tela; o CTkImage espera o tamanho antes
        # da escala do Windows (125%, 150%...).
        scaling = ctk.ScalingTracker.get_widget_scaling(self._art_area)
        available = min(
            self._art_area.winfo_width(), self._art_area.winfo_height()
        ) / scaling
        side = min(available, ARTWORK_MAX_SIZE)
        if side < 1:
            return  # a janela ainda não foi desenhada
        width, height = self._artwork_image.size
        ratio = side / max(width, height)
        size = (round(width * ratio), round(height * ratio))
        self._artwork.configure(
            image=ctk.CTkImage(self._artwork_image, size=size)
        )

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
            self._show_status(CONNECTION_ERROR, ERROR_COLOR)
        else:
            on_success(result)

    def _show_status(
        self, text: str, color: ThemeColor = MUTED_COLOR
    ) -> None:
        """Mostra um aviso no lugar da contagem de Pokémon."""
        self._cancel_status_delay()
        self._status.configure(text=text, text_color=color)

    def _cancel_status_delay(self) -> None:
        if self._status_job is not None:
            self._root.after_cancel(self._status_job)
            self._status_job = None

    def _close(self) -> None:
        self._closing.set()
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._icon_executor.shutdown(wait=False, cancel_futures=True)
        self._root.destroy()
