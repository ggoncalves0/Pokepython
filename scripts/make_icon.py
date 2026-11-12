"""Gera o ícone da janela (assets/icon.ico) a partir do desenho em pixel art.

Uso: python scripts/make_icon.py

O desenho fica em pokedex/icons.py (APP_ICON). Rode este script de novo
sempre que mudar o desenho.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Permite rodar o script direto, sem instalar o pacote.
sys.path.insert(0, str(ROOT))

from pokedex.icons import APP_ICON, APP_ICON_PALETTE, pixel_art  # noqa: E402

# Só múltiplos de 16: cada pixel do desenho vira um bloco inteiro, sem
# borrar. O Windows escolhe o tamanho conforme o lugar (barra de título,
# barra de tarefas, Alt+Tab).
SIZES = (16, 32, 48, 64, 128, 256)


def main() -> None:
    base = len(APP_ICON)
    images = [
        pixel_art(APP_ICON, APP_ICON_PALETTE, size // base) for size in SIZES
    ]
    output = ROOT / "assets" / "icon.ico"
    output.parent.mkdir(exist_ok=True)
    # Cada tamanho vai pronto; sem isso o Pillow reduziria o de 256 px e
    # os menores sairiam borrados.
    images[-1].save(
        output,
        format="ICO",
        sizes=[image.size for image in images],
        append_images=images[:-1],
    )
    print(f"Ícone salvo em {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
