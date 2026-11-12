"""Tokens de design da Pokédex: cores, espaçamentos, tamanhos e fontes.

Também ficam aqui as regras de cor por tipo. Assim, para mudar o visual
não é preciso caçar números espalhados pelo ui.py.

Os valores em px são lógicos: o CustomTkinter ajusta tamanhos, fontes e
espaçamentos à escala da tela (125%, 150%...).
"""

from typing import NamedTuple

# --- Cores base (tema escuro) ---------------------------------------------

APP_BACKGROUND = "#16171d"  # fundo da janela
SIDEBAR_COLOR = "#1f2029"  # lateral com a lista
CARD_COLOR = "#262834"  # cards e campo de busca
ELEVATED_COLOR = "#323545"  # hover da lista, trilho das barras, divisórias
BORDER_COLOR = "#44475a"  # borda do campo de busca em repouso
TEXT_COLOR = "#f1f1f4"
MUTED_COLOR = "#9a9cb0"  # textos secundários
DARK_TEXT_COLOR = "#1c1c1c"  # texto sobre fundos claros (pastel)
WHITE = "#ffffff"
ERROR_COLOR = "#ff6b6b"

# --- Espaçamentos ---------------------------------------------------------

WINDOW_MARGIN = 24  # entre o conteúdo e as bordas da janela
CARD_GAP = 16  # entre um card e outro
CARD_PADDING = 20  # dentro de todos os cards
TITLE_GAP = 8  # entre o título de um card e o conteúdo
ITEM_GAP = 8  # entre itens lado a lado: selos, colunas, rótulos
WIDE_GAP = 12  # entre itens que precisam respirar: nome e número
CONTROL_PADDING = 12  # recuo do conteúdo na busca e nas linhas da lista
PILL_PADDING = 10  # recuo do texto dentro dos selos de tipo
HERO_NUMBER_NUDGE = 6  # desce o número até a linha de base do nome

# --- Cantos arredondados --------------------------------------------------

HERO_RADIUS = 24
CARD_RADIUS = 18
CONTROL_RADIUS = 10  # campo de busca
ROW_RADIUS = 8  # linhas da lista
PILL_RADIUS = 12  # selos de tipo

# --- Tamanhos -------------------------------------------------------------

WINDOW_SIZE = (920, 680)  # tamanho inicial e também o mínimo
LIST_WIDTH = 200  # área das linhas da lista, sem a barra de rolagem
SEARCH_HEIGHT = 38
ROW_HEIGHT = 34  # linhas da lista
ROW_GAP = 2  # entre as linhas da lista
PILL_HEIGHT = 26
BAR_HEIGHT = 8
ICON_SIZE = 16  # lupa da busca
CLEAR_ICON_SIZE = 12  # "×" da busca
CLEAR_BUTTON_SIZE = 24  # área clicável do "×"
NUMBER_WIDTH = 44  # coluna do número na lista
STAT_VALUE_WIDTH = 36  # coluna do valor nos status
BORDER_WIDTH = 1
FOCUS_BORDER_WIDTH = 2
ROW_INSET = FOCUS_BORDER_WIDTH + 1  # textos da lista longe do anel de foco
ARTWORK_MIN_SIZE = 230  # arte no tamanho mínimo da janela
ARTWORK_MAX_SIZE = 475  # resolução da arte oficial; maior que isso borra

# --- Fontes (tamanho em px) -----------------------------------------------

FONT_HERO = 30  # nome do Pokémon
FONT_SIDEBAR_TITLE = 20  # "Pokédex"
FONT_HEADING = 17  # títulos dos cards
FONT_BODY = 14
FONT_BADGE = 12  # selos de tipo
FONT_TAG = 11  # "OCULTA"

# --- Regras de cor por tipo -----------------------------------------------

PASTEL_AMOUNT = 0.55  # quanto de branco entra na cor do tipo no hero
HERO_NUMBER_AMOUNT = 0.20  # quanto do pastel entra no texto do número
BAR_LIGHTEN_AMOUNT = 0.25  # branco somado às barras com pouco contraste
MIN_TEXT_CONTRAST = 4.5  # WCAG AA para texto
MIN_BAR_CONTRAST = 3.0  # WCAG AA para elementos gráficos


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


def mix_colors(color: str, other: str, amount: float) -> str:
    """Mistura duas cores "#rrggbb"; `amount` é quanto entra de `other`."""
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
    """Contraste da WCAG entre duas cores, de 1 (nenhum) a 21."""
    lighter, darker = sorted(
        (relative_luminance(color), relative_luminance(other)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def readable_text_color(background: str) -> str:
    """Texto escuro ou claro: o que tiver mais contraste com o fundo."""
    return max(
        (DARK_TEXT_COLOR, TEXT_COLOR),
        key=lambda text: contrast_ratio(text, background),
    )


def pastel(type_color: str) -> str:
    """Fundo do hero: a cor do tipo clareada com branco."""
    return mix_colors(type_color, WHITE, PASTEL_AMOUNT)


def hero_number_color(pastel_color: str) -> str:
    """Número do hero: o texto do nome com um pouco do fundo.

    Fica mais suave que o nome, mas ainda acima de 4,5:1.
    """
    return mix_colors(
        readable_text_color(pastel_color), pastel_color, HERO_NUMBER_AMOUNT
    )


def badge_text_color(type_color: str) -> str:
    """Texto do selo de tipo: preto ou branco, o que contrastar mais."""
    return readable_text_color(type_color)


def bar_color(type_color: str) -> str:
    """Cor das barras: a do tipo, clareada se sumir contra o trilho."""
    if contrast_ratio(type_color, ELEVATED_COLOR) >= MIN_BAR_CONTRAST:
        return type_color
    return mix_colors(type_color, WHITE, BAR_LIGHTEN_AMOUNT)
