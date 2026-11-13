"""Cache simples em disco: cada item é um arquivo dentro de uma pasta."""

import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class FileCache:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def get_or_create(self, name: str, create: Callable[[], bytes]) -> bytes:
        """Pode ser chamado de várias threads ao mesmo tempo, inclusive para
        o mesmo item."""
        path = self._directory / name
        try:
            return path.read_bytes()
        except FileNotFoundError:
            pass

        content = create()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Nome temporário único: duas threads gravando o mesmo item não
        # usam o mesmo arquivo. A troca é atômica: o cache nunca fica com
        # um arquivo pela metade.
        handle, temporary_name = tempfile.mkstemp(
            dir=path.parent, prefix=f"{path.name}.", suffix=".tmp"
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "wb") as file:
                file.write(content)
            temporary.replace(path)
        except PermissionError:
            # No Windows, a troca falha se outra thread estiver lendo o
            # mesmo item, que ela acabou de gravar: o conteúdo é o mesmo.
            logger.debug("Item %s já gravado por outra thread.", name)
        finally:
            temporary.unlink(missing_ok=True)
        return content

    def discard(self, name: str) -> None:
        (self._directory / name).unlink(missing_ok=True)
