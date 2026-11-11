"""Ponto de entrada: monta as dependências e abre a Pokédex."""

from pathlib import Path

from pokedex.cache import FileCache
from pokedex.pokeapi import PokeApiRepository
from pokedex.ui import PokedexWindow

CACHE_DIR = Path(__file__).resolve().parent / ".cache"


def main() -> None:
    PokedexWindow(PokeApiRepository(FileCache(CACHE_DIR))).run()


if __name__ == "__main__":
    main()
