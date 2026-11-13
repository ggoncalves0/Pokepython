"""Testes do adaptador do CustomTkinter (pokedex/ctk_adapter.py).

Abrem uma janela de verdade, fora da área visível da tela. Se não houver
Tk disponível (sem tela), são pulados.
"""

import ctypes
import sys
import tkinter
import unittest
from typing import Any

import customtkinter as ctk

from pokedex import ctk_adapter
from tests.test_pokemon_list import cancel_pending_jobs

LIGHT_DARK = ("#f8f9fb", "#1f2029")
GWL_EXSTYLE = -20
GW_OWNER = 4
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000


class CtkAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        ctk_adapter.install()
        self.previous_mode = ctk.get_appearance_mode()
        ctk.set_appearance_mode("light")
        try:
            self.root = ctk.CTk(fg_color=LIGHT_DARK)
        except tkinter.TclError as error:
            self.skipTest(f"sem Tk: {error}")
        self.root.geometry("200x120+-3000+-3000")  # fora da tela
        self.root.update()  # a janela passa a existir para o CustomTkinter

    def tearDown(self) -> None:
        cancel_pending_jobs(self.root)
        self.root.destroy()
        ctk.set_appearance_mode(self.previous_mode)

    def build(self) -> ctk.CTkFrame:
        """Uma linha como as da lista: um frame com um rótulo dentro."""
        row = ctk.CTkFrame(self.root, fg_color="transparent")
        row.pack()
        ctk.CTkLabel(row, text="Bulbasaur").pack()
        self.root.update()
        return row

    def test_hidden_widget_keeps_old_background_until_synced(self) -> None:
        # O bug A: um widget escondido não acompanha o tema.
        row = self.build()
        row.pack_forget()
        ctk.set_appearance_mode("dark")
        self.root.update()
        self.assertGreater(ctk_adapter.stale_frame_backgrounds(row)[0], 0)

        ctk_adapter.sync_backgrounds(row)  # antes de mostrar de novo
        row.pack()
        self.root.update()
        stale, total = ctk_adapter.stale_frame_backgrounds(row)
        self.assertEqual((stale, total), (0, 2))

    def test_sync_backgrounds_follows_color_change(self) -> None:
        # Como no hover: a cor do widget muda depois de ele ser criado.
        row = self.build()
        row.configure(fg_color="#e4a19e")
        ctk_adapter.sync_backgrounds(row)
        self.assertEqual(ctk_adapter.stale_frame_backgrounds(row)[0], 0)

    def test_theme_change_does_not_hide_window(self) -> None:
        self.build()
        hidden: list[Any] = []
        original = tkinter.Wm.withdraw

        def count(window: tkinter.Wm) -> None:
            hidden.append(window)
            original(window)

        tkinter.Wm.withdraw = count  # type: ignore[method-assign]
        try:
            ctk.set_appearance_mode("dark")
            self.root.update()
        finally:
            tkinter.Wm.withdraw = original  # type: ignore[method-assign]
        self.assertEqual(hidden, [])
        self.assertEqual(self.root.state(), "normal")

    def test_theme_change_redraws_once(self) -> None:
        # Sem um update_idletasks() por widget durante a troca de tema.
        self.build()
        calls: list[Any] = []
        original = tkinter.Misc.update_idletasks

        def count(widget: tkinter.Misc) -> None:
            calls.append(widget)
            original(widget)

        misc: Any = tkinter.Misc
        misc.update_idletasks = count
        try:
            ctk.set_appearance_mode("dark")
        finally:
            misc.update_idletasks = original
        self.assertEqual(calls, [])


@unittest.skipUnless(sys.platform.startswith("win"), "só no Windows")
class WindowCoverTest(unittest.TestCase):
    """A capa da troca de tema: uma camada do Windows por cima da janela."""

    def setUp(self) -> None:
        try:
            self.root = ctk.CTk()
        except tkinter.TclError as error:
            self.skipTest(f"sem Tk: {error}")
        self.root.geometry("200x120+-3000+-3000")  # fora da tela
        self.root.update()
        self.cover = ctk_adapter.WindowCover(self.root)

    def tearDown(self) -> None:
        self.cover.destroy()
        cancel_pending_jobs(self.root)
        self.root.destroy()

    def test_sits_above_window_without_taking_mouse_or_focus(self) -> None:
        self.assertTrue(self.cover.show())
        user32 = ctypes.windll.user32
        layer = self.cover._layer
        ex_style = user32.GetWindowLongW(layer, GWL_EXSTYLE)
        self.assertTrue(user32.IsWindowVisible(layer))
        self.assertTrue(ex_style & WS_EX_TRANSPARENT, "o mouse passa direto")
        self.assertTrue(ex_style & WS_EX_NOACTIVATE, "não recebe o foco")
        # Dona = a janela: a camada fica sempre logo acima dela.
        owner = user32.GetWindow(layer, GW_OWNER)
        self.assertEqual(owner, user32.GetParent(self.root.winfo_id()))

    def test_serves_many_changes_and_is_destroyed(self) -> None:
        self.assertTrue(self.cover.show())
        first_layer = self.cover._layer
        self.cover.set_opacity(0.5)
        self.cover.hide()
        self.assertTrue(self.cover.show())
        self.assertEqual(self.cover._layer, first_layer)
        self.cover.destroy()
        self.assertFalse(ctypes.windll.user32.IsWindow(first_layer))


if __name__ == "__main__":
    unittest.main()
