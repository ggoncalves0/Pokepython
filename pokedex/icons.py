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

# Desenhos que ficam ao lado de letras: cada um vai numa caixa com a
# altura de uma linha de texto e o desenho na altura das maiúsculas. Com a
# mesma altura, o Tk alinha imagem e letras sozinho. Medidas da fonte no
# Tk, em pixels da grade:
# - Press Start 2P: 8 de subida e 3 de descida; maiúsculas nas 7 primeiras
#   linhas, traço vertical de 2 px.
TITLE_LINE = 11
# - Jersey 10 em 24 px (nomes da lista): 19 de subida e 6 de descida;
#   maiúsculas nas linhas 6 a 18, traço de uns 2 px.
LIST_LINE = 25
LIST_CAP_TOP = 6

# Cursor da linha selecionada na lista, no estilo da Press Start 2P.
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
# Uma versão para o nome no card principal (Press Start 2P) e outra para a
# lista (Jersey 10).
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


def in_line(
    rows: list[str], height: int, top: int = 0, left: int = 0,
    right: int = 0,
) -> list[str]:
    """Põe o desenho na caixa de uma linha de texto, completando com "."."""
    width = left + len(rows[0]) + right
    blank = "." * width
    body = ["." * left + row + "." * right for row in rows]
    return [blank] * top + body + [blank] * (height - top - len(rows))


def cursor_icon(color: str) -> Image.Image:
    """▶ da linha selecionada."""
    return pixel_art(CURSOR, {"X": color})


def title_symbol(symbol: str, color: str) -> Image.Image:
    """♀ ou ♂ na linha da Press Start 2P (cada caractere tem 8 colunas)."""
    return pixel_art(
        in_line(TITLE_SYMBOLS[symbol], TITLE_LINE, right=1), {"X": color}
    )


def list_symbol(symbol: str, color: str) -> Image.Image:
    """♀ ou ♂ na linha dos nomes da lista (Jersey 10 em 24 px)."""
    rows = in_line(
        LIST_SYMBOLS[symbol], LIST_LINE, top=LIST_CAP_TOP, left=1, right=1
    )
    return pixel_art(rows, {"X": color})


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
