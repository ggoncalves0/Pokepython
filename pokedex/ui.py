"""Janela da Pokédex, montada com CustomTkinter."""

import logging
import tkinter as tk
from collections.abc import Callable
from functools import partial
from io import BytesIO
from pathlib import Path
from typing import Any, NamedTuple

import customtkinter as ctk
from PIL import Image

from . import ctk_adapter
from .background import TaskRunner, Ticket
from .icons import (
    TITLE_SYMBOLS,
    close_icon,
    cursor_icon,
    list_symbol,
    moon_icon,
    pixel_art,
    search_icon,
    sun_icon,
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
    render_title,
)
from .pokemon_list import PokemonList, format_number
from .settings import load_theme, save_theme
from .theme import (
    APP_BACKGROUND,
    ARTWORK_MAX_SIZE,
    ARTWORK_MIN_SIZE,
    BADGE_HEIGHT,
    BADGE_PADDING,
    BADGE_RADIUS,
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
    CURSOR_SCALE,
    ELEVATED_COLOR,
    ERROR_COLOR,
    FOCUS_BORDER_WIDTH,
    FOCUS_COLOR,
    FONT_BADGE,
    FONT_BODY,
    FONT_HERO,
    FONT_HIDDEN_TAG,
    FONT_LIST_NAME,
    FONT_LIST_NUMBER,
    FONT_TITLE,
    ICON_BUTTON_RADIUS,
    INITIAL_WINDOW_SIZE,
    ITEM_GAP,
    LIST_ICON_SIZE,
    LIST_WIDTH,
    MIN_WINDOW_SIZE,
    MUTED_COLOR,
    SEARCH_HEIGHT,
    SEARCH_ICON_SIZE,
    SEARCH_RADIUS,
    SIDEBAR_COLOR,
    SIDEBAR_WIDTH,
    STAT_VALUE_WIDTH,
    TEXT_COLOR,
    THEME_BUTTON_SIZE,
    TITLE_GAP,
    TYPES,
    WIDE_GAP,
    WINDOW_MARGIN,
    Color,
    ThemeColor,
    TypeStyle,
    badge_text_color,
    bar_color,
    hero_border_color,
    hero_number_color,
    pastel,
    readable_text_color,
    theme_pair,
)
from .tooltip import Tooltip

logger = logging.getLogger(__name__)

# Valor que enche a barra. Quase todo stat base fica abaixo disso; os
# poucos acima (como o HP 250 do Chansey) enchem a barra, e o número ao
# lado mostra o valor exato. Com o máximo real (255), 45 e 65 pareciam
# quase iguais.
STAT_BAR_MAX = 180
# Carregamentos rápidos não chegam a mostrar o aviso na lateral.
LOADING_STATUS_DELAY_MS = 300
# Curto o bastante para o clique ter resposta na hora. Com o Pokémon no
# cache, os dados chegam antes e o card de espera não pisca.
LOADING_CARD_DELAY_MS = 50
FILTER_DELAY_MS = 150
RESIZE_DELAY_MS = 60
THEME_FADE_MS = 220
THEME_FADE_STEPS = 12
# Três filas, para o clique nunca esperar a pré-carga nem os ícones. O
# limite de pedidos simultâneos à PokéAPI fica em pokeapi.download.
DETAIL_WORKERS = 2
PREFETCH_WORKERS = 1
ICON_WORKERS = 4
PRIORITY_NOW = 0
PRIORITY_LATER = 1
CONNECTION_ERROR = "Sem conexão com a PokéAPI."
LOAD_ERROR = "Não deu para carregar {name}."
LIST_ERROR = "Não deu para carregar a lista de Pokémon."
LOADING_POKEDEX = "Carregando a Pokédex..."
LOADING = "Carregando..."
NO_VALUE = "—"
# Um Pokémon tem no máximo 2 habilidades normais e 1 oculta. O card
# reserva sempre as 3 linhas, para não mudar de altura entre Pokémon.
MAX_ABILITIES = 3
PROJECT_DIR = Path(__file__).resolve().parent.parent
ICON_PATH = PROJECT_DIR / "assets" / "icon.ico"
SETTINGS_PATH = PROJECT_DIR / "settings.json"
# O Pokémon fica no miolo do ícone de 40 x 30 px.
LIST_ICON_CROP = (6, 4, 6 + LIST_ICON_SIZE[0], 4 + LIST_ICON_SIZE[1])
CENTERED: dict[str, Any] = {"relx": 0.5, "rely": 0.5, "anchor": "center"}

STAT_NAMES = {
    "hp": "HP",
    "attack": "Ataque",
    "defense": "Defesa",
    "special-attack": "Ataque Esp.",
    "special-defense": "Defesa Esp.",
    "speed": "Velocidade",
}


class AbilityRow(NamedTuple):
    name: str
    hidden: bool


NO_ABILITY = AbilityRow("", hidden=False)


class Title(NamedTuple):
    text: str
    size: int
    color: Color
    symbol: str | None = None


class CardColors(NamedTuple):
    background: str
    text: str
    number: str
    border: ThemeColor
    accent: ThemeColor


class IconButton(ctk.CTkButton):
    """CTkButton só com ícone que aceita o foco do teclado.

    O CTkButton passa o foco para o rótulo do texto, que não existe num
    botão sem texto; aqui o foco fica no próprio botão.
    """

    def focus(self) -> None:
        tk.Frame.focus_set(self)

    focus_set = focus

    def focus_force(self) -> None:
        tk.Frame.focus_force(self)


def format_measure(value: float, unit: str) -> str:
    """No padrão brasileiro: 6.0 vira "6,0 kg"."""
    return f"{value:.1f} {unit}".replace(".", ",")


def type_styles(pokemon: Pokemon) -> list[TypeStyle]:
    return [TYPES[name] for name in pokemon.types]


def stat_rows(pokemon: Pokemon) -> list[tuple[str, int]]:
    return [(label, pokemon.stats[name]) for name, label in STAT_NAMES.items()]


def bar_fraction(value: int) -> float:
    return min(value / STAT_BAR_MAX, 1)


def ability_rows(pokemon: Pokemon) -> list[AbilityRow]:
    rows = [AbilityRow(name, hidden=False) for name in pokemon.abilities]
    if pokemon.hidden_ability:
        rows.append(AbilityRow(pokemon.hidden_ability, hidden=True))
    return rows


def card_colors(pokemon: Pokemon) -> CardColors:
    type_color = type_styles(pokemon)[0].color
    background = pastel(type_color)
    return CardColors(
        background=background,
        text=readable_text_color(background),
        number=hero_number_color(background),
        border=hero_border_color(type_color),
        accent=bar_color(type_color),
    )


def destroy_children(frame: tk.Misc) -> None:
    for child in frame.winfo_children():
        child.destroy()


def split_symbol(name: str) -> tuple[str, str | None]:
    """As fontes pixeladas não têm ♀ e ♂: eles viram desenhos."""
    if name[-1:] in TITLE_SYMBOLS:
        return name[:-1], name[-1]
    return name, None


def pixel_image(
    draw: Callable[[str], Image.Image],
    color: Color,
    scale: int = 1,
    snap: bool = False,
) -> PixelImage:
    light, dark = theme_pair(color)
    return PixelImage(draw(light), draw(dark), scale, snap)


def themed_icon(
    draw: Callable[[str, int], Image.Image], color: ThemeColor, size: int
) -> ctk.CTkImage:
    light, dark = color
    return ctk.CTkImage(
        light_image=draw(light, size),
        dark_image=draw(dark, size),
        size=(size, size),
    )


def ease_out(progress: float) -> float:
    return 1 - (1 - progress) ** 2


class PokedexWindow:
    def __init__(self, repository: PokemonRepository) -> None:
        ctk.set_appearance_mode(load_theme(SETTINGS_PATH))
        # Antes de criar a janela: os ajustes mudam como ela troca de tema.
        ctk_adapter.install()
        # As fontes precisam estar registradas antes de criar os widgets.
        fonts_loaded = load_pixel_fonts()
        self._root = ctk.CTk(fg_color=APP_BACKGROUND)
        self._pixel_fonts = fonts_loaded and fonts_available(self._root)
        self._repository = repository
        self._details = TaskRunner(self._root.after, DETAIL_WORKERS, "dados")
        self._prefetch = TaskRunner(
            self._root.after, PREFETCH_WORKERS, "vizinhos"
        )
        self._icons = TaskRunner(self._root.after, ICON_WORKERS, "icones")
        self._selected: int | None = None
        self._displayed: int | None = None
        self._loading_ticket: Ticket | None = None
        self._loading_card_job: str | None = None
        self._status_job: str | None = None
        self._filter_job: str | None = None
        self._artwork_job: str | None = None
        self._prefetched: set[int] = set()
        self._prefetching: dict[int, Ticket] = {}
        self._count_text = ""
        self._applied_query = ""
        self._type_accent: Color = MUTED_COLOR
        self._artwork_source: Image.Image | None = None
        self._theme_cover = ctk_adapter.WindowCover(self._root)
        self._current_fade = 0
        self._list_images: dict[tuple[str, Color], PixelImage] = {}
        # Guardados para redesenhar os títulos se a escala da tela mudar.
        self._drawn_titles: dict[ctk.CTkLabel, Title] = {}

        self._create_fonts()
        self._configure_window()
        self._build_details()
        self._build_sidebar()
        ctk.ScalingTracker.add_widget(self._on_scaling_change, self._root)
        self._bind_shortcuts()
        self._show_status(LOADING_POKEDEX)
        self._details.submit(
            repository.list_entries, self._show_entries,
            on_error=partial(self._report_error, LIST_ERROR),
            priority=PRIORITY_NOW,
        )

    def run(self) -> None:
        self._root.mainloop()

    def _configure_window(self) -> None:
        width, height = INITIAL_WINDOW_SIZE
        self._root.title("PokePython")
        self._root.geometry(f"{width}x{height}")
        self._root.minsize(*MIN_WINDOW_SIZE)
        self._set_window_icon()
        self._root.protocol("WM_DELETE_WINDOW", self._close)
        self._root.grid_columnconfigure(0, weight=1)
        self._root.grid_rowconfigure(0, weight=1)

    def _set_window_icon(self) -> None:
        """Precisa vir antes de a janela abrir: o CustomTkinter põe o ícone
        dele logo depois, se ninguém tiver chamado iconbitmap."""
        try:
            self._root.iconbitmap(str(ICON_PATH))
        except tk.TclError:
            logger.info("Ícone da janela não aceito neste sistema.")

    def _bind_shortcuts(self) -> None:
        self._root.bind("<Up>", lambda _event: self._move_selection(-1))
        self._root.bind("<Down>", lambda _event: self._move_selection(1))
        for key in ("<Control-f>", "<Control-F>"):
            self._root.bind(key, lambda _event: self._focus_search())

    def _create_fonts(self) -> None:
        if self._pixel_fonts:
            # As duas fontes têm um peso só; um negrito falso borraria os
            # pixels.
            title, text, weight = TITLE_FAMILY, TEXT_FAMILY, "normal"
        else:
            # Sem as fontes pixeladas, o negrito destaca títulos e selos.
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
        self._hidden_tag_font = ctk.CTkFont(
            family=text, size=FONT_HIDDEN_TAG, weight=weight
        )
        self._fonts_on_pixel_grid = (
            (self._hero_font, FONT_HERO),
            (self._title_font, FONT_TITLE),
        )
        self._snap_title_fonts(
            ctk.ScalingTracker.get_widget_scaling(self._root)
        )

    def _snap_title_fonts(self, widget_scaling: float) -> None:
        for font, size in self._fonts_on_pixel_grid:
            font.configure(size=pixel_font_size(size, widget_scaling))
        for label, title in self._drawn_titles.items():
            label.configure(image=self._title_image(title))

    def _on_scaling_change(
        self, widget_scaling: float, *_args: object
    ) -> None:
        self._snap_title_fonts(widget_scaling)
        self._list.rescale()

    def _set_title(self, label: ctk.CTkLabel, title: Title) -> None:
        if not self._pixel_fonts:
            label.configure(
                text=title.text + (title.symbol or ""), text_color=title.color
            )
            return
        self._drawn_titles[label] = title
        label.configure(image=self._title_image(title))

    def _title_image(self, title: Title) -> ctk.CTkImage:
        scaling = ctk.ScalingTracker.get_widget_scaling(self._root)
        on_screen = round(pixel_font_size(title.size, scaling) * scaling)
        light, dark = (
            self._draw_title(title.text, on_screen, ink, title.symbol)
            for ink in theme_pair(title.color)
        )
        width, height = light.size
        # Tamanho dividido pela escala: ao multiplicar de volta, o CTkImage
        # não precisa ampliar nada e os pixels ficam intactos.
        return ctk.CTkImage(
            light, dark, size=(width / scaling, height / scaling)
        )

    @staticmethod
    def _draw_title(
        text: str, size: int, color: str, symbol: str | None
    ) -> Image.Image:
        image = render_title(text, size, color)
        if symbol is None:
            return image
        mark = pixel_art(
            TITLE_SYMBOLS[symbol], {"X": color}, size // PIXEL_GRID
        )
        joined = Image.new(
            "RGBA", (image.width + mark.width, image.height), (0, 0, 0, 0)
        )
        joined.alpha_composite(image)
        joined.alpha_composite(mark, (image.width, 0))
        return joined

    def _split_name(self, name: str) -> tuple[str, str | None]:
        return split_symbol(name) if self._pixel_fonts else (name, None)

    def _cursor_image(self, color: Color) -> PixelImage:
        key = ("cursor", color)
        if key not in self._list_images:
            # Acompanha o nome da lista (Jersey 10), que segue a escala
            # exata da tela.
            self._list_images[key] = pixel_image(
                cursor_icon, color, CURSOR_SCALE
            )
        return self._list_images[key]

    def _list_symbol_image(self, symbol: str, color: Color) -> PixelImage:
        key = (symbol, color)
        if key not in self._list_images:
            self._list_images[key] = pixel_image(
                partial(list_symbol, symbol), color
            )
        return self._list_images[key]

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(
            self._root, width=SIDEBAR_WIDTH, corner_radius=0,
            fg_color=SIDEBAR_COLOR,
        )
        sidebar.grid(row=0, column=1, sticky="ns")
        sidebar.grid_propagate(False)  # largura fixa: veja SIDEBAR_WIDTH
        sidebar.grid_rowconfigure(3, weight=1)
        sidebar.grid_columnconfigure(0, weight=1)

        self._build_sidebar_header(sidebar).grid(
            row=0, column=0, sticky="ew",
            padx=WINDOW_MARGIN, pady=(WINDOW_MARGIN, 0),
        )
        self._status = self._label(
            sidebar, "", color=MUTED_COLOR, wraplength=LIST_WIDTH,
            justify="left",
        )
        self._status.grid(row=1, column=0, sticky="w", padx=WINDOW_MARGIN)
        self._search_box = self._build_search(sidebar)
        self._search_box.grid(
            row=2, column=0, sticky="ew", padx=WINDOW_MARGIN, pady=CARD_GAP
        )
        self._list = PokemonList(
            sidebar,
            number_font=self._list_number_font,
            name_font=self._list_name_font,
            message_font=self._body_font,
            split_name=self._split_name,
            cursor_image=self._cursor_image,
            symbol_image=self._list_symbol_image,
            on_click=self._select,
        )
        self._list.frame.grid(
            row=3, column=0, sticky="nsew",
            padx=WINDOW_MARGIN, pady=(0, WINDOW_MARGIN),
        )

    def _build_sidebar_header(self, sidebar: ctk.CTkFrame) -> ctk.CTkFrame:
        header = self._container(sidebar)
        # Menor que o nome do Pokémon, para não disputar atenção com ele.
        title = self._label(header, "", self._title_font)
        self._set_title(title, Title("Pokédex", FONT_TITLE, TEXT_COLOR))
        title.pack(side="left")
        self._build_theme_button(header).pack(side="right")
        return header

    def _build_theme_button(self, parent: ctk.CTkFrame) -> IconButton:
        light, dark = MUTED_COLOR
        button = IconButton(
            parent,
            text="",
            # O ícone mostra para onde o clique leva: lua no tema claro,
            # sol no escuro.
            image=PixelImage(moon_icon(light), sun_icon(dark)),
            width=THEME_BUTTON_SIZE,
            height=THEME_BUTTON_SIZE,
            corner_radius=ICON_BUTTON_RADIUS,
            fg_color="transparent",
            hover_color=ELEVATED_COLOR,
            border_color=FOCUS_COLOR,
            command=self._toggle_theme,
        )
        tip = Tooltip(button, self._theme_tip, self._body_font)
        self._make_keyboard_accessible(button, tip)
        return button

    @staticmethod
    def _make_keyboard_accessible(button: IconButton, tip: Tooltip) -> None:
        # Direto no Frame do botão, que é quem recebe o foco: o configure e
        # o bind do CTkButton vão para as partes de dentro dele.
        tk.Frame.configure(button, takefocus=True)
        for key in ("<Return>", "<KP_Enter>", "<space>"):
            tk.Misc.bind(button, key, lambda _event: button.invoke())

        def show_focus(focused: bool) -> None:
            button.configure(border_width=FOCUS_BORDER_WIDTH if focused else 0)
            if focused:
                tip.show()
            else:
                tip.hide()

        tk.Misc.bind(button, "<FocusIn>", lambda _event: show_focus(True))
        tk.Misc.bind(button, "<FocusOut>", lambda _event: show_focus(False))

    @staticmethod
    def _theme_tip() -> str:
        if ctk.get_appearance_mode() == "Dark":
            return "Mudar para tema claro"
        return "Mudar para tema escuro"

    def _build_search(self, parent: ctk.CTkFrame) -> ctk.CTkFrame:
        # O CTkEntry não aceita ícone: uma moldura com borda leva a lupa, o
        # campo e o "×" lado a lado.
        box = ctk.CTkFrame(
            parent,
            width=LIST_WIDTH,
            height=SEARCH_HEIGHT,
            corner_radius=SEARCH_RADIUS,
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
            image=themed_icon(search_icon, MUTED_COLOR, SEARCH_ICON_SIZE),
            width=SEARCH_ICON_SIZE,
            height=SEARCH_ICON_SIZE,
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
        # Sem recuo à direita, com o "×" escondido, o fundo do campo
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
        self._clear_button.grid_remove()

        for widget in (box, icon):
            widget.bind("<Button-1>", lambda _event: self._search.focus_set())
        self._bind_search_keys()
        return box

    def _bind_search_keys(self) -> None:
        search = self._search
        search.bind("<KeyRelease>", self._on_search_key)
        search.bind("<Escape>", lambda _event: self._clear_search())
        for key in ("<Return>", "<KP_Enter>"):
            search.bind(key, lambda _event: self._open_first_result())
        search.bind(
            "<FocusIn>",
            lambda _event: self._paint_search_border(focused=True),
        )
        search.bind(
            "<FocusOut>",
            lambda _event: self._paint_search_border(focused=False),
        )

    def _build_details(self) -> None:
        details = ctk.CTkFrame(self._root, fg_color="transparent")
        details.grid(
            row=0, column=0, sticky="nsew",
            padx=WINDOW_MARGIN, pady=WINDOW_MARGIN,
        )
        details.grid_columnconfigure(0, weight=3, uniform="cards")
        details.grid_columnconfigure(1, weight=2, uniform="cards")
        details.grid_rowconfigure(0, weight=1)
        self._build_hero(details)

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
        self._build_abilities(abilities_card)
        measures_card = self._card(right_column)
        measures_card.pack(fill="x", pady=(CARD_GAP, 0))
        self._build_measures(measures_card)

    def _build_hero(self, details: ctk.CTkFrame) -> None:
        self._hero = self._card(details)
        self._hero.grid(row=0, column=0, columnspan=2, sticky="nsew")
        header = self._container(self._hero)
        header.pack(fill="x", padx=CARD_PADDING, pady=(CARD_PADDING, 0))
        self._name = self._label(
            header, "", self._hero_font, height=FONT_HERO
        )
        self._name.pack(side="left", anchor="s")
        self._number = self._label(
            header, "", self._title_font, height=FONT_TITLE
        )
        # Na Press Start 2P, a última linha da grade (1/8 da altura) fica
        # vazia; o número sobe a diferença entre as duas fontes para as
        # linhas de base do nome e do número baterem.
        self._number.pack(
            side="left", anchor="s", padx=WIDE_GAP,
            pady=(0, (FONT_HERO - FONT_TITLE) // PIXEL_GRID),
        )
        self._badges = self._container(header)
        self._badges.pack(side="right")

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
        # place() centraliza sem mudar o tamanho da área: a arte acompanha o
        # hero sem empurrar o layout.
        self._artwork = ctk.CTkLabel(
            self._art_area, text="", width=0, height=0
        )
        self._artwork.place(**CENTERED)
        self._art_message = self._label(
            self._art_area, "", color=MUTED_COLOR
        )
        self._art_area.bind("<Configure>", self._schedule_artwork_resize)

    def _build_stats(self, card: ctk.CTkFrame) -> None:
        card.grid_columnconfigure(2, weight=1)
        self._card_title(card, "Status base").grid(
            row=0, column=0, columnspan=3, sticky="w",
            padx=CARD_PADDING, pady=(CARD_PADDING, TITLE_GAP),
        )
        self._stat_widgets: list[tuple[ctk.CTkLabel, ctk.CTkProgressBar]] = []
        for row, label in enumerate(STAT_NAMES.values(), start=1):
            name = self._label(card, label, color=MUTED_COLOR)
            name.grid(
                row=row, column=0, sticky="w", padx=(CARD_PADDING, ITEM_GAP)
            )
            value = self._label(card, "", width=STAT_VALUE_WIDTH)
            value.grid(row=row, column=1, sticky="e")
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
        self._label(card, "Total").grid(
            row=total_row, column=0, sticky="w",
            padx=(CARD_PADDING, ITEM_GAP), pady=(0, CARD_PADDING),
        )
        self._total = self._label(card, "", width=STAT_VALUE_WIDTH)
        self._total.grid(
            row=total_row, column=1, sticky="e", pady=(0, CARD_PADDING)
        )

    def _build_abilities(self, card: ctk.CTkFrame) -> None:
        self._card_title(card, "Habilidades").pack(
            anchor="w", padx=CARD_PADDING, pady=(CARD_PADDING, TITLE_GAP)
        )
        rows = self._container(card)
        rows.pack(fill="x", padx=CARD_PADDING, pady=(0, CARD_PADDING))
        self._ability_rows: list[tuple[ctk.CTkLabel, ctk.CTkLabel]] = []
        for _ in range(MAX_ABILITIES):
            row = self._container(rows)
            row.pack(fill="x")
            name = self._label(row, "")
            name.pack(side="left")
            # Rótulo simples, sem fundo: um selo arredondado parecia um
            # botão.
            hidden_tag = self._label(
                row, "OCULTA", self._hidden_tag_font, MUTED_COLOR
            )
            self._ability_rows.append((name, hidden_tag))

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
            value = self._label(card, "")
            value.grid(
                row=row, column=1, sticky="w",
                padx=(0, CARD_PADDING), pady=(0, bottom),
            )
            self._measures.append(value)

    def _card_title(self, card: ctk.CTkFrame, text: str) -> ctk.CTkLabel:
        title = self._label(card, "", self._title_font)
        self._set_title(title, Title(text, FONT_TITLE, TEXT_COLOR))
        return title

    def _label(
        self,
        parent: tk.Misc,
        text: str,
        font: ctk.CTkFont | None = None,
        color: Color = TEXT_COLOR,
        **options: Any,
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
        return ctk.CTkLabel(
            parent,
            text=style.label,
            font=self._badge_font,
            fg_color=style.color,
            text_color=badge_text_color(style.color),
            corner_radius=BADGE_RADIUS,
            height=BADGE_HEIGHT,
            padx=BADGE_PADDING,
        )

    @staticmethod
    def _card(parent: tk.Misc) -> ctk.CTkFrame:
        return ctk.CTkFrame(
            parent, corner_radius=CARD_RADIUS, fg_color=CARD_COLOR,
            border_width=CARD_BORDER_WIDTH, border_color=CARD_BORDER_COLOR,
        )

    @staticmethod
    def _container(parent: tk.Misc) -> ctk.CTkFrame:
        # Tamanho inicial zero: vazio, o padrão do CTkFrame (200 x 200)
        # empurraria o resto da tela.
        return ctk.CTkFrame(
            parent, width=0, height=0, fg_color="transparent"
        )

    def _show_entries(self, entries: list[PokedexEntry]) -> None:
        self._list.set_entries(entries)
        # A busca pode ter sido digitada enquanto a lista carregava.
        self._show_count(self._list.filter(self._applied_query))
        if entries:
            self._select(entries[0])
        self._load_icons(self._list.all_numbers())

    def _load_icons(self, numbers: list[int]) -> None:
        in_view = set(self._list.numbers_in_view())
        for number in numbers:
            self._icons.submit(
                partial(self._fetch_icon, number),
                partial(self._list.set_icon, number),
                on_error=partial(self._icon_failed, number),
                priority=PRIORITY_NOW if number in in_view else PRIORITY_LATER,
            )

    def _fetch_icon(self, number: int) -> Image.Image:
        """Roda numa thread de trabalho."""
        data = self._repository.get_icon(number)
        return Image.open(BytesIO(data)).convert("RGBA").crop(LIST_ICON_CROP)

    @staticmethod
    def _icon_failed(number: int, error: Exception) -> None:
        # O ícone é enfeite: a linha continua usável sem ele.
        logger.warning("Ícone do #%03d não carregou: %s", number, error)

    def _show_count(self, matching: int) -> None:
        total = self._list.total
        self._count_text = (
            f"{matching} de {total}" if self._applied_query
            else f"{total} Pokémon"
        )
        self._show_status(self._count_text)

    def _move_selection(self, step: int) -> str:
        self._apply_pending_filter()
        matching = self._list.matching_numbers()
        if matching:
            if self._selected in matching:
                index = matching.index(self._selected) + step
                index = max(0, min(index, len(matching) - 1))
            else:
                index = 0  # a seleção sumiu na busca: vai para o primeiro
            self._select(self._list.entry(matching[index]))
        return "break"

    def _open_first_result(self) -> str:
        self._apply_pending_filter()
        matching = self._list.matching_numbers()
        if matching:
            self._select(self._list.entry(matching[0]))
        return "break"

    def _focus_search(self) -> str:
        self._search.focus_set()
        self._search.select_range(0, "end")  # digitar substitui a busca
        return "break"

    def _on_search_key(self, _event: tk.Event | None = None) -> None:
        if self._search.get():
            ctk_adapter.reveal(self._clear_button, "grid")
        else:
            self._clear_button.grid_remove()
        # Digitando rápido, o filtro roda uma vez só, depois da última tecla.
        self._cancel_job(self._filter_job)
        self._filter_job = self._root.after(
            FILTER_DELAY_MS, self._apply_filter
        )

    def _apply_pending_filter(self) -> None:
        if self._filter_job is not None:
            self._cancel_job(self._filter_job)
            self._apply_filter()

    def _apply_filter(self) -> None:
        self._filter_job = None
        query = self._search.get().strip().lower()
        if query == self._applied_query:
            return  # teclas como as setas não mudam o texto
        self._applied_query = query
        matching = self._list.filter(query)
        if self._list.total:  # sem a lista, fica o aviso de carregamento
            self._show_count(matching)

    def _clear_search(self) -> None:
        self._cancel_job(self._filter_job)
        self._search.delete(0, "end")
        self._search.focus_set()
        self._clear_button.grid_remove()
        self._apply_filter()

    def _paint_search_border(self, *, focused: bool) -> None:
        if focused:
            self._search_box.configure(
                border_width=FOCUS_BORDER_WIDTH, border_color=FOCUS_COLOR
            )
        else:
            self._search_box.configure(
                border_width=BORDER_WIDTH, border_color=BORDER_COLOR
            )

    def _select(self, entry: PokedexEntry) -> None:
        self._list.scroll_into_view(entry.number)
        if self._is_shown_or_loading(entry.number):
            return
        self._selected = entry.number
        # Cinza enquanto carrega; ao terminar, a linha ganha o pastel do card.
        self._list.set_selection(
            entry.number, ELEVATED_COLOR, TEXT_COLOR, self._type_accent
        )
        self._load(entry)

    def _is_shown_or_loading(self, number: int) -> bool:
        return number == self._selected and (
            number == self._displayed or self._loading_ticket is not None
        )

    def _load(self, entry: PokedexEntry) -> None:
        if self._loading_ticket is not None:
            self._loading_ticket.cancel()
        self._cancel_job(self._status_job)
        self._cancel_job(self._loading_card_job)
        self._status_job = self._root.after(
            LOADING_STATUS_DELAY_MS,
            self._show_status, f"Carregando {entry.name}...",
        )
        self._loading_card_job = self._root.after(
            LOADING_CARD_DELAY_MS, self._loading_card_delay_over, entry
        )
        self._loading_ticket = self._details.submit(
            partial(self._fetch, entry.number),
            self._show_pokemon,
            on_error=partial(self._load_failed, entry),
            priority=PRIORITY_NOW,
        )

    def _fetch(self, number: int) -> tuple[Pokemon, Image.Image]:
        """Roda numa thread de trabalho."""
        pokemon = self._repository.get_pokemon(number)
        artwork = Image.open(BytesIO(self._repository.get_artwork(pokemon)))
        artwork.thumbnail((ARTWORK_MAX_SIZE, ARTWORK_MAX_SIZE))
        return pokemon, artwork

    def _download_to_cache(self, number: int) -> None:
        """Roda numa thread de trabalho."""
        self._repository.get_artwork(self._repository.get_pokemon(number))

    def _prefetch_neighbors(self, number: int) -> None:
        neighbors = self._neighbors(number)
        # Navegando rápido, os vizinhos de escolhas antigas que ainda não
        # começaram saem da fila, para ela não acumular.
        for stale in [n for n in self._prefetching if n not in neighbors]:
            self._prefetching.pop(stale).cancel()
        for neighbor in neighbors:
            if neighbor in self._prefetched or neighbor in self._prefetching:
                continue
            self._prefetching[neighbor] = self._prefetch.submit(
                partial(self._download_to_cache, neighbor),
                partial(self._prefetch_done, neighbor),
                on_error=partial(self._prefetch_failed, neighbor),
            )

    def _neighbors(self, number: int) -> list[int]:
        matching = self._list.matching_numbers()
        if number not in matching:
            return []
        index = matching.index(number)
        return [
            neighbor for neighbor in matching[max(index - 1, 0):index + 2]
            if neighbor != number
        ]

    def _prefetch_done(self, number: int, _result: None) -> None:
        self._prefetching.pop(number, None)
        self._prefetched.add(number)

    def _prefetch_failed(self, number: int, error: Exception) -> None:
        self._prefetching.pop(number, None)
        logger.info("Pré-carga do #%03d falhou: %s", number, error)

    def _loading_card_delay_over(self, entry: PokedexEntry) -> None:
        self._loading_card_job = None
        # Com o Pokémon no cache, os dados já estão prontos: entram direto,
        # sem passar pelo card de espera.
        self._details.deliver_ready()
        self._show_loading_card(entry, LOADING)

    def _show_loading_card(self, entry: PokedexEntry, message: str) -> None:
        if entry.number != self._selected or entry.number == self._displayed:
            return
        self._displayed = None
        self._hero.configure(
            fg_color=CARD_COLOR, border_color=CARD_BORDER_COLOR
        )
        name, symbol = self._split_name(entry.name)
        self._set_title(self._name, Title(name, FONT_HERO, TEXT_COLOR, symbol))
        self._set_title(
            self._number,
            Title(format_number(entry.number), FONT_TITLE, MUTED_COLOR),
        )
        destroy_children(self._badges)
        self._artwork.place_forget()
        self._art_message.configure(text=message)
        ctk_adapter.reveal(self._art_message, "place", **CENTERED)
        self._clear_details()

    def _clear_details(self) -> None:
        for value_label, bar in self._stat_widgets:
            value_label.configure(text=NO_VALUE)
            bar.set(0)
        self._total.configure(text=NO_VALUE)
        for name_label, hidden_tag in self._ability_rows:
            name_label.configure(text="")
            hidden_tag.pack_forget()
        for measure in self._measures:
            measure.configure(text=NO_VALUE)

    def _load_failed(self, entry: PokedexEntry, error: Exception) -> None:
        if entry.number != self._selected:
            return
        self._loading_ticket = None
        self._cancel_job(self._loading_card_job)
        self._loading_card_job = None
        if isinstance(error, OSError):
            message = CONNECTION_ERROR
        else:
            message = LOAD_ERROR.format(name=entry.name)
        # O card e a lateral avisam: o app nunca fica preso em
        # "Carregando...".
        self._show_loading_card(entry, message)
        self._report_error(message, error)

    def _show_pokemon(self, result: tuple[Pokemon, Image.Image]) -> None:
        pokemon, artwork = result
        if pokemon.number != self._selected:
            return
        self._loading_ticket = None
        self._cancel_job(self._loading_card_job)
        self._loading_card_job = None
        self._displayed = pokemon.number
        colors = card_colors(pokemon)
        self._type_accent = colors.accent
        self._show_hero(pokemon, artwork, colors)
        self._list.set_selection(
            pokemon.number, colors.background, colors.text, colors.accent
        )
        self._show_stats(pokemon, colors.accent)
        self._show_abilities(pokemon)
        self._show_measures(pokemon)
        self._show_status(self._count_text)
        self._prefetch_neighbors(pokemon.number)

    def _show_hero(
        self, pokemon: Pokemon, artwork: Image.Image, colors: CardColors
    ) -> None:
        self._hero.configure(
            fg_color=colors.background, border_color=colors.border
        )
        self._art_message.place_forget()
        ctk_adapter.reveal(self._artwork, "place", **CENTERED)
        self._artwork_source = artwork
        self._render_artwork()
        name, symbol = self._split_name(pokemon.name)
        self._set_title(
            self._name, Title(name, FONT_HERO, colors.text, symbol)
        )
        self._set_title(
            self._number,
            Title(format_number(pokemon.number), FONT_TITLE, colors.number),
        )
        destroy_children(self._badges)
        for style in type_styles(pokemon):
            self._type_badge(self._badges, style).pack(
                side="left", padx=(ITEM_GAP, 0)
            )

    def _show_stats(self, pokemon: Pokemon, accent: ThemeColor) -> None:
        stats = zip(self._stat_widgets, stat_rows(pokemon), strict=True)
        for (value_label, bar), (_, value) in stats:
            value_label.configure(text=str(value))
            bar.configure(progress_color=accent)
            bar.set(bar_fraction(value))
        self._total.configure(text=str(pokemon.total))

    def _show_abilities(self, pokemon: Pokemon) -> None:
        abilities = ability_rows(pokemon) + [NO_ABILITY] * MAX_ABILITIES
        rows = zip(self._ability_rows, abilities[:MAX_ABILITIES], strict=True)
        for (name_label, hidden_tag), ability in rows:
            name_label.configure(text=ability.name)
            if ability.hidden:
                ctk_adapter.reveal(
                    hidden_tag, "pack", side="left", padx=ITEM_GAP
                )
            else:
                hidden_tag.pack_forget()

    def _show_measures(self, pokemon: Pokemon) -> None:
        height_label, weight_label = self._measures
        height_label.configure(text=format_measure(pokemon.height, "m"))
        weight_label.configure(text=format_measure(pokemon.weight, "kg"))

    def _toggle_theme(self) -> None:
        theme = "light" if ctk.get_appearance_mode() == "Dark" else "dark"
        # Uma foto do tema antigo cobre a janela e esmaece sobre o novo: a
        # troca fica suave, sem mostrar os widgets se redesenhando.
        self._current_fade += 1
        covered = self._theme_cover.show()
        ctk.set_appearance_mode(theme)
        save_theme(SETTINGS_PATH, theme)
        if covered:
            self._root.update_idletasks()  # o tema novo pronto por baixo
            self._fade_step(self._current_fade, 1)
        else:
            self._theme_cover.hide()  # a foto de uma troca anterior, se sobrou

    def _fade_step(self, fade: int, step: int) -> None:
        if fade != self._current_fade:
            return  # outra troca começou e pôs uma foto nova
        if step > THEME_FADE_STEPS:
            self._theme_cover.hide()
            return
        self._theme_cover.set_opacity(1 - ease_out(step / THEME_FADE_STEPS))
        self._root.after(
            THEME_FADE_MS // THEME_FADE_STEPS, self._fade_step, fade, step + 1
        )

    def _schedule_artwork_resize(self, _event: tk.Event) -> None:
        # Arrastar a borda da janela gera dezenas de eventos: a arte é
        # redesenhada uma vez só, quando ela para de mudar.
        self._cancel_job(self._artwork_job)
        self._artwork_job = self._root.after(
            RESIZE_DELAY_MS, self._render_artwork
        )

    def _render_artwork(self) -> None:
        self._artwork_job = None
        if self._artwork_source is None:
            return
        # winfo_* mede em pixels da tela; o CTkImage espera o tamanho antes
        # da escala do Windows.
        scaling = ctk.ScalingTracker.get_widget_scaling(self._art_area)
        available = min(
            self._art_area.winfo_width(), self._art_area.winfo_height()
        ) / scaling
        side = min(available, ARTWORK_MAX_SIZE)
        if side < 1:
            return  # a janela ainda não foi desenhada
        width, height = self._artwork_source.size
        ratio = side / max(width, height)
        size = (round(width * ratio), round(height * ratio))
        self._artwork.configure(
            image=ctk.CTkImage(self._artwork_source, size=size)
        )

    def _report_error(self, message: str, error: Exception) -> None:
        # Falha de rede é esperada; outra exceção é defeito e precisa do
        # traceback no log.
        if isinstance(error, OSError):
            logger.warning("%s (%s)", message, error)
        else:
            logger.error(message, exc_info=error)
        self._show_status(message, ERROR_COLOR)

    def _show_status(
        self, text: str, color: ThemeColor = MUTED_COLOR
    ) -> None:
        self._cancel_job(self._status_job)
        self._status_job = None
        self._status.configure(text=text, text_color=color)

    def _cancel_job(self, job: str | None) -> None:
        if job is not None:
            self._root.after_cancel(job)

    def _close(self) -> None:
        self._details.close()
        self._prefetch.close()
        self._icons.close()
        self._theme_cover.destroy()
        self._root.destroy()
