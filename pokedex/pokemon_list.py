"""Lista da Pokédex desenhada num único tk.Canvas.

Antes, cada linha tinha quatro widgets do CustomTkinter: 606 no total, ou
1516 janelas do Windows. Rolar movia as 1516 janelas, e cada uma se
repintava num momento diferente (linhas rasgadas, bug B); limpar a busca
recriava e repintava todas, com a lista vazia por quase um segundo; e
trocar o tema repintava uma a uma. Aqui cada linha é um punhado de itens
do canvas (ícone, número, nome): rolar, filtrar e trocar o tema são
operações sobre itens, que o Tk desenha de uma vez.
"""

import math
import tkinter as tk
import tkinter.font
from collections.abc import Callable
from dataclasses import dataclass

import customtkinter as ctk
from PIL import Image, ImageTk

from . import ctk_adapter
from .models import PokedexEntry
from .pixel import PixelImage
from .theme import (
    CONTROL_PADDING,
    CURSOR_X,
    ELEVATED_COLOR,
    FOCUS_BORDER_WIDTH,
    ITEM_GAP,
    LIST_ICON_SIZE,
    LIST_WIDTH,
    MUTED_COLOR,
    NUMBER_WIDTH,
    ROW_GAP,
    ROW_HEIGHT,
    ROW_RADIUS,
    SCROLLBAR_COLOR,
    SCROLLBAR_HOVER_COLOR,
    SCROLLBAR_WIDTH,
    SIDEBAR_COLOR,
    TEXT_COLOR,
    ThemeColor,
)

NO_RESULTS = "Nenhum Pokémon encontrado"
# Colunas da linha, em px lógicos: cursor no recuo, ícone alinhado com a
# lupa da busca, número e nome.
NUMBER_X = CONTROL_PADDING + LIST_ICON_SIZE[0] + ITEM_GAP // 2
NAME_X = NUMBER_X + NUMBER_WIDTH + ITEM_GAP
MESSAGE_Y = 4  # recuo do aviso de busca sem resultado

type Color = str | ThemeColor


def format_number(number: int) -> str:
    return f"#{number:03}"


def resolve(color: Color) -> str:
    """A cor no tema atual: o canvas não entende o par (claro, escuro)."""
    if isinstance(color, str):
        return color
    light, dark = color
    return dark if ctk.get_appearance_mode() == "Dark" else light


def rounded_rect_bands(
    x0: int, y0: int, x1: int, y1: int, radius: int
) -> list[tuple[int, int, int, int]]:
    """Retângulos cuja união é um retângulo de cantos arredondados.

    Os cantos saem em degraus de pixel, no estilo 8-bit, e iguais nos
    quatro lados (o desenho do CustomTkinter deixava cada canto de um
    jeito).
    """
    radius = max(0, min(radius, (x1 - x0) // 2, (y1 - y0) // 2))
    insets = [
        radius - round(math.sqrt(max(radius**2 - (radius - i - 0.5) ** 2, 0)))
        for i in range(radius)
    ]
    bands: list[tuple[int, int, int, int]] = []
    previous = None
    for i, inset in enumerate([*insets, 0]):
        if inset != previous:
            bands.append((x0 + inset, y0 + i, x1 - inset, y1 - i))
            previous = inset
    return bands


@dataclass
class _Row:
    entry: PokedexEntry
    search_text: str
    text: str  # nome sem ♀/♂
    symbol: str | None
    tag: str
    number_item: int = 0
    name_item: int = 0
    icon_item: int = 0
    symbol_item: int | None = None
    top: int = 0  # posição atual, em px da tela
    shown: bool = True


class PokemonList:
    """Lista clicável, com busca, seleção, foco e ícones que chegam aos
    poucos. `frame` é o widget a posicionar na tela."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        number_font: ctk.CTkFont,
        name_font: ctk.CTkFont,
        message_font: ctk.CTkFont,
        split_name: Callable[[str], tuple[str, str | None]],
        cursor_image: Callable[[Color], PixelImage],
        symbol_image: Callable[[str, Color], PixelImage],
        on_click: Callable[[PokedexEntry], None],
    ) -> None:
        self._fonts = (number_font, name_font, message_font)
        self._split_name = split_name
        self._cursor_image = cursor_image
        self._symbol_image = symbol_image
        self._on_click = on_click

        self.frame = ctk.CTkFrame(
            master, width=0, height=0, corner_radius=0, fg_color="transparent"
        )
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        self._canvas = tk.Canvas(
            self.frame, width=1, height=1, borderwidth=0,
            highlightthickness=0, takefocus=1, yscrollincrement=1,
        )
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._scrollbar = ctk.CTkScrollbar(
            self.frame, command=self._canvas.yview, width=SCROLLBAR_WIDTH,
            fg_color="transparent", button_color=SCROLLBAR_COLOR,
            button_hover_color=SCROLLBAR_HOVER_COLOR,
        )
        # O +1 à direita é o mesmo recuo da lista antiga (veja SIDEBAR_WIDTH).
        self._scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 1))
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._rows: dict[int, _Row] = {}
        self._order: list[int] = []  # todas, na ordem da Pokédex
        self._shown_order: list[int] = []  # as que a busca deixou à mostra
        self._content_height = 0
        self._selected: int | None = None
        self._hovered: int | None = None
        self._focused = False
        self._selection_background: Color = ELEVATED_COLOR
        self._selection_text: Color = TEXT_COLOR
        self._accent: Color = MUTED_COLOR
        self._icons: dict[int, Image.Image] = {}
        self._icon_photos: dict[int, ImageTk.PhotoImage] = {}
        # O Tk apaga uma imagem quando o Python a descarta: guarda a que
        # cada item do canvas está mostrando (cursor e ♀/♂).
        self._photos_in_use: dict[int, ImageTk.PhotoImage] = {}

        self._measure()
        self._create_fixed_items()
        canvas = self._canvas
        canvas.bind("<Configure>", self._on_resize)
        canvas.bind("<Motion>", self._on_motion)
        canvas.bind("<Leave>", self._on_leave)
        canvas.bind("<Button-1>", lambda event: self.click_at(event.y))
        canvas.bind("<MouseWheel>", self._on_wheel)
        canvas.bind("<FocusIn>", lambda _event: self._set_focus(True))
        canvas.bind("<FocusOut>", lambda _event: self._set_focus(False))
        self._unsubscribe = ctk_adapter.on_appearance_change(
            lambda _mode: self.apply_theme()
        )
        canvas.bind("<Destroy>", self._on_destroy, add="+")
        self.apply_theme()

    # --- Dados ----------------------------------------------------------

    @property
    def total(self) -> int:
        return len(self._order)

    @property
    def row_pitch(self) -> int:
        """Altura de uma linha mais o vão, em px da tela."""
        return self._pitch

    def entry(self, number: int) -> PokedexEntry:
        return self._rows[number].entry

    def visible_numbers(self) -> list[int]:
        """Números das linhas que a busca deixou à mostra, em ordem."""
        return list(self._shown_order)

    def numbers_in_view(self) -> list[int]:
        """Números das linhas que aparecem agora na área visível."""
        height = self._canvas.winfo_height()
        if height <= 1:  # ainda não desenhada: supõe a altura da janela
            height = self._pitch * 16
        top = int(self._canvas.canvasy(0))
        first, last = top // self._pitch, (top + height) // self._pitch
        return self._shown_order[first:last + 1]

    def icon_count(self) -> int:
        return len(self._icon_photos)

    def set_entries(self, entries: list[PokedexEntry]) -> None:
        """Monta as linhas (de uma vez: são itens do canvas)."""
        for row in self._rows.values():
            self._canvas.delete(row.tag)
        self._rows.clear()
        self._order = []
        for entry in entries:
            text, symbol = self._split_name(entry.name)
            row = _Row(
                entry=entry,
                search_text=f"{format_number(entry.number)} {entry.name}"
                .lower(),
                text=text,
                symbol=symbol,
                tag=f"row{entry.number}",
            )
            self._rows[entry.number] = row
            self._order.append(entry.number)
            self._create_row(row)
        self._relayout()

    def set_icon(self, number: int, image: Image.Image) -> None:
        """Mostra o ícone de uma linha (chegam aos poucos, em paralelo)."""
        self._icons[number] = image
        row = self._rows.get(number)
        if row is not None:
            photo = self._icon_photo(image)
            self._icon_photos[number] = photo
            self._canvas.itemconfigure(row.icon_item, image=photo)

    # --- Busca e seleção -----------------------------------------------

    def filter(self, query: str) -> int:
        """Mostra só as linhas com `query` no número ou no nome."""
        for row in self._rows.values():
            shown = query in row.search_text
            if shown != row.shown:
                row.shown = shown
                self._canvas.itemconfigure(
                    row.tag, state="normal" if shown else "hidden"
                )
        self._relayout()
        # Volta ao topo: com a lista rolada, os resultados ficariam fora
        # da vista.
        self._canvas.yview_moveto(0)
        return len(self._shown_order)

    def set_selection(
        self,
        number: int | None,
        background: Color,
        text: Color,
        accent: Color,
    ) -> None:
        """Linha selecionada: fundo (cinza ao carregar, pastel depois),
        cor do texto e cor do anel de foco."""
        previous, self._selected = self._selected, number
        self._selection_background = background
        self._selection_text = text
        self._accent = accent
        if previous is not None and previous != number:
            self._paint_row_text(previous)
        if number is not None:
            self._paint_row_text(number)
        self._paint_selection()
        self._paint_hover()

    def scroll_to(self, number: int) -> None:
        """Rola só o necessário para a linha ficar inteira à vista."""
        row = self._rows.get(number)
        height = self._canvas.winfo_height()
        if row is None or not row.shown or height <= 1:
            return
        total = max(self._content_height, 1)
        view_top = self._canvas.canvasy(0)
        bottom = row.top + self._row_height
        if row.top < view_top:
            self._canvas.yview_moveto(row.top / total)
        elif bottom > view_top + height:
            self._canvas.yview_moveto((bottom - height) / total)

    def click_at(self, y: int) -> None:
        """Clique na altura `y` do canvas: seleciona a linha que estiver
        ali e leva o foco à lista (as setas seguem daqui)."""
        self._canvas.focus_set()
        number = self._row_at(y)
        if number is not None:
            self._on_click(self._rows[number].entry)

    def focus_set(self) -> None:
        self._canvas.focus_set()

    # --- Tema e escala --------------------------------------------------

    def apply_theme(self) -> None:
        """Recolore tudo para o tema atual: poucas chamadas, um desenho."""
        canvas = self._canvas
        canvas.configure(bg=resolve(SIDEBAR_COLOR))
        canvas.itemconfigure("text", fill=resolve(TEXT_COLOR))
        canvas.itemconfigure(self._message, fill=resolve(MUTED_COLOR))
        for number, row in self._rows.items():
            if row.symbol is not None or number == self._selected:
                self._paint_row_text(number)
        self._paint_selection()
        self._paint_hover()

    def rescale(self) -> None:
        """Refaz tudo depois de a escala da tela mudar (outro monitor)."""
        self._measure()
        self._canvas.delete("all")
        self._photos_in_use.clear()
        self._create_fixed_items()
        self._icon_photos = {
            number: self._icon_photo(image)
            for number, image in self._icons.items()
        }
        for number in self._order:
            row = self._rows[number]
            self._create_row(row)
            if not row.shown:
                self._canvas.itemconfigure(row.tag, state="hidden")
        self._relayout()
        self.apply_theme()

    # --- Desenho --------------------------------------------------------

    def _px(self, value: float) -> int:
        return round(value * self._scaling)

    def _measure(self) -> None:
        self._scaling = ctk.ScalingTracker.get_widget_scaling(self.frame)
        number_font, name_font, message_font = self._fonts
        self._number_font = number_font.create_scaled_tuple(self._scaling)
        self._name_font = name_font.create_scaled_tuple(self._scaling)
        self._message_font = message_font.create_scaled_tuple(self._scaling)
        self._name_metrics = tkinter.font.Font(
            self._canvas, font=self._name_font
        )
        self._row_height = self._px(ROW_HEIGHT)
        self._pitch = self._row_height + self._px(ROW_GAP)
        self._center = self._row_height // 2
        self._canvas.configure(width=self._px(LIST_WIDTH))

    def _create_fixed_items(self) -> None:
        self._message = self._canvas.create_text(
            self._px(CONTROL_PADDING), self._px(MESSAGE_Y), anchor="nw",
            text=NO_RESULTS, font=self._message_font,
            width=self._px(LIST_WIDTH - CONTROL_PADDING), state="hidden",
        )
        self._cursor = self._canvas.create_image(
            0, 0, anchor="w", state="hidden"
        )

    def _create_row(self, row: _Row) -> None:
        canvas, tags, middle = self._canvas, (row.tag,), self._center
        number = row.entry.number
        row.icon_item = canvas.create_image(
            self._px(CONTROL_PADDING), middle, anchor="w", tags=tags
        )
        if number in self._icon_photos:
            canvas.itemconfigure(
                row.icon_item, image=self._icon_photos[number]
            )
        row.number_item = canvas.create_text(
            self._px(NUMBER_X), middle, anchor="w",
            text=format_number(number), font=self._number_font,
            tags=(row.tag, "text"),
        )
        row.name_item = canvas.create_text(
            self._px(NAME_X), middle, anchor="w", text=row.text,
            font=self._name_font, tags=(row.tag, "text"),
        )
        row.symbol_item = None
        if row.symbol is not None:
            # ♀/♂ logo depois do nome (a imagem já traz o espaço).
            x = self._px(NAME_X) + self._name_metrics.measure(row.text)
            row.symbol_item = canvas.create_image(
                x, middle, anchor="w", tags=tags
            )
        row.top = 0
        self._paint_row_text(number)

    def _relayout(self) -> None:
        """Empilha as linhas à mostra e ajusta a área de rolagem."""
        y = 0
        self._shown_order = []
        for number in self._order:
            row = self._rows[number]
            if not row.shown:
                continue
            if row.top != y:
                self._canvas.move(row.tag, 0, y - row.top)
                row.top = y
            self._shown_order.append(number)
            y += self._pitch
        self._content_height = y
        self._canvas.configure(
            scrollregion=(0, 0, self._canvas.winfo_width(), max(y, 1))
        )
        empty = bool(self._rows) and not self._shown_order
        self._canvas.itemconfigure(
            self._message, state="normal" if empty else "hidden"
        )
        self._paint_selection()
        self._paint_hover()
        self._update_scrollbar()

    def _paint_row_text(self, number: int) -> None:
        row = self._rows.get(number)
        if row is None:
            return
        color = self._selection_text if number == self._selected else (
            TEXT_COLOR
        )
        self._canvas.itemconfigure(row.number_item, fill=resolve(color))
        self._canvas.itemconfigure(row.name_item, fill=resolve(color))
        if row.symbol is not None and row.symbol_item is not None:
            self._set_image(
                row.symbol_item, self._symbol_image(row.symbol, color)
            )

    def _shape(
        self, tag: str, x0: int, y0: int, x1: int, y1: int, radius: int,
        color: str,
    ) -> None:
        for band in rounded_rect_bands(x0, y0, x1, y1, radius):
            self._canvas.create_rectangle(
                *band, fill=color, outline="", tags=(tag,)
            )

    def _paint_selection(self) -> None:
        """Fundo da linha selecionada, anel de foco e cursor ▶."""
        canvas = self._canvas
        canvas.delete("ring", "selection")
        row = self._rows.get(self._selected) if self._selected else None
        if row is None or not row.shown:
            canvas.itemconfigure(self._cursor, state="hidden")
            return
        x1, radius = canvas.winfo_width(), self._px(ROW_RADIUS)
        y0, y1 = row.top, row.top + self._row_height
        background = resolve(self._selection_background)
        if self._focused:
            border = self._px(FOCUS_BORDER_WIDTH)
            self._shape("ring", 0, y0, x1, y1, radius, resolve(self._accent))
            self._shape(
                "selection", border, y0 + border, x1 - border, y1 - border,
                max(radius - border, 0), background,
            )
        else:
            self._shape("selection", 0, y0, x1, y1, radius, background)
        canvas.tag_lower("selection")
        canvas.tag_lower("ring")
        self._set_image(self._cursor, self._cursor_image(self._selection_text))
        canvas.itemconfigure(self._cursor, state="normal")
        canvas.coords(self._cursor, self._px(CURSOR_X), y0 + self._center)
        canvas.tag_raise(self._cursor)

    def _paint_hover(self) -> None:
        canvas = self._canvas
        canvas.delete("hover")
        number = self._hovered
        row = self._rows.get(number) if number is not None else None
        if row is None or not row.shown or number == self._selected:
            return
        self._shape(
            "hover", 0, row.top, canvas.winfo_width(),
            row.top + self._row_height, self._px(ROW_RADIUS),
            resolve(ELEVATED_COLOR),
        )
        canvas.tag_lower("hover")

    def _set_image(self, item: int, image: PixelImage) -> None:
        """Mostra `image` no item, na versão do tema e da escala atuais."""
        mode = "dark" if ctk.get_appearance_mode() == "Dark" else "light"
        photo = image.create_scaled_photo_image(self._scaling, mode)
        self._photos_in_use[item] = photo
        self._canvas.itemconfigure(item, image=photo)

    def _icon_photo(self, image: Image.Image) -> ImageTk.PhotoImage:
        if self._scaling != 1:  # pixel art: amplia sem borrar
            size = (self._px(image.width), self._px(image.height))
            image = image.resize(size, Image.Resampling.NEAREST)
        return ImageTk.PhotoImage(image)

    def _update_scrollbar(self) -> None:
        """Mostra a barra de rolagem só quando a lista não cabe inteira."""
        height = self._canvas.winfo_height()
        fits = height > 1 and self._content_height <= height
        if fits and self._scrollbar.winfo_manager():
            self._scrollbar.grid_remove()
        elif not fits and not self._scrollbar.winfo_manager():
            # Ao voltar, a barra vinha na cor do tema de abertura e às vezes
            # não se repintava (bug A; veja ctk_adapter).
            ctk_adapter.sync_backgrounds(self._scrollbar)
            self._scrollbar.grid()
            self.frame.after_idle(ctk_adapter.repaint, self._scrollbar)

    # --- Eventos --------------------------------------------------------

    def _row_at(self, y: int) -> int | None:
        index, offset = divmod(int(self._canvas.canvasy(y)), self._pitch)
        if offset >= self._row_height or not (
            0 <= index < len(self._shown_order)
        ):
            return None
        return self._shown_order[index]

    def _on_resize(self, _event: tk.Event) -> None:
        width = self._canvas.winfo_width()
        self._canvas.configure(
            scrollregion=(0, 0, width, max(self._content_height, 1))
        )
        self._paint_selection()
        self._paint_hover()
        self._update_scrollbar()

    def _on_motion(self, event: tk.Event) -> None:
        number = self._row_at(event.y)
        if number != self._hovered:
            self._hovered = number
            self._paint_hover()
            self._canvas.configure(cursor="hand2" if number else "")

    def _on_leave(self, _event: tk.Event) -> None:
        if self._hovered is not None:
            self._hovered = None
            self._paint_hover()
            self._canvas.configure(cursor="")

    def _on_wheel(self, event: tk.Event) -> None:
        if self._content_height > self._canvas.winfo_height():
            # A mesma velocidade da lista antiga (CTkScrollableFrame).
            self._canvas.yview_scroll(-int(event.delta / 6), "units")

    def _set_focus(self, focused: bool) -> None:
        self._focused = focused
        self._paint_selection()

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is self._canvas:
            self._unsubscribe()
