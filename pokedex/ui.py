"""Janela da Pokédex feita com Tkinter."""

import tkinter as tk
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from io import BytesIO
from tkinter import ttk

from PIL import Image, ImageTk

from .models import PokedexEntry, Pokemon, PokemonRepository

BACKGROUND = "#feffff"
TEXT_COLOR = "#444466"
DETAIL_COLOR = "#403d3d"
SELECTION_COLOR = "#6f9fbd"
ERROR_COLOR = "#e06636"

NAME_FONT = ("Fixedsys", 20)
TITLE_FONT = ("Verdana", 16)
BOLD_FONT = ("Verdana", 10, "bold")
TEXT_FONT = ("Verdana", 10)

IMAGE_SIZE = 240
CHECK_INTERVAL_MS = 50
CONNECTION_ERROR = "Sem conexão com a PokéAPI."

TYPE_NAMES = {
    "normal": "Normal",
    "fire": "Fogo",
    "water": "Água",
    "electric": "Elétrico",
    "grass": "Planta",
    "ice": "Gelo",
    "fighting": "Lutador",
    "poison": "Venenoso",
    "ground": "Terrestre",
    "flying": "Voador",
    "psychic": "Psíquico",
    "bug": "Inseto",
    "rock": "Pedra",
    "ghost": "Fantasma",
    "dragon": "Dragão",
    "dark": "Sombrio",
    "steel": "Aço",
    "fairy": "Fada",
}

STAT_NAMES = {
    "hp": "HP",
    "attack": "Ataque",
    "defense": "Defesa",
    "special-attack": "Ataque Esp.",
    "special-defense": "Defesa Esp.",
    "speed": "Velocidade",
}


def format_number(number: int) -> str:
    return f"#{number:03}"


def format_types(pokemon: Pokemon) -> str:
    return " / ".join(TYPE_NAMES[name] for name in pokemon.types)


def format_stats(pokemon: Pokemon) -> str:
    lines = [
        f"{label}: {pokemon.stats[name]}" for name, label in STAT_NAMES.items()
    ]
    lines.append(f"Total: {pokemon.total}")
    return "\n".join(lines)


def format_abilities(pokemon: Pokemon) -> str:
    lines = list(pokemon.abilities)
    if pokemon.hidden_ability:
        lines.append(f"{pokemon.hidden_ability} (oculta)")
    return "\n".join(lines)


def make_label(
    parent: tk.Misc, font: tuple, color: str = TEXT_COLOR, **options
) -> tk.Label:
    """Cria um Label com o visual padrão da Pokédex."""
    return tk.Label(
        parent, font=font, bg=BACKGROUND, fg=color,
        anchor="w", justify="left", **options,
    )


class PokedexWindow:
    """Janela principal: detalhes à esquerda e a lista dos 151 à direita."""

    def __init__(self, root: tk.Tk, repository: PokemonRepository) -> None:
        self._root = root
        self._repository = repository
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._entries: list[PokedexEntry] = []
        self._pending: Future | None = None
        # Sem guardar essa referência, o Tk descarta a imagem da tela.
        self._photo: ImageTk.PhotoImage | None = None

        root.title("PokePython")
        root.configure(bg=BACKGROUND, padx=15, pady=15)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self._close)
        ttk.Style(root).theme_use("clam")

        self._build_details()
        self._build_list()
        self._set_status("Carregando a Pokédex...")
        self._run_in_background(repository.list_entries, self._show_entries)

    def _build_details(self) -> None:
        details = tk.Frame(self._root, bg=BACKGROUND)
        details.grid(row=0, column=0, sticky="n")
        details.grid_rowconfigure(2, minsize=IMAGE_SIZE)

        # Nome e número ficam num frame próprio para não alargar as colunas.
        header = tk.Frame(details, bg=BACKGROUND)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        self._name = make_label(header, NAME_FONT)
        self._name.pack(side="left")
        self._number = make_label(header, BOLD_FONT)
        self._number.pack(side="right")

        self._types = make_label(details, BOLD_FONT)
        self._types.grid(row=1, column=0, columnspan=2, sticky="w")
        self._image = tk.Label(details, bg=BACKGROUND)
        self._image.grid(row=2, column=0, columnspan=2)

        status_title = make_label(details, TITLE_FONT, text="Status")
        status_title.grid(row=3, column=0, sticky="w")
        abilities_title = make_label(details, TITLE_FONT, text="Habilidades")
        abilities_title.grid(row=3, column=1, sticky="w")

        # Tamanho fixo (em caracteres e linhas): a janela não muda de
        # tamanho ao trocar de Pokémon.
        self._stats = make_label(
            details, TEXT_FONT, DETAIL_COLOR,
            width=16, height=len(STAT_NAMES) + 1,
        )
        self._stats.grid(row=4, column=0, sticky="nw")
        self._abilities = make_label(
            details, TEXT_FONT, DETAIL_COLOR, width=22
        )
        self._abilities.grid(row=4, column=1, sticky="nw")

        self._status = make_label(details, TEXT_FONT)
        self._status.grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )

    def _build_list(self) -> None:
        frame = tk.Frame(self._root, bg=BACKGROUND)
        frame.grid(row=0, column=1, sticky="ns", padx=(15, 0))
        frame.grid_rowconfigure(0, weight=1)

        self._list = tk.Listbox(
            frame,
            width=18,
            font=TEXT_FONT,
            bg=BACKGROUND,
            fg=TEXT_COLOR,
            selectbackground=SELECTION_COLOR,
            selectforeground=BACKGROUND,
            activestyle="none",
            # Mantém a seleção quando o foco vai para outro widget.
            exportselection=False,
        )
        scrollbar = ttk.Scrollbar(
            frame, orient="vertical", command=self._list.yview
        )
        self._list.configure(yscrollcommand=scrollbar.set)
        self._list.grid(row=0, column=0, sticky="ns")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._list.bind("<<ListboxSelect>>", self._on_select)

    def _show_entries(self, entries: list[PokedexEntry]) -> None:
        self._entries = entries
        labels = [f"{format_number(e.number)} {e.name}" for e in entries]
        self._list.insert("end", *labels)
        self._list.selection_set(0)
        self._load(entries[0])

    def _on_select(self, _event: tk.Event) -> None:
        selection = self._list.curselection()
        if selection:
            self._load(self._entries[selection[0]])

    def _load(self, entry: PokedexEntry) -> None:
        if self._pending is not None:
            # Descarta o pedido anterior se ele ainda não começou.
            self._pending.cancel()
        self._set_status(f"Carregando {entry.name}...")
        self._pending = self._run_in_background(
            lambda: self._fetch(entry.number), self._show_pokemon
        )

    def _fetch(self, number: int) -> tuple[Pokemon, Image.Image]:
        """Roda fora da thread da interface: baixa dados e prepara a imagem."""
        pokemon = self._repository.get_pokemon(number)
        image = Image.open(BytesIO(self._repository.get_artwork(pokemon)))
        image.thumbnail((IMAGE_SIZE, IMAGE_SIZE))
        return pokemon, image

    def _show_pokemon(self, result: tuple[Pokemon, Image.Image]) -> None:
        pokemon, image = result
        self._photo = ImageTk.PhotoImage(image)
        self._image.configure(image=self._photo)
        self._name.configure(text=pokemon.name)
        self._number.configure(text=format_number(pokemon.number))
        self._types.configure(text=format_types(pokemon))
        self._stats.configure(text=format_stats(pokemon))
        self._abilities.configure(text=format_abilities(pokemon))
        self._set_status("")

    def _run_in_background[T](
        self, task: Callable[[], T], on_success: Callable[[T], None]
    ) -> Future:
        """Executa `task` em outra thread para a janela não travar."""
        future = self._executor.submit(task)
        self._wait_for(future, on_success)
        return future

    def _wait_for[T](
        self, future: Future, on_success: Callable[[T], None]
    ) -> None:
        """Confere o resultado de tempos em tempos.

        O Tkinter não é thread-safe: só a thread da interface pode mexer
        nos widgets, por isso o resultado é tratado aqui, e não na thread
        que fez o download.
        """
        if not future.done():
            self._root.after(
                CHECK_INTERVAL_MS, self._wait_for, future, on_success
            )
            return
        if future.cancelled():
            return
        try:
            result = future.result()
        except (OSError, ValueError):  # sem rede, erro HTTP, JSON inválido
            self._set_status(CONNECTION_ERROR, ERROR_COLOR)
        else:
            on_success(result)

    def _set_status(self, text: str, color: str = TEXT_COLOR) -> None:
        self._status.configure(text=text, fg=color)

    def _close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._root.destroy()
