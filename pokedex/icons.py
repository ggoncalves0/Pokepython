"""Ícones desenhados com o Pillow.

Emojis aparecem errado (ou nem aparecem) no Tk do Windows, então os
ícones são desenhados aqui. A lupa e o "×" são feitos 4x maiores e
reduzidos pelo CTkImage, o que deixa as bordas suaves em qualquer escala
de tela. O ícone da janela, o sol e a lua são pixel art.
"""

import math

from PIL import Image, ImageColor, ImageDraw

SUPERSAMPLE = 4
STROKE = 0.12  # espessura do traço, em fração do tamanho do ícone

# Ícone da janela: um aparelho portátil com lente azul, luzes e uma tela
# verde com um rostinho. Cada caractere é um pixel; "." é transparente.
APP_ICON = [
    "................",
    "..KKKKKKKKKKKK..",
    ".KRRRRRRRRRRRRK.",
    ".KRRKKKRRRRRRRK.",
    ".KRKWbBKRYRGRRK.",
    ".KRKBBBKRRRRRRK.",
    ".KRRKKKRRRRRRRK.",
    ".KRRRRRRRRRRRRK.",
    ".KRKKKKKKKKKKRK.",
    ".KRKGGGGGGGGKRK.",
    ".KRKGGgGGgGGKRK.",
    ".KRKGGGGGGGGKRK.",
    ".KRKGgGGGGgGKRK.",
    ".KRKGGggggGGKRK.",
    ".KRKKKKKKKKKKRK.",
    "..KKKKKKKKKKKK..",
]
APP_ICON_PALETTE = {
    "K": "#1c1d26",  # contorno
    "R": "#d8433a",  # corpo
    "W": "#ffffff",  # brilho da lente
    "b": "#b9cdf8",  # lente, parte clara
    "B": "#6390f0",  # lente
    "Y": "#f7d02c",  # luz amarela
    "G": "#c3e6ae",  # tela
    "g": "#4e7a3a",  # rostinho na tela
}

# Botão de tema. Uma cor só ("X"), passada em sun_icon() e moon_icon().
SUN_ICON = [
    "................",
    ".......XX.......",
    ".......XX.......",
    "..XX........XX..",
    "..XX..XXXX..XX..",
    ".....XXXXXX.....",
    "....XXXXXXXX....",
    ".XX.XXXXXXXX.XX.",
    ".XX.XXXXXXXX.XX.",
    "....XXXXXXXX....",
    ".....XXXXXX.....",
    "..XX..XXXX..XX..",
    "..XX........XX..",
    ".......XX.......",
    ".......XX.......",
    "................",
]
MOON_ICON = [
    "................",
    "................",
    ".....XX.........",
    "....XX..........",
    "...XXX..........",
    "...XXX..........",
    "..XXXX..........",
    "..XXXXX.........",
    "..XXXXX.........",
    "..XXXXXXX....X..",
    "...XXXXXXXXXXX..",
    "...XXXXXXXXXX...",
    "....XXXXXXXX....",
    "......XXXX......",
    "................",
    "................",
]


def pixel_art(
    rows: list[str], palette: dict[str, str], scale: int = 1
) -> Image.Image:
    """Monta uma imagem a partir de um desenho em texto.

    Cada caractere é um pixel com a cor de `palette`; "." é transparente.
    A ampliação usa NEAREST, que mantém os pixels nítidos.
    """
    width, height = len(rows[0]), len(rows)
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            if char != ".":
                image.putpixel((x, y), ImageColor.getrgb(palette[char]))
    return image.resize((width * scale, height * scale), Image.NEAREST)


def sun_icon(color: str) -> Image.Image:
    return pixel_art(SUN_ICON, {"X": color})


def moon_icon(color: str) -> Image.Image:
    return pixel_art(MOON_ICON, {"X": color})


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
