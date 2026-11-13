"""Adaptador para a API privada do CustomTkinter 6.0.0.

Tudo o que depende de detalhes internos do CustomTkinter fica neste
módulo, com o motivo de cada ajuste. Ao atualizar o CustomTkinter, rode
tests/test_ctk_adapter.py: os ajustes dependem dos números de linha
citados abaixo.

Bug A (blocos na cor do tema de abertura). Todo widget do CustomTkinter
é um tkinter.Frame com um canvas por cima. A cor desse Frame é definida
uma vez só, na criação (ctk_base_class.py, linha 68), e nunca acompanha
a troca de tema nem as mudanças de cor (linhas 104 a 108 e 122 a 130).
Normalmente o canvas e o texto cobrem o Frame, mas um widget que volta à
tela (o × da busca, a barra de rolagem) às vezes não se repinta, e o
Frame aparece. Correção, para cada widget que volta à tela:
1. reveal() acerta a cor do Frame (sync_backgrounds) enquanto ele ainda
   está escondido, e só então o mostra. Acertar todos os widgets a cada
   troca de tema saía caro (~400 ms com a lista antiga), porque cada
   mudança de cor refaz o layout do pai;
2. repaint(), depois de voltar, pede ao Windows a repintura que o hover
   fazia linha a linha no vídeo do bug.

Bug C (a tela "apaga" ao trocar o tema). install() instala dois ajustes:
1. Barra de título sem esconder a janela. No Windows, a janela principal
   chamava withdraw() e deiconify() a cada troca de tema para repintar a
   barra de título (ctk_tk.py, linhas 276 a 330): a janela sumia e
   voltava vazia. Aqui a barra muda pela mesma API do Windows
   (DwmSetWindowAttribute), e só a moldura é repintada.
2. Um redesenho só. Cada widget chamava update_idletasks() ao trocar de
   tema (ctk_base_class.py, linhas 220 a 223); com ~670 widgets, a janela
   se redesenhava aos pedaços.

Troca de tema suave: WindowCover cobre a janela com uma foto dela, que
esmaece sobre o tema novo (veja PokedexWindow._toggle_theme).
"""

import contextlib
import ctypes
import functools
import logging
import sys
import tkinter
from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any, Literal

import customtkinter as ctk
from customtkinter.windows.widgets.appearance_mode import (
    AppearanceModeTracker,
)
from customtkinter.windows.widgets.core_widget_classes import CTkBaseClass

logger = logging.getLogger(__name__)

# DwmSetWindowAttribute: modo escuro da barra de título. 20 vale a partir do
# Windows 10 20H1; 19, nas versões anteriores.
_DWMWA_USE_IMMERSIVE_DARK_MODE = (20, 19)
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOZORDER = 0x0004
_SWP_NOACTIVATE = 0x0010
_SWP_FRAMECHANGED = 0x0020
_SWP_REPAINT_FRAME_ONLY = (
    _SWP_NOSIZE | _SWP_NOMOVE | _SWP_NOZORDER | _SWP_NOACTIVATE
    | _SWP_FRAMECHANGED
)
_RDW_INVALIDATE = 0x0001
_RDW_ALLCHILDREN = 0x0080

_installed = False


def install() -> None:
    """Instala os ajustes do bug C. Chame antes de criar a janela."""
    global _installed
    if _installed:
        return
    _installed = True

    def set_appearance_mode(self: CTkBaseClass, mode_string: str) -> None:
        # Igual ao original, sem o update_idletasks() de cada widget: a
        # janela se redesenha uma vez só, quando todos já trocaram de cor.
        super(CTkBaseClass, self)._set_appearance_mode(mode_string)
        self._draw()

    original_title_bar: Callable[[ctk.CTk, str], None] = (
        ctk.CTk._windows_set_titlebar_color
    )

    def set_title_bar_color(self: ctk.CTk, color_mode: str) -> None:
        if not self._window_exists:
            # A janela ainda não apareceu: o original não pisca.
            original_title_bar(self, color_mode)
        else:
            set_title_bar_theme(self, color_mode)

    CTkBaseClass._set_appearance_mode = set_appearance_mode
    ctk.CTk._windows_set_titlebar_color = set_title_bar_color


def _ctk_widgets(widget: tkinter.Misc) -> list[Any]:
    found = []
    pending: list[Any] = [widget]
    while pending:
        current = pending.pop()
        pending.extend(current.winfo_children())
        if isinstance(current, CTkBaseClass):
            found.append(current)
    return found


def _expected_background(widget: CTkBaseClass) -> str:
    color: str = widget._apply_appearance_mode(widget._bg_color)
    return color


def sync_backgrounds(widget: tkinter.Misc) -> None:
    """Acerta a cor do Frame do widget e dos filhos (bug A).

    Chame antes de mostrar de novo um widget escondido. Só muda o que
    está errado: sem troca de tema desde a última vez, quase não custa.
    """
    for current in _ctk_widgets(widget):
        color = _expected_background(current)
        if tkinter.Frame.cget(current, "bg") != color:
            tkinter.Frame.configure(current, bg=color)


def reveal(
    widget: Any, manager: Literal["grid", "pack", "place"], **options: Any
) -> None:
    """Mostra de novo um widget escondido, já na cor do tema atual (bug A).

    Não faz nada se ele já estiver à mostra.
    """
    if widget.winfo_manager():
        return
    sync_backgrounds(widget)
    getattr(widget, manager)(**options)


def stale_frame_backgrounds(widget: tkinter.Misc) -> tuple[int, int]:
    """(Frames na cor errada, widgets do CustomTkinter) no widget e filhos."""
    widgets = _ctk_widgets(widget)
    stale = sum(
        widget.winfo_rgb(_expected_background(current))
        != widget.winfo_rgb(tkinter.Frame.cget(current, "bg"))
        for current in widgets
    )
    return stale, len(widgets)


def repaint(widget: tkinter.Misc) -> None:
    """Pede ao Windows para repintar o widget e todos os filhos dele (bug A).

    Faz o que o hover fazia em cada linha no vídeo do bug: widgets que
    voltam à tela às vezes não se repintavam sozinhos.
    """
    if sys.platform.startswith("win"):
        ctypes.windll.user32.RedrawWindow(
            widget.winfo_id(), None, None, _RDW_INVALIDATE | _RDW_ALLCHILDREN
        )


def set_title_bar_theme(window: ctk.CTk, color_mode: str) -> None:
    """Barra de título clara ou escura (Windows), sem esconder a janela."""
    if not sys.platform.startswith("win"):
        return
    value = ctypes.c_int(1 if color_mode.lower() == "dark" else 0)
    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        for attribute in _DWMWA_USE_IMMERSIVE_DARK_MODE:
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            )
            if result == 0:
                break
        ctypes.windll.user32.SetWindowPos(
            hwnd, 0, 0, 0, 0, 0, _SWP_REPAINT_FRAME_ONLY
        )
    except (AttributeError, OSError):
        logger.warning(
            "Não deu para mudar a cor da barra de título.", exc_info=True
        )


def on_appearance_change(
    callback: Callable[[str], None],
) -> Callable[[], None]:
    """Chama `callback("Light" ou "Dark")` a cada troca de tema.

    Para widgets que não são do CustomTkinter (como o canvas da lista).
    Devolve a função que cancela o aviso.
    """
    AppearanceModeTracker.add(callback)

    def unsubscribe() -> None:
        AppearanceModeTracker.remove(callback)

    return unsubscribe


_WS_POPUP = 0x80000000
_WS_EX_LAYERED = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_NOACTIVATE = 0x08000000
_SW_SHOWNA = 8
_ULW_ALPHA = 2
_PW_RENDERFULLCONTENT = 2
_DWMWA_TRANSITIONS_FORCEDISABLED = 3


class _Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _Size(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class _Blend(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte),
        ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte),
        ("AlphaFormat", ctypes.c_ubyte),
    ]


@functools.cache
def _win32() -> SimpleNamespace:
    """user32, gdi32 e dwmapi com os tipos declarados.

    Instâncias próprias: os tipos declarados aqui não mudam as funções
    de ctypes.windll que o CustomTkinter usa.
    """
    user32 = ctypes.WinDLL("user32")
    gdi32 = ctypes.WinDLL("gdi32")
    dwmapi = ctypes.WinDLL("dwmapi")
    handle, uint = ctypes.c_void_p, ctypes.c_uint32
    signatures: list[tuple[Any, Any, list[Any]]] = [
        (user32.GetParent, handle, [handle]),
        (user32.GetDC, handle, [handle]),
        (user32.ReleaseDC, ctypes.c_int, [handle, handle]),
        (user32.PrintWindow, ctypes.c_int, [handle, handle, uint]),
        (user32.CreateWindowExW, handle, [
            uint, ctypes.c_wchar_p, ctypes.c_wchar_p, uint, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, handle, handle,
            handle, ctypes.c_void_p,
        ]),
        (user32.DestroyWindow, ctypes.c_int, [handle]),
        (user32.ShowWindow, ctypes.c_int, [handle, ctypes.c_int]),
        (user32.UpdateLayeredWindow, ctypes.c_int, [
            handle, handle, ctypes.POINTER(_Point), ctypes.POINTER(_Size),
            handle, ctypes.POINTER(_Point), uint, ctypes.POINTER(_Blend),
            uint,
        ]),
        (gdi32.CreateCompatibleDC, handle, [handle]),
        (gdi32.CreateCompatibleBitmap, handle, [
            handle, ctypes.c_int, ctypes.c_int,
        ]),
        (gdi32.SelectObject, handle, [handle, handle]),
        (gdi32.DeleteObject, ctypes.c_int, [handle]),
        (gdi32.DeleteDC, ctypes.c_int, [handle]),
        (dwmapi.DwmSetWindowAttribute, ctypes.c_long, [
            handle, uint, ctypes.c_void_p, uint,
        ]),
    ]
    for function, result, arguments in signatures:
        function.restype = result
        function.argtypes = arguments
    return SimpleNamespace(user32=user32, gdi32=gdi32, dwmapi=dwmapi)


class WindowCover:
    """Foto de uma janela numa camada por cima dela (só no Windows).

    Para transições: show() cobre a janela com uma foto do que ela mostra;
    a janela muda por baixo; set_opacity() deixa a foto esmaecer; hide()
    a tira. A camada não recebe o mouse nem o foco e fica sempre acima da
    janela (é "dona" dela no Windows).

    A foto vai direto para o Windows (UpdateLayeredWindow), que a mostra
    na hora. A primeira versão usava uma Toplevel do Tk com a foto num
    Label: da segunda troca em diante, a foto só aparecia ~100 ms depois
    do tema novo, quando o Tk repintava o Label, e a troca piscava.
    """

    def __init__(self, window: tkinter.Misc) -> None:
        self._window = window
        self._layer: int | None = None

    def show(self) -> bool:
        """Cobre a janela com uma foto dela. False se não der."""
        if not sys.platform.startswith("win"):
            return False
        width = self._window.winfo_width()
        height = self._window.winfo_height()
        if width <= 1 or height <= 1:
            return False
        try:
            return self._show(width, height)
        except OSError:
            logger.warning("Não deu para cobrir a janela.", exc_info=True)
            return False

    def set_opacity(self, opacity: float) -> None:
        """De 1 (só a foto) a 0 (só a janela)."""
        if self._layer is not None:
            blend = _Blend(0, 0, round(255 * opacity), 0)
            _win32().user32.UpdateLayeredWindow(
                self._layer, None, None, None, None, None, 0,
                ctypes.byref(blend), _ULW_ALPHA,
            )

    def hide(self) -> None:
        """Tira a foto. A camada continua lá, transparente e vazia."""
        if self._layer is not None:
            # Um bitmap de 1 px no lugar da foto libera a memória dela.
            with self._bitmap(1, 1) as bitmap_dc:
                self._update_layer(bitmap_dc, 1, 1, opacity=0.0)

    def destroy(self) -> None:
        if self._layer is not None:
            _win32().user32.DestroyWindow(self._layer)
            self._layer = None

    def _show(self, width: int, height: int) -> bool:
        if self._layer is None:
            self._layer = self._create_layer()
        source = self._window.winfo_id()
        with self._bitmap(width, height) as bitmap_dc:
            if not _win32().user32.PrintWindow(
                source, bitmap_dc, _PW_RENDERFULLCONTENT
            ):
                return False
            return self._update_layer(bitmap_dc, width, height, opacity=1.0)

    def _create_layer(self) -> int:
        api = _win32()
        owner = api.user32.GetParent(self._window.winfo_id())
        layer = api.user32.CreateWindowExW(
            _WS_EX_LAYERED | _WS_EX_TRANSPARENT | _WS_EX_TOOLWINDOW
            | _WS_EX_NOACTIVATE,
            "Static", None, _WS_POPUP, 0, 0, 1, 1, owner, None, None, None,
        )
        if not layer:
            raise ctypes.WinError()
        disabled = ctypes.c_int(1)
        api.dwmapi.DwmSetWindowAttribute(
            layer, _DWMWA_TRANSITIONS_FORCEDISABLED, ctypes.byref(disabled),
            ctypes.sizeof(disabled),
        )
        # Fica visível de vez: sem conteúdo, não aparece. Mostrar e
        # esconder a cada troca é o que atrasava a primeira versão.
        api.user32.ShowWindow(layer, _SW_SHOWNA)
        return int(layer)

    @contextlib.contextmanager
    def _bitmap(self, width: int, height: int) -> Iterator[int]:
        api = _win32()
        source = self._window.winfo_id()
        window_dc = api.user32.GetDC(source)
        bitmap_dc = api.gdi32.CreateCompatibleDC(window_dc)
        bitmap = api.gdi32.CreateCompatibleBitmap(window_dc, width, height)
        previous = api.gdi32.SelectObject(bitmap_dc, bitmap)
        try:
            yield bitmap_dc
        finally:
            api.gdi32.SelectObject(bitmap_dc, previous)
            api.gdi32.DeleteObject(bitmap)
            api.gdi32.DeleteDC(bitmap_dc)
            api.user32.ReleaseDC(source, window_dc)

    def _update_layer(
        self, bitmap_dc: int, width: int, height: int, opacity: float
    ) -> bool:
        position = _Point(
            self._window.winfo_rootx(), self._window.winfo_rooty()
        )
        blend = _Blend(0, 0, round(255 * opacity), 0)
        return bool(_win32().user32.UpdateLayeredWindow(
            self._layer, None, ctypes.byref(position),
            ctypes.byref(_Size(width, height)), bitmap_dc,
            ctypes.byref(_Point(0, 0)), 0, ctypes.byref(blend), _ULW_ALPHA,
        ))
