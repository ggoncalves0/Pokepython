"""Confere o contraste (WCAG) das cores nos temas claro e escuro.

Uso: python scripts/check_contrast.py

Para cada tipo, mede cada elemento contra o fundo em que ele aparece:
- nome e número no hero, sobre o pastel: mínimo 4,5:1;
- texto do selo, sobre a cor do tipo: mínimo 4,5:1;
- barra de status, contra o trilho: mínimo 3:1;
- borda do hero contra o fundo da janela: mínimo 3:1 (no escuro, a borda
  tem a cor do pastel, então conta o próprio pastel).
Nome, número e selo não mudam com o tema; barra e borda mudam.

Depois confere as cores da interface (textos, barra de rolagem, ícones).
Termina com erro se algum valor ficar abaixo do mínimo.
"""

import sys
from pathlib import Path

# Permite rodar o script direto, sem instalar o pacote.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pokedex.theme import (  # noqa: E402
    APP_BACKGROUND,
    BLACK,
    CARD_COLOR,
    CONTRAST_STEP,
    DARK_TEXT_COLOR,
    ELEVATED_COLOR,
    ERROR_COLOR,
    MIN_BAR_CONTRAST,
    MIN_TEXT_CONTRAST,
    MUTED_COLOR,
    SCROLLBAR_COLOR,
    SCROLLBAR_HOVER_COLOR,
    SIDEBAR_COLOR,
    TEXT_COLOR,
    TYPES,
    WHITE,
    badge_text_color,
    bar_color,
    contrast_ratio,
    hero_border_color,
    hero_number_color,
    mix_colors,
    pastel,
    readable_text_color,
)

THEMES = (("claro", 0), ("escuro", 1))  # nome e posição no par de cores

TYPE_COLUMNS = (
    ("Tipo", 10), ("Cor", 8), ("Pastel", 9), ("Nome", 7), ("Número", 8),
    ("Selo", 14), ("Barra", 32), ("Borda do hero", 14),
)

# Cor, fundo, mínimo e onde aparece. Cada cor é o par (claro, escuro).
INTERFACE_CHECKS = (
    ("Texto", TEXT_COLOR, SIDEBAR_COLOR, MIN_TEXT_CONTRAST,
     "título e lista"),
    ("Texto", TEXT_COLOR, CARD_COLOR, MIN_TEXT_CONTRAST,
     "cards e busca"),
    ("Texto", TEXT_COLOR, ELEVATED_COLOR, MIN_TEXT_CONTRAST,
     "linha sob o mouse"),
    ("Secundário", MUTED_COLOR, SIDEBAR_COLOR, MIN_TEXT_CONTRAST,
     "contador e avisos"),
    ("Secundário", MUTED_COLOR, CARD_COLOR, MIN_TEXT_CONTRAST,
     "rótulos, placeholder, OCULTA"),
    ("Ícones", MUTED_COLOR, ELEVATED_COLOR, MIN_BAR_CONTRAST,
     "sol/lua e × sob o mouse"),
    ("Erro", ERROR_COLOR, SIDEBAR_COLOR, MIN_TEXT_CONTRAST,
     "sem conexão"),
    ("Rolagem", SCROLLBAR_COLOR, SIDEBAR_COLOR, MIN_BAR_CONTRAST,
     "barra de rolagem"),
    ("Rolagem", SCROLLBAR_HOVER_COLOR, SIDEBAR_COLOR, MIN_BAR_CONTRAST,
     "barra sob o mouse"),
)
INTERFACE_COLUMNS = (
    ("Elemento", 12), ("Cor", 9), ("Fundo", 9), ("Contraste", 11),
    ("Onde", 30),
)


def ratio(value: float, minimum: float) -> str:
    """Formata "5,37" e marca com "!" o que fica abaixo do mínimo."""
    text = f"{value:.2f}".replace(".", ",")
    return text if value >= minimum else f"{text}!"


def describe_bar(color: str, bar: str) -> str:
    """"cor do tipo", "escurecida 40% #947d1a" ou "clareada 25% #d1625e"."""
    if bar == color:
        return "cor do tipo"
    for step in range(1, round(1 / CONTRAST_STEP) + 1):
        for target, verb in ((BLACK, "escurecida"), (WHITE, "clareada")):
            if mix_colors(color, target, step * CONTRAST_STEP) == bar:
                return f"{verb} {round(step * CONTRAST_STEP * 100)}% {bar}"
    return bar


def type_row(label: str, color: str, theme: int) -> tuple[list[str], bool]:
    background = pastel(color)
    badge_text = badge_text_color(color)
    bar = bar_color(color)[theme]
    border = hero_border_color(color)[theme]
    checks = [
        (contrast_ratio(readable_text_color(background), background),
         MIN_TEXT_CONTRAST),
        (contrast_ratio(hero_number_color(background), background),
         MIN_TEXT_CONTRAST),
        (contrast_ratio(badge_text, color), MIN_TEXT_CONTRAST),
        (contrast_ratio(bar, ELEVATED_COLOR[theme]), MIN_BAR_CONTRAST),
        (contrast_ratio(border, APP_BACKGROUND[theme]), MIN_BAR_CONTRAST),
    ]
    name, number, badge, bar_ratio, border_ratio = [
        ratio(*check) for check in checks
    ]
    badge_label = "preto" if badge_text == DARK_TEXT_COLOR else "branco"
    border_label = "pastel" if border == background else "barra"
    cells = [
        label, color, background, name, number,
        f"{badge} {badge_label}",
        f"{bar_ratio} {describe_bar(color, bar)}",
        f"{border_ratio} {border_label}",
    ]
    return cells, all(value >= minimum for value, minimum in checks)


def print_row(cells: list[str], columns: tuple[tuple[str, int], ...]) -> None:
    print("".join(
        cell.ljust(width) for cell, (_, width) in zip(cells, columns)
    ).rstrip())


def check_theme(name: str, theme: int) -> int:
    """Imprime as duas tabelas de um tema e devolve quantas falhas houve."""
    print(f"=== Tema {name} ===")
    print()
    print_row([title for title, _ in TYPE_COLUMNS], TYPE_COLUMNS)
    failures = 0
    for style in TYPES.values():
        cells, passed = type_row(style.label, style.color, theme)
        failures += not passed
        print_row(cells, TYPE_COLUMNS)
    print()
    print(
        f"Trilho das barras {ELEVATED_COLOR[theme]}; "
        f"fundo da janela {APP_BACKGROUND[theme]}."
    )
    print()
    print_row([title for title, _ in INTERFACE_COLUMNS], INTERFACE_COLUMNS)
    for label, color, background, minimum, where in INTERFACE_CHECKS:
        value = contrast_ratio(color[theme], background[theme])
        failures += value < minimum
        print_row(
            [label, color[theme], background[theme], ratio(value, minimum),
             where],
            INTERFACE_COLUMNS,
        )
    print()
    return failures


def main() -> int:
    failures = sum(check_theme(name, theme) for name, theme in THEMES)
    print(
        "Mínimos: texto 4,5:1; barras, bordas e ícones 3:1. "
        "\"!\" marca o que ficou abaixo."
    )
    print("Tudo certo." if not failures else f"{failures} falha(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
