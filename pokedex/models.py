"""Modelos da Pokédex. Não dependem da API nem da interface."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PokedexEntry:
    """Linha da lista da Pokédex."""

    number: int
    name: str


@dataclass(frozen=True)
class Pokemon:
    """Dados de um Pokémon.

    Tipos e stats usam os identificadores da PokéAPI ("electric",
    "special-attack"); a tradução para exibição fica na interface.
    Altura em metros e peso em quilos.
    """

    number: int
    name: str
    types: list[str]
    stats: dict[str, int]
    abilities: list[str]
    hidden_ability: str | None
    artwork_url: str
    height: float
    weight: float

    @property
    def total(self) -> int:
        """Soma dos stats base."""
        return sum(self.stats.values())


class PokemonRepository(Protocol):
    """O que a interface precisa de uma fonte de dados.

    Pode ser a PokéAPI ou dados falsos num teste.
    """

    def list_entries(self) -> list[PokedexEntry]: ...

    def get_pokemon(self, number: int) -> Pokemon: ...

    def get_artwork(self, pokemon: Pokemon) -> bytes: ...
