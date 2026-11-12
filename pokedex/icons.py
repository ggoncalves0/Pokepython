"""Ícones desenhados com o Pillow.

Emojis aparecem errado (ou nem aparecem) no Tk do Windows, então os
ícones são desenhados aqui. Cada um é feito 4x maior e reduzido pelo
CTkImage, o que deixa as bordas suaves em qualquer escala de tela.
"""

import math

from PIL import Image, ImageDraw

SUPERSAMPLE = 4
STROKE = 0.12  # espessura do traço, em fração do tamanho do ícone


def _canvas(size: int) -> tuple[Image.Image, ImageDraw.ImageDraw, int, int]:
    side = size * SUPERSAMPLE
    image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image), side, round(side * STROKE)


def _line(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    color: str,
    width: int,
) -> None:
    """Linha com pontas arredondadas."""
    draw.line((start, end), fill=color, width=width)
    radius = width / 2
    for x, y in (start, end):
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius), fill=color
        )


def search_icon(color: str, size: int) -> Image.Image:
    """Lupa: um círculo com o cabo descendo para a direita."""
    image, draw, side, width = _canvas(size)
    center = side * 0.42
    radius = side * 0.30
    draw.ellipse(
        (center - radius, center - radius, center + radius, center + radius),
        outline=color,
        width=width,
    )
    edge = center + radius * math.cos(math.pi / 4)
    _line(draw, (edge, edge), (side * 0.86, side * 0.86), color, width)
    return image


def close_icon(color: str, size: int) -> Image.Image:
    """"×" para limpar um campo."""
    image, draw, side, width = _canvas(size)
    low, high = side * 0.22, side * 0.78
    _line(draw, (low, low), (high, high), color, width)
    _line(draw, (low, high), (high, low), color, width)
    return image
