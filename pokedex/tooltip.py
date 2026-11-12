"""Dica curta que aparece perto de um widget.

O CustomTkinter não tem dicas prontas. Esta aparece depois de o mouse
parar um instante sobre o widget, ou logo que ele recebe o foco pelo
teclado, e some ao sair, ao clicar ou ao perder o foco.
"""

import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from .theme import CARD_COLOR, TEXT_COLOR

DELAY_MS = 500  # espera do mouse antes de mostrar
GAP = 4  # entre o widget e a dica
PADDING = (8, 4)  # recuo do texto na dica (horizontal, vertical)


class Tooltip:
    """Dica com texto calculado na hora (pode mudar, como o tema)."""

    def __init__(
        self, widget: ctk.CTkBaseClass, text: Callable[[], str],
        font: ctk.CTkFont,
    ) -> None:
        self._widget = widget
        self._text = text
        self._font = font
        self._window: tk.Toplevel | None = None
        self._job: str | None = None
        # O CTkButton repassa Enter/Leave/clique para as partes dele.
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<Button-1>", self.hide, add="+")

    def _schedule(self, _event: tk.Event | None = None) -> None:
        if self._job is None and self._window is None:
            self._job = self._widget.after(DELAY_MS, self.show)

    def _leave(self, _event: tk.Event | None = None) -> None:
        """Some só se o mouse saiu do widget, não ao passar entre as partes
        dele (fundo e ícone)."""
        x, y = self._widget.winfo_pointerxy()
        left, top = self._widget.winfo_rootx(), self._widget.winfo_rooty()
        inside = (
            left <= x < left + self._widget.winfo_width()
            and top <= y < top + self._widget.winfo_height()
        )
        if not inside:
            self.hide()

    def show(self, _event: tk.Event | None = None) -> None:
        self.hide()
        theme = 1 if ctk.get_appearance_mode() == "Dark" else 0
        scaling = ctk.ScalingTracker.get_widget_scaling(self._widget)
        window = tk.Toplevel(self._widget)
        window.withdraw()
        window.overrideredirect(True)  # sem barra de título
        window.attributes("-topmost", True)
        # Cores invertidas: a dica se destaca do fundo nos dois temas.
        tk.Label(
            window, text=self._text(),
            font=self._font.create_scaled_tuple(scaling),
            bg=TEXT_COLOR[theme], fg=CARD_COLOR[theme],
            padx=round(PADDING[0] * scaling), pady=round(PADDING[1] * scaling),
        ).pack()
        window.update_idletasks()
        # Embaixo do widget, alinhada pela direita (o botão fica no canto).
        x = (
            self._widget.winfo_rootx() + self._widget.winfo_width()
            - window.winfo_reqwidth()
        )
        y = (
            self._widget.winfo_rooty() + self._widget.winfo_height()
            + round(GAP * scaling)
        )
        window.geometry(f"+{x}+{y}")
        window.deiconify()
        self._window = window

    def hide(self, _event: tk.Event | None = None) -> None:
        if self._job is not None:
            self._widget.after_cancel(self._job)
            self._job = None
        if self._window is not None:
            self._window.destroy()
            self._window = None
