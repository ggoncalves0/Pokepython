"""Preferências da interface, guardadas num JSON pequeno entre uma
execução e outra. Hoje só o tema: {"theme": "dark"}."""

import json
from pathlib import Path

# Os mesmos nomes do ctk.set_appearance_mode.
THEMES = ("system", "light", "dark")
DEFAULT_THEME = "system"  # segue o tema do sistema operacional


def load_theme(path: Path) -> str:
    """Tema salvo; o padrão se o arquivo não existir ou estiver estranho."""
    try:
        theme = json.loads(path.read_text(encoding="utf-8")).get("theme")
    except (OSError, ValueError, AttributeError):  # sem arquivo, JSON ruim
        return DEFAULT_THEME
    return theme if theme in THEMES else DEFAULT_THEME


def save_theme(path: Path, theme: str) -> None:
    """Grava o tema. Se não conseguir, o app segue; só não lembra depois."""
    try:
        path.write_text(json.dumps({"theme": theme}), encoding="utf-8")
    except OSError:
        pass
