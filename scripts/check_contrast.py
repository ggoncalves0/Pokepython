"""Confere o contraste (WCAG) das cores de cada tipo.

Uso: python scripts/check_contrast.py

Para cada tipo, mede cada elemento contra o fundo em que ele aparece:
- nome e número no hero, sobre o pastel: mínimo 4,5:1;
- texto do selo, sobre a cor do tipo: mínimo 4,5:1;
- barra de status, contra o trilho: mínimo 3:1.

Termina com erro se algum valor ficar abaixo do mínimo.
"""

import sys
from pathlib import Path

# Permite rodar o script direto, sem instalar o pacote.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pokedex.theme import (  # noqa: E402
    DARK_TEXT_COLOR,
    ELEVATED_COLOR,
    MIN_BAR_CONTRAST,
    MIN_TEXT_CONTRAST,
    TYPES,
    badge_text_color,
    bar_color,
    contrast_ratio,
    hero_number_color,
    pastel,
    readable_text_color,
)

COLUMNS = (
    ("Tipo", 10), ("Cor", 8), ("Pastel", 9), ("Nome", 7), ("Número", 8),
    ("Selo", 14), ("Barra", 18),
)


def ratio(value: float, minimum: float) -> str:
    """Formata "5,37" e marca com "!" o que fica abaixo do mínimo."""
    text = f"{value:.2f}".replace(".", ",")
    return text if value >= minimum else f"{text}!"


def row_for(label: str, color: str) -> tuple[list[str], bool]:
    background = pastel(color)
    badge_text = badge_text_color(color)
    bar = bar_color(color)
    checks = [
        (contrast_ratio(readable_text_color(background), background),
         MIN_TEXT_CONTRAST),
        (contrast_ratio(hero_number_color(background), background),
         MIN_TEXT_CONTRAST),
        (contrast_ratio(badge_text, color), MIN_TEXT_CONTRAST),
        (contrast_ratio(bar, ELEVATED_COLOR), MIN_BAR_CONTRAST),
    ]
    name, number, badge, bar_ratio = [ratio(*check) for check in checks]
    badge_label = "preto" if badge_text == DARK_TEXT_COLOR else "branco"
    bar_label = "cor do tipo" if bar == color else f"clareada {bar}"
    cells = [
        label, color, background, name, number,
        f"{badge} {badge_label}", f"{bar_ratio} {bar_label}",
    ]
    return cells, all(value >= minimum for value, minimum in checks)


def main() -> int:
    print("".join(title.ljust(width) for title, width in COLUMNS))
    failures = 0
    for style in TYPES.values():
        cells, passed = row_for(style.label, style.color)
        failures += not passed
        print("".join(
            cell.ljust(width) for cell, (_, width) in zip(cells, COLUMNS)
        ))
    print()
    print(
        "Mínimos: texto 4,5:1 (nome, número, selo); barra 3:1 contra o "
        f"trilho {ELEVATED_COLOR}. \"!\" marca o que ficou abaixo."
    )
    print("Tudo certo." if not failures else f"{failures} tipo(s) com falha.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
