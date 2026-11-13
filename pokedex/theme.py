"""Tokens de design da Pokédex: cores, espaçamentos, tamanhos e fontes.

Também ficam aqui as regras de cor por tipo. Assim, para mudar o visual
não é preciso caçar números espalhados pelo código.

Os valores em px são lógicos: o CustomTkinter ajusta tamanhos, fontes e
espaçamentos à escala da tela (125%, 150%...).
"""

from typing import NamedTuple

# Par (tema claro, tema escuro). O CustomTkinter aceita o par em qualquer
# cor e troca sozinho quando o tema muda.
type ThemeColor = tuple[str, str]
type Color = str | ThemeColor

APP_BACKGROUND: ThemeColor = ("#eef0f5", "#16171d")
SIDEBAR_COLOR: ThemeColor = ("#f8f9fb", "#1f2029")
CARD_COLOR: ThemeColor = ("#ffffff", "#262834")
ELEVATED_COLOR: ThemeColor = ("#e4e7ef", "#323545")
BORDER_COLOR: ThemeColor = ("#cdd1de", "#44475a")
# A busca com foco usa uma cor neutra: a do tipo (vermelho no Lutador)
# parecia erro, ainda mais junto de "Nenhum Pokémon encontrado".
FOCUS_COLOR: ThemeColor = ("#5b5f75", "#9a9cb0")
TEXT_COLOR: ThemeColor = ("#1c1d26", "#f1f1f4")
MUTED_COLOR: ThemeColor = ("#5b5f75", "#9a9cb0")
ERROR_COLOR: ThemeColor = ("#c62828", "#ff6b6b")
SCROLLBAR_COLOR: ThemeColor = ("#868a9f", "#6b6e85")
SCROLLBAR_HOVER_COLOR: ThemeColor = ("#5b5f75", "#9a9cb0")
# No claro, o branco dos cards quase some no fundo, e a borda os separa.
# No escuro, ela tem a cor do card: não aparece.
CARD_BORDER_COLOR: ThemeColor = ("#dfe2ea", CARD_COLOR[1])

# Iguais nos dois temas: ficam sobre o pastel ou sobre a cor do tipo, que
# não mudam com o tema.
DARK_TEXT_COLOR = "#1c1c1c"
LIGHT_TEXT_COLOR = "#f1f1f4"
WHITE = "#ffffff"
BLACK = "#000000"

WINDOW_MARGIN = 24
CARD_GAP = 16
CARD_PADDING = 20
TITLE_GAP = 8
ITEM_GAP = 8
WIDE_GAP = 12
# Nas linhas da lista, o cursor ▶ fica dentro deste recuo, à esquerda do
# ícone.
CONTROL_PADDING = 16
CURSOR_X = 4  # o anel de foco ocupa os 2 px da borda da linha
BADGE_PADDING = 10

# Cantos quase retos, no estilo 8-bit.
CARD_RADIUS = 4
SEARCH_RADIUS = 4
ROW_RADIUS = 4
BADGE_RADIUS = 2
# Botões só com ícone ("×" e tema): o CTkButton reserva o raio dos dois
# lados do ícone, e com um raio maior o botão fica mais largo que o pedido.
ICON_BUTTON_RADIUS = 4

# A linha de baixo tem altura fixa (pior caso: 3 habilidades); com 720 px
# de altura, o hero mantém a arte no tamanho de antes.
INITIAL_WINDOW_SIZE = (920, 720)
MIN_WINDOW_SIZE = (920, 680)
LIST_WIDTH = 200
SCROLLBAR_WIDTH = 16
SCROLLBAR_RIGHT_GAP = 1
# Largura fixa: se dependesse do conteúdo, a lateral encolheria ao esconder
# a barra de rolagem, e a tela toda se deslocaria.
SIDEBAR_WIDTH = (
    2 * WINDOW_MARGIN + LIST_WIDTH + SCROLLBAR_WIDTH + SCROLLBAR_RIGHT_GAP
)
SEARCH_HEIGHT = 38
ROW_HEIGHT = 34
ROW_GAP = 2
BADGE_HEIGHT = 26
BAR_HEIGHT = 8
SEARCH_ICON_SIZE = 16
CLEAR_ICON_SIZE = 12
CLEAR_BUTTON_SIZE = 24
THEME_BUTTON_SIZE = 32
NUMBER_WIDTH = 36  # cabe "#000" em 18 px
# O miolo do ícone de 40 x 30 px, onde fica o Pokémon.
LIST_ICON_SIZE = (28, 24)
CURSOR_SCALE = 2  # 8 x 14 px: a altura das maiúsculas do nome
STAT_VALUE_WIDTH = 28  # cabe "100" em 18 px
BORDER_WIDTH = 1
FOCUS_BORDER_WIDTH = 2
CARD_BORDER_WIDTH = 2
ARTWORK_MIN_SIZE = 230  # a arte com a janela no tamanho mínimo
ARTWORK_MAX_SIZE = 475  # a resolução da arte oficial; maior que isso borra

# Press Start 2P: só múltiplos de 8 px, a grade dela (veja
# pixel.pixel_font_size para outras escalas de tela).
FONT_HERO = 24
# Desenhada como imagem (pixel.render_title), sem as franjas do ClearType.
FONT_TITLE = 16
# Jersey 10, proporcional ("0,7 m" sem buracos). Em 18 px, cada pixel do
# desenho vale 1 px na tela.
FONT_BODY = 18
FONT_LIST_NAME = 24
FONT_LIST_NUMBER = 18
FONT_BADGE = 18
FONT_HIDDEN_TAG = 16

PASTEL_AMOUNT = 0.55
HERO_NUMBER_AMOUNT = 0.20
CONTRAST_STEP = 0.05
MIN_TEXT_CONTRAST = 4.5  # WCAG AA, texto
MIN_BAR_CONTRAST = 3.0  # WCAG AA, elementos gráficos


class TypeStyle(NamedTuple):
    label: str
    color: str


TYPES = {
    "normal": TypeStyle("Normal", "#A8A77A"),
    "fire": TypeStyle("Fogo", "#EE8130"),
    "water": TypeStyle("Água", "#6390F0"),
    "electric": TypeStyle("Elétrico", "#F7D02C"),
    "grass": TypeStyle("Planta", "#7AC74C"),
    "ice": TypeStyle("Gelo", "#96D9D6"),
    "fighting": TypeStyle("Lutador", "#C22E28"),
    "poison": TypeStyle("Venenoso", "#A33EA1"),
    "ground": TypeStyle("Terrestre", "#E2BF65"),
    "flying": TypeStyle("Voador", "#A98FF3"),
    "psychic": TypeStyle("Psíquico", "#F95587"),
    "bug": TypeStyle("Inseto", "#A6B91A"),
    "rock": TypeStyle("Pedra", "#B6A136"),
    "ghost": TypeStyle("Fantasma", "#735797"),
    "dragon": TypeStyle("Dragão", "#6F35FC"),
    "dark": TypeStyle("Sombrio", "#705746"),
    "steel": TypeStyle("Aço", "#B7B7CE"),
    "fairy": TypeStyle("Fada", "#D685AD"),
}


def theme_pair(color: Color) -> ThemeColor:
    return (color, color) if isinstance(color, str) else color


def mix_colors(color: str, other: str, amount: float) -> str:
    """`amount` é quanto entra de `other`, de 0 a 1."""
    channels = [
        round(int(color[i:i + 2], 16) * (1 - amount)
              + int(other[i:i + 2], 16) * amount)
        for i in (1, 3, 5)
    ]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def relative_luminance(color: str) -> float:
    """Luminância relativa da WCAG: 0 é preto e 1 é branco."""
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    red, green, blue = [
        c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        for c in channels
    ]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(color: str, other: str) -> float:
    """Contraste da WCAG, de 1 (nenhum) a 21."""
    lighter, darker = sorted(
        (relative_luminance(color), relative_luminance(other)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def readable_text_color(background: str) -> str:
    return max(
        (DARK_TEXT_COLOR, LIGHT_TEXT_COLOR),
        key=lambda text: contrast_ratio(text, background),
    )


def adjust_contrast(
    color: str, background: str, minimum: float = MIN_BAR_CONTRAST
) -> str:
    """A cor mais próxima de `color` com pelo menos `minimum` de contraste.

    Se faltar contraste, mistura branco (fundo escuro) ou preto (fundo
    claro) em passos de 5% até chegar ao mínimo.
    """
    if contrast_ratio(color, background) >= minimum:
        return color
    target = max((WHITE, BLACK), key=lambda c: contrast_ratio(c, background))
    steps = round(1 / CONTRAST_STEP)
    for step in range(1, steps + 1):
        adjusted = mix_colors(color, target, step * CONTRAST_STEP)
        if contrast_ratio(adjusted, background) >= minimum:
            return adjusted
    return target  # só se o mínimo for maior que o possível


def pastel(type_color: str) -> str:
    return mix_colors(type_color, WHITE, PASTEL_AMOUNT)


def hero_number_color(pastel_color: str) -> str:
    """Mais suave que o nome, mas ainda acima de 4,5:1."""
    return mix_colors(
        readable_text_color(pastel_color), pastel_color, HERO_NUMBER_AMOUNT
    )


def badge_text_color(type_color: str) -> str:
    return readable_text_color(type_color)


def bar_color(type_color: str) -> ThemeColor:
    """A cor do tipo, ajustada contra o trilho de cada tema.

    No escuro, os tipos escuros clareiam; no claro, os tipos claros
    escurecem.
    """
    light_track, dark_track = ELEVATED_COLOR
    return (
        adjust_contrast(type_color, light_track),
        adjust_contrast(type_color, dark_track),
    )


def hero_border_color(type_color: str) -> ThemeColor:
    """Uma linha mais escura que o pastel, nos dois temas.

    Usa a cor das barras do tema claro. No claro, é o contorno que separa
    o card do fundo, onde alguns pastéis quase somem (Elétrico fica em
    1,06:1). No escuro, o próprio pastel já se destaca, e a linha é
    acabamento.
    """
    border = bar_color(type_color)[0]
    return (border, border)
