"""Preferências da interface, guardadas num JSON pequeno entre uma
execução e outra. Hoje só o tema: {"theme": "dark"}."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Os mesmos nomes aceitos por ctk.set_appearance_mode.
THEMES = ("system", "light", "dark")
DEFAULT_THEME = "light"


def load_theme(path: Path) -> str:
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DEFAULT_THEME
    theme = settings.get("theme") if isinstance(settings, dict) else None
    return theme if theme in THEMES else DEFAULT_THEME


def save_theme(path: Path, theme: str) -> None:
    # Sem conseguir gravar, o app segue; só não lembra o tema depois.
    try:
        path.write_text(json.dumps({"theme": theme}), encoding="utf-8")
    except OSError:
        logger.warning("Não deu para salvar o tema em %s.", path)
