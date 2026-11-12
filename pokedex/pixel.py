"""Fontes pixeladas e pixel art nítidos em qualquer escala de tela.

A Press Start 2P é desenhada numa grade de 8 px e só fica nítida em
múltiplos de 8 px. Com a escala do Windows em 125%, 16 px virariam 20 px
e borrariam; por isso o tamanho dela é ajustado ao múltiplo de 8 mais
próximo. As imagens em pixel art seguem a mesma regra.
"""

import tkinter
import tkinter.font
from functools import cache
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageTk

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONT_FILES = (
    "PressStart2P-Regular.ttf",
    "Jersey10-Regular.ttf",
)
TITLE_FAMILY = "Press Start 2P"  # títulos e números
TEXT_FAMILY = "Jersey 10"  # o resto; só tem um peso, que já parece negrito
PIXEL_GRID = 8  # grade da Press Start 2P, em px


def load_pixel_fonts() -> bool:
    """Registra as fontes de assets/fonts só para este programa.

    Precisa vir antes de criar os widgets. Devolve False se alguma falhar.
    """
    return all(
        ctk.FontManager.load_font(str(FONTS_DIR / name))
        for name in FONT_FILES
    )


def fonts_available(root: tkinter.Misc) -> bool:
    """Confere se o Tk achou as fontes (se não acha, ele usa outra)."""
    return all(
        tkinter.font.Font(root, family=family).actual("family") == family
        for family in (TITLE_FAMILY, TEXT_FAMILY)
    )


def pixel_font_size(size: int, scaling: float) -> int:
    """Tamanho a pedir ao CTkFont para cair num múltiplo de 8 px na tela.

    O CTkFont só aceita inteiros e arredonda tamanho × escala. Entre os
    inteiros que dão um múltiplo de 8, escolhe o mais próximo de `size` ×
    escala; no empate, o menor, para títulos e números não estourarem as
    colunas (em 125%, 16 px ficam em 16, e não em 24). Em 100%, devolve o
    próprio `size`.
    """
    desired = size * scaling

    def on_screen(candidate: int) -> int:
        return round(candidate * scaling)  # a mesma conta do CTkFont

    candidates = [
        c for c in range(1, 2 * size + 1)
        if on_screen(c) > 0 and on_screen(c) % PIXEL_GRID == 0
    ]
    if not candidates:
        return size
    return min(
        candidates, key=lambda c: (abs(on_screen(c) - desired), on_screen(c))
    )


def pixel_scale(scale: int, scaling: float) -> int:
    """Fator inteiro de ampliação que acompanha a Press Start 2P.

    Um desenho feito para a fonte de `scale` × 8 px é ampliado tanto quanto
    a fonte na tela: em 125%, a de 16 px fica em 16 (2x) e a de 24 px, em
    32 (4x).
    """
    size = pixel_font_size(scale * PIXEL_GRID, scaling)
    return round(size * scaling) // PIXEL_GRID


@cache
def _title_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS_DIR / FONT_FILES[0]), size)


def render_title(text: str, size: int, color: str) -> Image.Image:
    """Texto na Press Start 2P desenhado pelo Pillow, sem suavização.

    O Tk desenha com ClearType, que deixa franjas coloridas nas bordas das
    letras. Com fontmode "1", cada pixel é tinta ou fundo. A imagem tem
    `size` px de altura (a fonte não desce abaixo da linha) e a largura do
    texto; use `size` já em pixels da tela (veja pixel_font_size).
    """
    font = _title_font(size)
    image = Image.new(
        "RGBA", (max(1, round(font.getlength(text))), size), (0, 0, 0, 0)
    )
    draw = ImageDraw.Draw(image)
    draw.fontmode = "1"
    draw.text((0, 0), text, font=font, fill=color)
    return image


class PixelImage(ctk.CTkImage):
    """CTkImage para pixel art: amplia sem borrar.

    O CTkImage comum amplia com suavização, o que borra os pixels quando a
    escala do Windows não é 100%. Este amplia com NEAREST. Com snap=True,
    amplia sempre por um fator inteiro (2x, 3x...), acompanhando a Press
    Start 2P; sem ele, segue a escala exata, como a Jersey 10.
    """

    def __init__(
        self,
        light_image: Image.Image,
        dark_image: Image.Image,
        scale: int = 1,
        snap: bool = False,
    ) -> None:
        width, height = light_image.size
        super().__init__(
            light_image, dark_image, size=(width * scale, height * scale)
        )
        self._scale = scale
        self._snap = snap

    def create_scaled_photo_image(
        self, widget_scaling: float, appearance_mode: str
    ) -> ImageTk.PhotoImage:
        if self._snap:
            factor = pixel_scale(self._scale, widget_scaling)
            width, height = self._light_image.size
            size = (width * factor, height * factor)
        else:
            size = self._get_scaled_size(widget_scaling)
        dark = appearance_mode == "dark"
        cache = (
            self._scaled_dark_photo_images if dark
            else self._scaled_light_photo_images
        )
        if size not in cache:
            image = self._dark_image if dark else self._light_image
            cache[size] = ImageTk.PhotoImage(image.resize(size, Image.NEAREST))
        return cache[size]
