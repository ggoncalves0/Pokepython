"""Lista da Pokédex desenhada num único tk.Canvas.

Com quatro widgets do CustomTkinter por linha (606 no total, ou 1516
janelas do Windows), rolar movia as 1516 janelas, e cada uma se repintava
num momento diferente: as linhas apareciam rasgadas. Limpar a busca
repintava todas, com a lista vazia por quase um segundo, e trocar o tema
as repintava uma a uma. Aqui cada linha é um punhado de itens do canvas
(ícone, número, nome): rolar, filtrar e trocar o tema são operações sobre
itens, que o Tk desenha de uma vez.
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
    SCROLLBAR_RIGHT_GAP,
    SCROLLBAR_WIDTH,
    SIDEBAR_COLOR,
    TEXT_COLOR,
    Color,
)

NO_RESULTS = "Nenhum Pokémon encontrado"
NO_RESULTS_Y = 4
# O ícone começa no recuo da busca, alinhado com a lupa.
NUMBER_X = CONTROL_PADDING + LIST_ICON_SIZE[0] + ITEM_GAP // 2
NAME_X = NUMBER_X + NUMBER_WIDTH + ITEM_GAP
# Antes do primeiro desenho o canvas mede 1 px; supõe a lista da janela
# inicial para saber quais ícones baixar primeiro.
INITIAL_ROWS_IN_VIEW = 16
WINDOWS_WHEEL_DELTA = 120
WHEEL_PIXELS_PER_NOTCH = 20


def format_number(number: int) -> str:
    return f"#{number:03}"


def resolve(color: Color) -> str:
    """O canvas não entende o par (claro, escuro): fica a cor do tema
    atual."""
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
    name_without_symbol: str
    symbol: str | None
    tag: str
    number_item: int = 0
    name_item: int = 0
    icon_item: int = 0
    symbol_item: int | None = None
    top: int = 0
    matches: bool = True


class PokemonList:
    """`frame` é o widget a posicionar na tela."""

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
        self._scrollbar.grid(
            row=0, column=1, sticky="ns", padx=(0, SCROLLBAR_RIGHT_GAP)
        )
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._rows: dict[int, _Row] = {}
        self._all_numbers: list[int] = []
        self._matching: list[int] = []
        self._content_height = 0
        self._selected: int | None = None
        self._hovered: int | None = None
        self._focused = False
        self._selection_background: Color = ELEVATED_COLOR
        self._selection_text: Color = TEXT_COLOR
        self._ring_color: Color = MUTED_COLOR
        self._icons: dict[int, Image.Image] = {}
        self._icon_photos: dict[int, ImageTk.PhotoImage] = {}
        # O Tk apaga uma imagem quando o Python a descarta: guarda a que
        # cada item do canvas está mostrando (cursor e ♀/♂).
        self._photos_in_use: dict[int, ImageTk.PhotoImage] = {}

        self._measure()
        self._create_fixed_items()
        self._bind_events()
        self._unsubscribe = ctk_adapter.on_appearance_change(
            lambda _mode: self.apply_theme()
        )
        self.apply_theme()

    @property
    def total(self) -> int:
        return len(self._all_numbers)

    @property
    def row_pitch(self) -> int:
        return self._pitch

    def entry(self, number: int) -> PokedexEntry:
        return self._rows[number].entry

    def all_numbers(self) -> list[int]:
        return list(self._all_numbers)

    def matching_numbers(self) -> list[int]:
        return list(self._matching)

    def numbers_in_view(self) -> list[int]:
        height = self._canvas.winfo_height()
        if height <= 1:
            height = self._pitch * INITIAL_ROWS_IN_VIEW
        top = int(self._canvas.canvasy(0))
        first, last = top // self._pitch, (top + height) // self._pitch
        return self._matching[first:last + 1]

    def icon_count(self) -> int:
        return len(self._icon_photos)

    def set_entries(self, entries: list[PokedexEntry]) -> None:
        for row in self._rows.values():
            self._canvas.delete(row.tag)
        self._rows.clear()
        self._all_numbers = []
        for entry in entries:
            name_without_symbol, symbol = self._split_name(entry.name)
            row = _Row(
                entry=entry,
                search_text=f"{format_number(entry.number)} {entry.name}"
                .lower(),
                name_without_symbol=name_without_symbol,
                symbol=symbol,
                tag=f"row{entry.number}",
            )
            self._rows[entry.number] = row
            self._all_numbers.append(entry.number)
            self._create_row(row)
        self._relayout()

    def set_icon(self, number: int, image: Image.Image) -> None:
        self._icons[number] = image
        row = self._rows.get(number)
        if row is not None:
            photo = self._icon_photo(image)
            self._icon_photos[number] = photo
            self._canvas.itemconfigure(row.icon_item, image=photo)

    def filter(self, query: str) -> int:
        for row in self._rows.values():
            matches = query in row.search_text
            if matches != row.matches:
                row.matches = matches
                self._canvas.itemconfigure(
                    row.tag, state="normal" if matches else "hidden"
                )
        self._relayout()
        # Com a lista rolada, os resultados ficariam fora da vista.
        self._canvas.yview_moveto(0)
        return len(self._matching)

    def set_selection(
        self,
        number: int | None,
        background: Color,
        text: Color,
        ring_color: Color,
    ) -> None:
        previous, self._selected = self._selected, number
        self._selection_background = background
        self._selection_text = text
        self._ring_color = ring_color
        if previous is not None and previous != number:
            self._paint_row_text(previous)
        if number is not None:
            self._paint_row_text(number)
        self._paint_selection()
        self._paint_hover()

    def scroll_into_view(self, number: int) -> None:
        row = self._rows.get(number)
        height = self._canvas.winfo_height()
        if row is None or not row.matches or height <= 1:
            return
        total = max(self._content_height, 1)
        view_top = self._canvas.canvasy(0)
        bottom = row.top + self._row_height
        if row.top < view_top:
            self._canvas.yview_moveto(row.top / total)
        elif bottom > view_top + height:
            self._canvas.yview_moveto((bottom - height) / total)

    def click_at(self, y: int) -> None:
        self._canvas.focus_set()
        number = self._row_at(y)
        if number is not None:
            self._on_click(self._rows[number].entry)

    def focus_set(self) -> None:
        self._canvas.focus_set()

    def apply_theme(self) -> None:
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
        self._measure()
        self._canvas.delete("all")
        self._photos_in_use.clear()
        self._create_fixed_items()
        self._icon_photos = {
            number: self._icon_photo(image)
            for number, image in self._icons.items()
        }
        for number in self._all_numbers:
            row = self._rows[number]
            self._create_row(row)
            if not row.matches:
                self._canvas.itemconfigure(row.tag, state="hidden")
        self._relayout()
        self.apply_theme()

    def _bind_events(self) -> None:
        canvas = self._canvas
        canvas.bind("<Configure>", self._on_resize)
        canvas.bind("<Motion>", self._on_motion)
        canvas.bind("<Leave>", self._on_leave)
        canvas.bind("<Button-1>", lambda event: self.click_at(event.y))
        canvas.bind("<MouseWheel>", self._on_wheel)
        canvas.bind("<FocusIn>", lambda _event: self._set_focus(True))
        canvas.bind("<FocusOut>", lambda _event: self._set_focus(False))
        canvas.bind("<Destroy>", self._on_destroy, add="+")

    def _px(self, value: float) -> int:
        return round(value * self._scaling)

    def _measure(self) -> None:
        self._scaling: float = ctk.ScalingTracker.get_widget_scaling(
            self.frame
        )
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
            self._px(CONTROL_PADDING), self._px(NO_RESULTS_Y), anchor="nw",
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
            self._px(NAME_X), middle, anchor="w",
            text=row.name_without_symbol, font=self._name_font,
            tags=(row.tag, "text"),
        )
        row.symbol_item = None
        if row.symbol is not None:
            # A imagem do símbolo já traz o espaço antes dele.
            x = self._px(NAME_X) + self._name_metrics.measure(
                row.name_without_symbol
            )
            row.symbol_item = canvas.create_image(
                x, middle, anchor="w", tags=tags
            )
        row.top = 0
        self._paint_row_text(number)

    def _relayout(self) -> None:
        y = 0
        self._matching = []
        for number in self._all_numbers:
            row = self._rows[number]
            if not row.matches:
                continue
            if row.top != y:
                self._canvas.move(row.tag, 0, y - row.top)
                row.top = y
            self._matching.append(number)
            y += self._pitch
        self._content_height = y
        self._canvas.configure(
            scrollregion=(0, 0, self._canvas.winfo_width(), max(y, 1))
        )
        no_results = bool(self._rows) and not self._matching
        self._canvas.itemconfigure(
            self._message, state="normal" if no_results else "hidden"
        )
        self._paint_selection()
        self._paint_hover()
        self._update_scrollbar()

    def _paint_row_text(self, number: int) -> None:
        row = self._rows.get(number)
        if row is None:
            return
        color = (
            self._selection_text if number == self._selected else TEXT_COLOR
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
        self._canvas.delete("ring", "selection")
        selected = self._selected
        row = self._rows.get(selected) if selected is not None else None
        if row is None or not row.matches:
            self._canvas.itemconfigure(self._cursor, state="hidden")
            return
        self._draw_selection_background(row)
        self._place_cursor(row)

    def _draw_selection_background(self, row: _Row) -> None:
        x1, radius = self._canvas.winfo_width(), self._px(ROW_RADIUS)
        y0, y1 = row.top, row.top + self._row_height
        background = resolve(self._selection_background)
        if self._focused:
            ring = self._px(FOCUS_BORDER_WIDTH)
            self._shape(
                "ring", 0, y0, x1, y1, radius, resolve(self._ring_color)
            )
            self._shape(
                "selection", ring, y0 + ring, x1 - ring, y1 - ring,
                max(radius - ring, 0), background,
            )
        else:
            self._shape("selection", 0, y0, x1, y1, radius, background)
        self._canvas.tag_lower("selection")
        self._canvas.tag_lower("ring")

    def _place_cursor(self, row: _Row) -> None:
        cursor = self._cursor
        self._set_image(cursor, self._cursor_image(self._selection_text))
        self._canvas.itemconfigure(cursor, state="normal")
        self._canvas.coords(
            cursor, self._px(CURSOR_X), row.top + self._center
        )
        self._canvas.tag_raise(cursor)

    def _paint_hover(self) -> None:
        canvas = self._canvas
        canvas.delete("hover")
        number = self._hovered
        row = self._rows.get(number) if number is not None else None
        if row is None or not row.matches or number == self._selected:
            return
        self._shape(
            "hover", 0, row.top, canvas.winfo_width(),
            row.top + self._row_height, self._px(ROW_RADIUS),
            resolve(ELEVATED_COLOR),
        )
        canvas.tag_lower("hover")

    def _set_image(self, item: int, image: PixelImage) -> None:
        mode = "dark" if ctk.get_appearance_mode() == "Dark" else "light"
        photo = image.create_scaled_photo_image(self._scaling, mode)
        self._photos_in_use[item] = photo
        self._canvas.itemconfigure(item, image=photo)

    def _icon_photo(self, image: Image.Image) -> ImageTk.PhotoImage:
        if self._scaling != 1:  # pixel art: NEAREST amplia sem borrar
            size = (self._px(image.width), self._px(image.height))
            image = image.resize(size, Image.Resampling.NEAREST)
        return ImageTk.PhotoImage(image)

    def _update_scrollbar(self) -> None:
        height = self._canvas.winfo_height()
        fits = height > 1 and self._content_height <= height
        if fits and self._scrollbar.winfo_manager():
            self._scrollbar.grid_remove()
        elif not fits and not self._scrollbar.winfo_manager():
            # Ao voltar, a barra às vezes não se repintava (veja
            # ctk_adapter).
            ctk_adapter.reveal(self._scrollbar, "grid")
            self.frame.after_idle(ctk_adapter.repaint, self._scrollbar)

    def _row_at(self, y: int) -> int | None:
        index, offset = divmod(int(self._canvas.canvasy(y)), self._pitch)
        if offset >= self._row_height or not (
            0 <= index < len(self._matching)
        ):
            return None
        return self._matching[index]

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
            self._canvas.configure(cursor="" if number is None else "hand2")

    def _on_leave(self, _event: tk.Event) -> None:
        if self._hovered is not None:
            self._hovered = None
            self._paint_hover()
            self._canvas.configure(cursor="")

    def _on_wheel(self, event: tk.Event) -> None:
        if self._content_height > self._canvas.winfo_height():
            pixels = -round(
                event.delta * WHEEL_PIXELS_PER_NOTCH / WINDOWS_WHEEL_DELTA
            )
            self._canvas.yview_scroll(pixels, "units")

    def _set_focus(self, focused: bool) -> None:
        self._focused = focused
        self._paint_selection()

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is self._canvas:
            self._unsubscribe()
