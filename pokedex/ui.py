"""Janela da Pokédex, com visual moderno feito com CustomTkinter."""

import logging
import tkinter as tk
from collections.abc import Callable
from functools import partial
from io import BytesIO
from pathlib import Path

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
    ELEVATED_COLOR,
    ERROR_COLOR,
    FOCUS_BORDER_WIDTH,
    FOCUS_COLOR,
    FONT_BADGE,
    FONT_BODY,
    FONT_HERO,
    FONT_LIST_NAME,
    FONT_LIST_NUMBER,
    FONT_TAG,
    FONT_TITLE,
    ICON_BUTTON_RADIUS,
    ICON_SIZE,
    ITEM_GAP,
    LIST_ICON_SIZE,
    LIST_WIDTH,
    MIN_WINDOW_SIZE,
    MUTED_COLOR,
    PILL_HEIGHT,
    PILL_PADDING,
    PILL_RADIUS,
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
from .tooltip import Tooltip

logger = logging.getLogger(__name__)

# Valor que enche a barra. Quase todo stat base fica abaixo disso; os
# poucos acima (como o HP 250 do Chansey) enchem a barra, e o número ao
# lado mostra o valor exato. Com o máximo real (255), 45 e 65 pareciam
# quase iguais.
STAT_BAR_MAX = 180
STATUS_DELAY_MS = 300  # só avisa na lateral que está carregando se demorar
# O card mostra nome, número e "Carregando..." se os dados não chegarem
# nesse tempo (o critério é aparecer em até 100 ms). Com o Pokémon no
# cache, os dados já estão prontos nessa hora e entram direto: o card de
# espera não pisca.
LOADING_DELAY_MS = 50
FILTER_DELAY_MS = 150  # a busca roda uma vez, 150 ms depois da última tecla
RESIZE_DELAY_MS = 60  # espera a janela parar de mudar antes de redesenhar
FADE_MS = 220  # transição de tema: o tema antigo esmaece sobre o novo
FADE_STEPS = 12
# Pedidos em paralelo, em três filas, para o clique nunca esperar as
# outras: o Pokémon escolhido, a pré-carga dos vizinhos e os ícones. A
# PokéAPI recebe no máximo 6 pedidos de uma vez (pokeapi.MAX_CONNECTIONS).
DETAIL_WORKERS = 2
PREFETCH_WORKERS = 1
ICON_WORKERS = 4
# Prioridades na fila dos ícones: os das linhas visíveis vão antes.
PRIORITY_NOW = 0
PRIORITY_ICON = 1
CONNECTION_ERROR = "Sem conexão com a PokéAPI."
LOAD_ERROR = "Não deu para carregar {name}."
LIST_ERROR = "Não deu para carregar a lista de Pokémon."
LOADING = "Carregando..."
NO_VALUE = "—"
# Um Pokémon tem no máximo 2 habilidades normais e 1 oculta. O card
# reserva sempre as 3 linhas, para não mudar de altura entre Pokémon.
MAX_ABILITIES = 3
PROJECT_DIR = Path(__file__).resolve().parent.parent
ICON_PATH = PROJECT_DIR / "assets" / "icon.ico"
# Miolo do ícone de 40 x 30 px, onde fica o Pokémon (LIST_ICON_SIZE).
LIST_ICON_CROP = (6, 4, 6 + LIST_ICON_SIZE[0], 4 + LIST_ICON_SIZE[1])
SETTINGS_PATH = PROJECT_DIR / "settings.json"  # tema escolhido


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


STAT_NAMES = {
    "hp": "HP",
    "attack": "Ataque",
    "defense": "Defesa",
    "special-attack": "Ataque Esp.",
    "special-defense": "Defesa Esp.",
    "speed": "Velocidade",
}

__all__ = ["PokedexWindow", "format_number"]


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


def ease_out(progress: float) -> float:
    """Começa rápido e termina devagar (0 a 1)."""
    return 1 - (1 - progress) ** 2


class PokedexWindow:
    """Janela principal: detalhes à esquerda, busca e lista à direita."""

    def __init__(self, repository: PokemonRepository) -> None:
        ctk.set_appearance_mode(load_theme(SETTINGS_PATH))
        # Correções do CustomTkinter (cores ao trocar de tema, janela que
        # sumia na troca): antes de criar a janela. Veja ctk_adapter.
        ctk_adapter.install()
        # As fontes precisam ser registradas antes de criar os widgets.
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
        self._shown: int | None = None  # Pokémon exibido nos cards
        self._loading: Ticket | None = None  # pedido do Pokémon escolhido
        self._loading_job: str | None = None
        self._filter_job: str | None = None
        self._prefetched: set[int] = set()  # no cache ou a caminho
        self._prefetching: dict[int, Ticket] = {}  # pré-cargas pendentes
        self._count_text = ""  # "151 Pokémon", depois que a lista chega
        self._query = ""  # busca aplicada à lista
        self._search_focused = False
        self._accent: str | ThemeColor = MUTED_COLOR  # cor do tipo atual
        self._artwork_image: Image.Image | None = None  # arte original
        self._artwork_job: str | None = None
        self._status_job: str | None = None
        # Transição de tema: foto do tema antigo, por cima da janela.
        self._cover = ctk_adapter.WindowCover(self._root)
        self._fading = 0  # conta as trocas; passos de uma troca antiga param
        self._images: dict[tuple, PixelImage] = {}  # cursor, ♀ e ♂ por cor
        # Títulos desenhados como imagem e o que cada um mostra, para
        # redesenhar se a escala da tela mudar (veja _set_title).
        self._titles: dict[ctk.CTkLabel, tuple] = {}

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
        # Se a janela for para um monitor com outra escala, ajusta de novo.
        ctk.ScalingTracker.add_widget(self._on_scaling_change, self._root)
        # Teclado: setas trocam o Pokémon (com o foco na lista ou na busca)
        # e Ctrl+F leva à busca.
        self._root.bind("<Up>", lambda _event: self._move_selection(-1))
        self._root.bind("<Down>", lambda _event: self._move_selection(1))
        for key in ("<Control-f>", "<Control-F>"):
            self._root.bind(key, lambda _event: self._focus_search())
        self._show_status("Carregando a Pokédex...")
        self._details.submit(
            repository.list_entries, self._show_entries,
            on_error=partial(self._report_error, LIST_ERROR),
            priority=PRIORITY_NOW,
        )

    def run(self) -> None:
        self._root.mainloop()

    def _create_fonts(self) -> None:
        """Press Start 2P nos títulos e números; Jersey 10 no resto.

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

    def _snap_title_fonts(self, widget_scaling: float) -> None:
        """Mantém a Press Start 2P em múltiplos de 8 px na tela."""
        for font, size in self._grid_fonts:
            font.configure(size=pixel_font_size(size, widget_scaling))
        for label, title in self._titles.items():
            label.configure(image=self._title_image(*title))

    def _on_scaling_change(self, widget_scaling: float, *_args) -> None:
        self._snap_title_fonts(widget_scaling)
        self._list.rescale()

    def _set_title(
        self,
        label: ctk.CTkLabel,
        text: str,
        size: int,
        color: str | ThemeColor,
        symbol: str | None = None,
    ) -> None:
        """Mostra um texto da Press Start 2P como imagem, sem ClearType.

        Sem as fontes pixeladas, mostra como texto comum na fonte do label.
        """
        if not self._pixel_fonts:
            label.configure(text=text + (symbol or ""), text_color=color)
            return
        self._titles[label] = (text, size, color, symbol)
        label.configure(image=self._title_image(text, size, color, symbol))

    def _title_image(
        self,
        text: str,
        size: int,
        color: str | ThemeColor,
        symbol: str | None,
    ) -> ctk.CTkImage:
        """Imagem do texto já no tamanho final da tela, nos dois temas.

        O CTkImage recebe o tamanho dividido pela escala; ao multiplicar de
        volta, ele não precisa ampliar nada e os pixels ficam intactos.
        """
        scaling = ctk.ScalingTracker.get_widget_scaling(self._root)
        on_screen = round(pixel_font_size(size, scaling) * scaling)
        light, dark = (color, color) if isinstance(color, str) else color
        images = [
            self._draw_title(text, on_screen, ink, symbol)
            for ink in (light, dark)
        ]
        width, height = images[0].size
        return ctk.CTkImage(
            *images, size=(width / scaling, height / scaling)
        )

    @staticmethod
    def _draw_title(
        text: str, size: int, color: str, symbol: str | None
    ) -> Image.Image:
        """Desenha o texto e, se houver, ♀/♂ logo depois, na mesma grade."""
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
        self, symbol: str, color: str | ThemeColor
    ) -> PixelImage:
        """♀ ou ♂ da lista, na cor do nome (desenhados para FONT_LIST_NAME).

        No card principal, o símbolo vai dentro da imagem do nome.
        """
        key = (symbol, color)
        if key not in self._images:
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
        title = self._label(header, "", self._title_font)
        self._set_title(title, "Pokédex", FONT_TITLE, TEXT_COLOR)
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

        # A lista é um canvas só (veja pokemon_list): rolar, filtrar e
        # trocar o tema não mexem em centenas de widgets.
        self._list = PokemonList(
            sidebar,
            number_font=self._list_number_font,
            name_font=self._list_name_font,
            message_font=self._body_font,
            split_name=self._split_name,
            cursor_image=self._cursor_image,
            symbol_image=self._symbol_image,
            on_click=self._select,
        )
        self._list.frame.grid(
            row=3, column=0, sticky="nsew",
            padx=WINDOW_MARGIN, pady=(0, WINDOW_MARGIN),
        )

    def _build_theme_button(self, parent: ctk.CTkFrame) -> ctk.CTkButton:
        """Botão que alterna entre os temas claro e escuro.

        O ícone mostra para onde o clique leva: lua no tema claro, sol no
        escuro. O CTkImage troca de versão sozinho quando o tema muda.
        """
        light, dark = MUTED_COLOR
        button = IconButton(
            parent,
            text="",
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
        # Teclado: entra na ordem do Tab e responde a Enter e espaço. Com o
        # foco, ganha um anel neutro (como a busca) e mostra a dica na hora.
        tk.Frame.configure(button, takefocus=True)
        for key in ("<Return>", "<KP_Enter>", "<space>"):
            tk.Misc.bind(button, key, lambda _event: button.invoke())

        def focus(focused: bool) -> None:
            button.configure(border_width=FOCUS_BORDER_WIDTH if focused else 0)
            if focused:
                tip.show()
            else:
                tip.hide()

        tk.Misc.bind(button, "<FocusIn>", lambda _event: focus(True))
        tk.Misc.bind(button, "<FocusOut>", lambda _event: focus(False))
        return button

    @staticmethod
    def _theme_tip() -> str:
        """Dica do botão de tema: diz para onde o clique leva."""
        if ctk.get_appearance_mode() == "Dark":
            return "Mudar para tema claro"
        return "Mudar para tema escuro"

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
        self._search.bind("<KeyRelease>", self._on_search_key)
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
        # tipos no topo, e um contorno mais escuro que o pastel (veja
        # hero_border_color).
        self._hero = ctk.CTkFrame(
            details, corner_radius=CARD_RADIUS, fg_color=CARD_COLOR,
            border_width=CARD_BORDER_WIDTH, border_color=CARD_BORDER_COLOR,
        )
        self._hero.grid(row=0, column=0, columnspan=2, sticky="nsew")
        header = self._container(self._hero)
        header.pack(fill="x", padx=CARD_PADDING, pady=(CARD_PADDING, 0))
        # Nome e número alinhados por baixo. Na Press Start 2P, a última
        # linha da grade (1/8 da altura) fica vazia; o número sobe a
        # diferença entre as duas para as linhas de base baterem.
        self._name = self._label(
            header, "", self._hero_font, height=FONT_HERO
        )
        self._name.pack(side="left", anchor="s")
        self._number = self._label(
            header, "", self._title_font, height=FONT_TITLE
        )
        self._number.pack(
            side="left", anchor="s", padx=WIDE_GAP,
            pady=(0, (FONT_HERO - FONT_TITLE) // PIXEL_GRID),
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
        # No lugar da arte enquanto os dados não chegam (ou se falharem).
        self._art_message = self._label(
            self._art_area, "", color=MUTED_COLOR
        )
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
            value = self._label(card, "")
            value.grid(
                row=row, column=1, sticky="w",
                padx=(0, CARD_PADDING), pady=(0, bottom),
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
        # Como os outros rótulos, mas na cor do texto principal.
        total = self._label(card, "Total")
        total.grid(
            row=total_row, column=0, sticky="w",
            padx=(CARD_PADDING, ITEM_GAP), pady=(0, CARD_PADDING),
        )
        self._total = self._label(card, "", width=STAT_VALUE_WIDTH)
        self._total.grid(
            row=total_row, column=1, sticky="e", pady=(0, CARD_PADDING)
        )

    def _card_title(self, card: ctk.CTkFrame, text: str) -> ctk.CTkLabel:
        title = self._label(card, "", self._title_font)
        self._set_title(title, text, FONT_TITLE, TEXT_COLOR)
        return title

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
        self._list.set_entries(entries)
        self._show_count(len(entries))
        self._select(entries[0])
        self._load_icons()

    def _load_icons(self) -> None:
        """Baixa os ícones em paralelo, os da área visível primeiro.

        Cada um aparece assim que chega. Um ícone que falha (depois das
        novas tentativas da rede) não interrompe os outros.
        """
        in_view = set(self._list.numbers_in_view())
        numbers = self._list.visible_numbers()
        for number in sorted(numbers, key=lambda n: n not in in_view):
            self._icons.submit(
                partial(self._fetch_icon, number),
                partial(self._list.set_icon, number),
                on_error=partial(self._icon_failed, number),
                priority=PRIORITY_NOW if number in in_view else PRIORITY_ICON,
            )

    def _fetch_icon(self, number: int) -> Image.Image:
        """Roda fora da thread da interface: baixa e recorta o ícone."""
        data = self._repository.get_icon(number)
        image = Image.open(BytesIO(data)).convert("RGBA")
        return image.crop(LIST_ICON_CROP)

    @staticmethod
    def _icon_failed(number: int, error: Exception) -> None:
        # O ícone é enfeite: a linha continua usável sem ele.
        logger.warning("Ícone do #%03d não carregou: %s", number, error)

    def _show_count(self, shown: int) -> None:
        """"151 Pokémon" sem busca; "2 de 151" durante a busca."""
        total = self._list.total
        self._count_text = (
            f"{shown} de {total}" if self._query else f"{total} Pokémon"
        )
        self._show_status(self._count_text)

    def _visible_numbers(self) -> list[int]:
        """Números das linhas que a busca deixou à mostra, em ordem."""
        return self._list.visible_numbers()

    def _move_selection(self, step: int) -> str:
        """Seta para cima (-1) ou para baixo (+1): seleciona o vizinho."""
        self._flush_filter()
        visible = self._visible_numbers()
        if visible:
            if self._selected in visible:
                index = visible.index(self._selected) + step
                index = max(0, min(index, len(visible) - 1))
            else:
                index = 0  # a seleção sumiu na busca: vai ao primeiro
            self._select(self._list.entry(visible[index]))
        return "break"  # a tecla já foi tratada

    def _open_first_result(self) -> str:
        self._flush_filter()
        visible = self._visible_numbers()
        if visible:
            self._select(self._list.entry(visible[0]))
        return "break"

    def _focus_search(self) -> str:
        self._search.focus_set()
        self._search.select_range(0, "end")  # digitar substitui a busca
        return "break"

    def _on_search_key(self, _event: tk.Event | None = None) -> None:
        """A cada tecla, o "×" aparece ou some na hora; a busca espera
        FILTER_DELAY_MS depois da última tecla e roda uma vez só."""
        if self._search.get():
            if not self._clear_button.winfo_manager():
                ctk_adapter.sync_backgrounds(self._clear_button)  # bug A
            self._clear_button.grid()
        else:
            self._clear_button.grid_remove()
        if self._filter_job is not None:
            self._root.after_cancel(self._filter_job)
        self._filter_job = self._root.after(
            FILTER_DELAY_MS, self._apply_filter
        )

    def _flush_filter(self) -> None:
        """Aplica já a busca que estava esperando (Enter, setas)."""
        if self._filter_job is not None:
            self._root.after_cancel(self._filter_job)
            self._apply_filter()

    def _apply_filter(self) -> None:
        self._filter_job = None
        query = self._search.get().strip().lower()
        if query == self._query:
            return  # teclas como as setas não mudam o texto
        self._query = query
        self._show_count(self._list.filter(query))

    def _clear_search(self) -> None:
        if self._filter_job is not None:
            self._root.after_cancel(self._filter_job)
            self._filter_job = None
        self._search.delete(0, "end")
        self._search.focus_set()
        self._clear_button.grid_remove()
        self._apply_filter()

    def _paint_search_border(self, focused: bool | None = None) -> None:
        """Borda de 2 px, numa cor neutra, quando o campo tem foco."""
        if focused is not None:
            self._search_focused = focused
        if self._search_focused:
            self._search_box.configure(
                border_width=FOCUS_BORDER_WIDTH, border_color=FOCUS_COLOR
            )
        else:
            self._search_box.configure(
                border_width=BORDER_WIDTH, border_color=BORDER_COLOR
            )

    def _select(self, entry: PokedexEntry) -> None:
        self._list.scroll_to(entry.number)
        if entry.number == self._selected and (
            self._shown == entry.number or self._loading is not None
        ):
            return  # já está na tela ou a caminho
        self._selected = entry.number
        # Cinza enquanto carrega; ao terminar, ganha o pastel do card.
        self._list.set_selection(
            entry.number, ELEVATED_COLOR, TEXT_COLOR, self._accent
        )
        self._load(entry)

    # --- Carregamento e exibição do Pokémon ----------------------------

    def _load(self, entry: PokedexEntry) -> None:
        if self._loading is not None:
            self._loading.cancel()  # o anterior não interessa mais
        self._cancel_status_delay()
        self._cancel_loading_card()
        self._status_job = self._root.after(
            STATUS_DELAY_MS, self._show_status, f"Carregando {entry.name}..."
        )
        self._loading_job = self._root.after(
            LOADING_DELAY_MS, self._loading_delay_over, entry
        )
        self._loading = self._details.submit(
            partial(self._fetch, entry.number),
            self._show_pokemon,
            on_error=partial(self._load_failed, entry),
            priority=PRIORITY_NOW,
        )

    def _fetch(self, number: int) -> tuple[Pokemon, Image.Image]:
        """Roda fora da thread da interface: baixa dados e prepara a imagem."""
        pokemon = self._repository.get_pokemon(number)
        image = Image.open(BytesIO(self._repository.get_artwork(pokemon)))
        image.thumbnail((ARTWORK_MAX_SIZE, ARTWORK_MAX_SIZE))
        return pokemon, image

    def _warm_cache(self, number: int) -> None:
        """Pré-carga: só baixa para o cache, sem preparar a imagem."""
        self._repository.get_artwork(self._repository.get_pokemon(number))

    def _prefetch_neighbors(self, number: int) -> None:
        """Baixa em segundo plano o anterior e o próximo da lista.

        Vizinhos de uma escolha anterior que ainda não começaram são
        cancelados: navegando rápido, a fila não acumula.
        """
        visible = self._visible_numbers()
        if number not in visible:
            return
        index = visible.index(number)
        neighbors = [
            neighbor for neighbor in visible[max(index - 1, 0):index + 2]
            if neighbor != number
        ]
        for old in list(self._prefetching):
            if old not in neighbors:
                self._prefetching.pop(old).cancel()
                self._prefetched.discard(old)
        for neighbor in neighbors:
            if neighbor in self._prefetched:
                continue
            self._prefetched.add(neighbor)
            self._prefetching[neighbor] = self._prefetch.submit(
                partial(self._warm_cache, neighbor),
                partial(self._prefetch_done, neighbor),
                on_error=partial(self._prefetch_failed, neighbor),
            )

    def _prefetch_done(self, number: int, _result: None) -> None:
        self._prefetching.pop(number, None)

    def _prefetch_failed(self, number: int, error: Exception) -> None:
        self._prefetching.pop(number, None)
        self._prefetched.discard(number)  # tenta de novo numa próxima vez
        logger.info("Pré-carga do #%03d falhou: %s", number, error)

    def _cancel_loading_card(self) -> None:
        if self._loading_job is not None:
            self._root.after_cancel(self._loading_job)
            self._loading_job = None

    def _loading_delay_over(self, entry: PokedexEntry) -> None:
        """Os dados não chegaram no prazo: mostra o card de espera.

        Antes, entrega o que já ficou pronto. Com o Pokémon no cache, os
        dados já estão prontos e entram direto, sem o card de espera.
        """
        self._loading_job = None
        self._details.deliver_ready()
        self._show_loading_card(entry, LOADING)

    def _show_loading_card(self, entry: PokedexEntry, message: str) -> None:
        """Card só com nome, número e um aviso no lugar da arte.

        Aparece quando os dados demoram (ou falham), para o clique ter
        resposta na hora.
        """
        self._loading_job = None
        if entry.number != self._selected or entry.number == self._shown:
            return
        self._shown = None  # o card já não mostra o Pokémon anterior
        self._hero.configure(
            fg_color=CARD_COLOR, border_color=CARD_BORDER_COLOR
        )
        name, symbol = self._split_name(entry.name)
        self._set_title(self._name, name, FONT_HERO, TEXT_COLOR, symbol)
        self._set_title(
            self._number, format_number(entry.number), FONT_TITLE,
            MUTED_COLOR,
        )
        clear(self._badges)
        self._artwork.place_forget()
        self._art_message.configure(text=message)
        if not self._art_message.winfo_manager():
            ctk_adapter.sync_backgrounds(self._art_message)  # bug A
            self._art_message.place(relx=0.5, rely=0.5, anchor="center")
        for value_label, bar in self._stat_widgets:
            value_label.configure(text=NO_VALUE)
            bar.set(0)
        self._total.configure(text=NO_VALUE)
        for name_label, tag in self._ability_rows:
            name_label.configure(text="")
            tag.pack_forget()
        for measure in self._measures:
            measure.configure(text=NO_VALUE)

    def _load_failed(self, entry: PokedexEntry, error: Exception) -> None:
        if entry.number != self._selected:
            return  # o usuário já escolheu outro Pokémon
        self._loading = None
        self._cancel_loading_card()
        if isinstance(error, OSError):
            message = CONNECTION_ERROR
        else:
            message = LOAD_ERROR.format(name=entry.name)
        # Nunca fica preso em "Carregando...": o card e a lateral avisam.
        self._show_loading_card(entry, message)
        self._report_error(message, error)

    def _show_pokemon(self, result: tuple[Pokemon, Image.Image]) -> None:
        pokemon, image = result
        if pokemon.number != self._selected:
            return  # chegou tarde: o usuário já escolheu outro Pokémon
        self._loading = None
        self._cancel_loading_card()
        self._shown = pokemon.number
        color = type_styles(pokemon)[0].color
        background = pastel(color)
        text_color = readable_text_color(background)

        self._hero.configure(
            fg_color=background, border_color=hero_border_color(color)
        )
        self._art_message.place_forget()
        if not self._artwork.winfo_manager():
            ctk_adapter.sync_backgrounds(self._artwork)  # bug A
            self._artwork.place(relx=0.5, rely=0.5, anchor="center")
        self._artwork_image = image
        self._render_artwork()
        name, symbol = self._split_name(pokemon.name)
        self._set_title(self._name, name, FONT_HERO, text_color, symbol)
        self._set_title(
            self._number, format_number(pokemon.number), FONT_TITLE,
            hero_number_color(background),
        )
        self._accent = bar_color(color)
        self._list.set_selection(
            pokemon.number, background, text_color, self._accent
        )

        height_label, weight_label = self._measures
        height_label.configure(text=format_measure(pokemon.height, "m"))
        weight_label.configure(text=format_measure(pokemon.weight, "kg"))

        clear(self._badges)
        for style in type_styles(pokemon):
            badge = self._type_badge(self._badges, style)
            badge.pack(side="left", padx=(ITEM_GAP, 0))

        stats = zip(self._stat_widgets, stat_rows(pokemon), strict=True)
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
                ctk_adapter.sync_backgrounds(tag)  # bug A
                tag.pack(side="left", padx=ITEM_GAP)
            else:
                tag.pack_forget()
        self._show_status(self._count_text)
        self._prefetch_neighbors(pokemon.number)

    # --- Tema -------------------------------------------------------------

    def _toggle_theme(self) -> None:
        """Troca entre claro e escuro e guarda a escolha para a próxima vez.

        Uma foto do tema antigo cobre a janela e esmaece sobre o tema novo:
        a troca fica suave, sem mostrar os widgets se redesenhando.
        """
        theme = "light" if ctk.get_appearance_mode() == "Dark" else "dark"
        self._fading += 1  # passos pendentes de uma troca anterior param
        covered = self._cover.show()  # sem foto, a troca é direta
        ctk.set_appearance_mode(theme)
        save_theme(SETTINGS_PATH, theme)
        if covered:
            self._root.update_idletasks()  # o tema novo, já desenhado
            self._fade_step(self._fading, 1)
        else:
            self._cover.hide()  # a foto de uma troca anterior, se sobrou

    def _fade_step(self, fade: int, step: int) -> None:
        if fade != self._fading:
            return  # outra troca começou e pôs uma foto nova
        if step > FADE_STEPS:
            self._cover.hide()
            return
        self._cover.set_opacity(1 - ease_out(step / FADE_STEPS))
        self._root.after(
            FADE_MS // FADE_STEPS, self._fade_step, fade, step + 1
        )

    def _set_window_icon(self) -> None:
        """Troca o ícone padrão do CustomTkinter pelo da Pokédex.

        Precisa vir logo depois de criar a janela: o CustomTkinter só põe
        o ícone dele se ninguém tiver chamado iconbitmap antes.
        """
        try:
            self._root.iconbitmap(str(ICON_PATH))
        except tk.TclError:
            logger.info("Ícone da janela não aceito neste sistema.")

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

    # --- Avisos -----------------------------------------------------------

    def _report_error(self, message: str, error: Exception) -> None:
        """Erro nunca fica em silêncio: vai para o log e para a lateral."""
        if isinstance(error, OSError):
            logger.warning("%s (%s)", message, error)
        else:
            logger.error(message, exc_info=error)
        self._show_status(message, ERROR_COLOR)

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
        self._details.close()
        self._prefetch.close()
        self._icons.close()
        self._cover.destroy()
        self._root.destroy()
