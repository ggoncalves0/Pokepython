"""Cache simples em disco: cada item é um arquivo dentro de uma pasta."""

from collections.abc import Callable
from pathlib import Path


class FileCache:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def get_or_create(self, name: str, create: Callable[[], bytes]) -> bytes:
        """Devolve o conteúdo salvo em `name`.

        Se ele ainda não existir, gera com `create` e salva.
        """
        path = self._directory / name
        if path.exists():
            return path.read_bytes()

        content = create()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_bytes(content)
        # Troca atômica: o cache nunca fica com um arquivo pela metade.
        temporary.replace(path)
        return content
