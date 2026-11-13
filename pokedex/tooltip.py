"""Dica curta que aparece perto de um widget.

O CustomTkinter não tem dicas prontas. Esta aparece depois de o mouse
parar um instante sobre o widget, ou logo que ele recebe o foco pelo
teclado, e some ao sair, ao clicar ou ao perder o foco.
"""

import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from .theme import CARD_COLOR, TEXT_COLOR

HOVER_DELAY_MS = 500
GAP_BELOW_WIDGET = 4
PADDING_X = 8
PADDING_Y = 4


class Tooltip:
    """O texto vem de uma função porque pode mudar, como o do botão de
    tema."""

    def __init__(
        self, widget: ctk.CTkBaseClass, text: Callable[[], str],
        font: ctk.CTkFont,
    ) -> None:
        self._widget = widget
        self._text = text
        self._font = font
        self._window: tk.Toplevel | None = None
        self._job: str | None = None
        # O CTkButton repassa estes eventos às partes dele (fundo e ícone).
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<Button-1>", self.hide, add="+")

    def _schedule(self, _event: tk.Event | None = None) -> None:
        if self._job is None and self._window is None:
            self._job = self._widget.after(HOVER_DELAY_MS, self.show)

    def _leave(self, _event: tk.Event | None = None) -> None:
        # Passar de uma parte do widget para outra também gera <Leave>.
        if not self._pointer_inside():
            self.hide()

    def _pointer_inside(self) -> bool:
        x, y = self._widget.winfo_pointerxy()
        left, top = self._widget.winfo_rootx(), self._widget.winfo_rooty()
        return bool(
            left <= x < left + self._widget.winfo_width()
            and top <= y < top + self._widget.winfo_height()
        )

    def show(self, _event: tk.Event | None = None) -> None:
        self.hide()
        scaling = ctk.ScalingTracker.get_widget_scaling(self._widget)
        window = self._create_window(scaling)
        window.geometry(self._position_below(window, scaling))
        window.deiconify()
        self._window = window

    def _create_window(self, scaling: float) -> tk.Toplevel:
        dark = ctk.get_appearance_mode() == "Dark"
        window = tk.Toplevel(self._widget)
        window.withdraw()
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        # Cores invertidas: a dica se destaca do fundo nos dois temas.
        tk.Label(
            window, text=self._text(),
            font=self._font.create_scaled_tuple(scaling),
            bg=TEXT_COLOR[dark], fg=CARD_COLOR[dark],
            padx=round(PADDING_X * scaling), pady=round(PADDING_Y * scaling),
        ).pack()
        window.update_idletasks()
        return window

    def _position_below(self, window: tk.Toplevel, scaling: float) -> str:
        # Alinhada pela direita: o botão de tema fica no canto da janela, e
        # uma dica alinhada pela esquerda sairia dela.
        x = (
            self._widget.winfo_rootx() + self._widget.winfo_width()
            - window.winfo_reqwidth()
        )
        y = (
            self._widget.winfo_rooty() + self._widget.winfo_height()
            + round(GAP_BELOW_WIDGET * scaling)
        )
        return f"+{x}+{y}"

    def hide(self, _event: tk.Event | None = None) -> None:
        if self._job is not None:
            self._widget.after_cancel(self._job)
            self._job = None
        if self._window is not None:
            self._window.destroy()
            self._window = None
