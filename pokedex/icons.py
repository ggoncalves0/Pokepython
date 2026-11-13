"""Ícones desenhados com o Pillow.

Emojis aparecem errado (ou nem aparecem) no Tk do Windows, então os
ícones são desenhados aqui. A lupa e o "×" são feitos 4x maiores e
reduzidos pelo CTkImage, o que deixa as bordas suaves em qualquer escala
de tela. O resto é pixel art: o ícone da janela, o sol e a lua, o cursor
da lista e os símbolos ♀ e ♂.
"""

import math

from PIL import Image, ImageColor, ImageDraw

SUPERSAMPLE = 4
STROKE_FRACTION = 0.12

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
    "K": "#1c1d26",
    "R": "#d8433a",
    "W": "#ffffff",
    "b": "#b9cdf8",
    "B": "#6390f0",
    "Y": "#f7d02c",
    "G": "#c3e6ae",
    "g": "#4e7a3a",
}

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

# ♀/♂ da lista ficam numa caixa com a altura de uma linha de texto e o
# desenho na altura das maiúsculas: com a mesma altura, o Tk alinha imagem
# e letras sozinho. Medidas da Jersey 10 em 24 px (nomes da lista), em
# pixels da grade: 19 de subida e 6 de descida; maiúsculas nas linhas 6 a
# 18, com traço de uns 2 px.
LIST_LINE = 25
LIST_CAP_TOP = 6

CURSOR = [
    "X...",
    "XX..",
    "XXX.",
    "XXXX",
    "XXX.",
    "XX..",
    "X...",
]

# ♀ e ♂ não existem nas duas fontes; estes desenhos ficam no lugar deles.
# Os do título acompanham a Press Start 2P (7 linhas, a altura das
# maiúsculas, com traço vertical de 2 px); os da lista, a Jersey 10.
TITLE_SYMBOLS = {
    "♀": [
        "..XXXX.",
        ".XX..XX",
        ".XX..XX",
        "..XXXX.",
        "...XX..",
        ".XXXXXX",
        "...XX..",
    ],
    "♂": [
        "...XXXX",
        ".....XX",
        ".XXXX.X",
        "XX..XX.",
        "XX..XX.",
        "XX..XX.",
        ".XXXX..",
    ],
}
LIST_SYMBOLS = {
    "♀": [
        "..XXXX..",
        ".XXXXXX.",
        "XXX..XXX",
        "XX....XX",
        "XX....XX",
        "XXX..XXX",
        ".XXXXXX.",
        "..XXXX..",
        "...XX...",
        ".XXXXXX.",
        ".XXXXXX.",
        "...XX...",
        "...XX...",
    ],
    "♂": [
        ".......XXXX",
        ".......XXXX",
        ".........XX",
        "........XXX",
        ".......XX..",
        "..XXXXXX...",
        ".XXXXXX....",
        "XXX..XXX...",
        "XX....XX...",
        "XX....XX...",
        "XXX..XXX...",
        ".XXXXXX....",
        "..XXXX.....",
    ],
}


def pixel_art(
    rows: list[str], palette: dict[str, str], scale: int = 1
) -> Image.Image:
    """Cada caractere de `rows` é um pixel na cor de `palette`; "." é
    transparente. A ampliação usa NEAREST, que mantém os pixels nítidos."""
    width, height = len(rows[0]), len(rows)
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, char in enumerate(row):
            if char != ".":
                image.putpixel((x, y), ImageColor.getrgb(palette[char]))
    return image.resize(
        (width * scale, height * scale), Image.Resampling.NEAREST
    )


def sun_icon(color: str) -> Image.Image:
    return pixel_art(SUN_ICON, {"X": color})


def moon_icon(color: str) -> Image.Image:
    return pixel_art(MOON_ICON, {"X": color})


def pad_to_line_box(
    rows: list[str], height: int, top: int = 0, left: int = 0,
    right: int = 0,
) -> list[str]:
    width = left + len(rows[0]) + right
    blank = "." * width
    body = ["." * left + row + "." * right for row in rows]
    return [blank] * top + body + [blank] * (height - top - len(rows))


def cursor_icon(color: str) -> Image.Image:
    return pixel_art(CURSOR, {"X": color})


def list_symbol(symbol: str, color: str) -> Image.Image:
    rows = pad_to_line_box(
        LIST_SYMBOLS[symbol], LIST_LINE, top=LIST_CAP_TOP, left=1, right=1
    )
    return pixel_art(rows, {"X": color})


def _canvas(size: int) -> tuple[Image.Image, ImageDraw.ImageDraw, int, int]:
    side = size * SUPERSAMPLE
    image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image), side, round(side * STROKE_FRACTION)


def _rounded_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    color: str,
    width: int,
) -> None:
    draw.line((start, end), fill=color, width=width)
    radius = width / 2
    for x, y in (start, end):
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius), fill=color
        )


def search_icon(color: str, size: int) -> Image.Image:
    image, draw, side, width = _canvas(size)
    center = side * 0.42
    radius = side * 0.30
    draw.ellipse(
        (center - radius, center - radius, center + radius, center + radius),
        outline=color,
        width=width,
    )
    handle_start = center + radius * math.cos(math.pi / 4)
    handle_end = side * 0.86
    _rounded_line(
        draw, (handle_start, handle_start), (handle_end, handle_end), color,
        width,
    )
    return image


def close_icon(color: str, size: int) -> Image.Image:
    image, draw, side, width = _canvas(size)
    low, high = side * 0.22, side * 0.78
    _rounded_line(draw, (low, low), (high, high), color, width)
    _rounded_line(draw, (low, high), (high, low), color, width)
    return image
