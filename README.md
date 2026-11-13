# PokePython 🎮

Uma Pokédex de desktop com os 151 primeiros Pokémon, feita em Python com CustomTkinter, com visual 8-bit, dados da PokéAPI, busca por nome ou número, temas claro e escuro e navegação pelo teclado.

## Tecnologias

- Python 3.12+
- CustomTkinter
- Pillow
- PokéAPI

## Instalação

1. Clone o repositório:
```bash
git clone https://github.com/ggoncalves0/Pokepython.git
cd Pokepython
```

2. Crie um ambiente virtual (opcional, mas recomendado):
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Execute a Pokédex:
```bash
python main.py
```

Na primeira vez que cada Pokémon é aberto, é preciso estar conectado à internet.

## Recursos

- Visual 8-bit, com fontes pixeladas e o card em tom pastel da cor do tipo do Pokémon
- Lista com os 151 Pokémon da primeira geração, com um mini ícone de cada um e busca por nome ou número
- Nome, número e tipos (em português), imagem oficial, status base com barras, habilidades (incluindo a oculta), altura e peso
- Temas claro e escuro: abre no claro, e o botão de sol/lua troca de tema com o antigo esmaecendo sobre o novo; a escolha fica salva
- Cache local: cada Pokémon é baixado uma vez só e depois funciona offline
- Downloads em paralelo e em segundo plano, com novas tentativas se a rede falhar: a janela não trava, e o Pokémon anterior e o próximo da lista já ficam baixados
- A arte cresce junto com a janela
- Navegação completa pelo teclado
- Contraste de cores conferido para os 18 tipos, nos dois temas (WCAG AA)

## Atalhos de teclado

| Tecla | Ação |
|---|---|
| `↑` / `↓` | Seleciona o Pokémon anterior / seguinte da lista (respeita a busca) |
| `Ctrl` + `F` | Vai para a busca |
| `Enter` (na busca) | Abre o primeiro resultado |
| `Esc` (na busca) | Limpa a busca |
| `Tab` / `Shift` + `Tab` | Alterna o foco entre o botão de tema, a busca e a lista |
| `Enter` ou `Espaço` (no botão de tema) | Troca entre os temas claro e escuro |

## Testes

```bash
python -m unittest                # testes automatizados, sem acessar a internet
python scripts/check_contrast.py  # contraste das cores de todos os tipos, nos dois temas
```

## Estrutura

```
Pokepython/
├── main.py               # ponto de entrada: monta as peças e abre a janela
├── pokedex/
│   ├── models.py         # dados (Pokemon, PokedexEntry) e o contrato da fonte de dados
│   ├── pokeapi.py        # acesso à PokéAPI e conversão das respostas
│   ├── cache.py          # cache em disco
│   ├── background.py     # tarefas em segundo plano, com o resultado entregue na janela
│   ├── settings.py       # salva e restaura o tema escolhido
│   ├── theme.py          # cores (claro e escuro), espaçamentos, fontes e regras de cor por tipo
│   ├── icons.py          # ícones desenhados com o Pillow (lupa, "×", sol, lua, cursor, ♀ e ♂)
│   ├── pixel.py          # fontes pixeladas e pixel art nítidos em qualquer escala de tela
│   ├── tooltip.py        # dica que aparece sobre o botão de tema
│   ├── pokemon_list.py   # lista de Pokémon, desenhada num canvas só
│   ├── ctk_adapter.py    # ajustes no CustomTkinter e no Windows (cores, barra de título, troca de tema)
│   └── ui.py             # janela principal
├── assets/
│   ├── icon.ico          # ícone da janela, em pixel art
│   └── fonts/            # Press Start 2P e Jersey 10, com a licença (OFL.txt)
├── scripts/
│   ├── check_contrast.py # tabela de contraste das cores, nos dois temas
│   └── make_icon.py      # gera o assets/icon.ico a partir do desenho em icons.py
├── tests/                # testes automatizados
├── requirements.txt      # dependências, com versões fixas
└── README.md
```

## Observações

- Os dados vêm da [PokéAPI](https://pokeapi.co/), e as imagens (arte oficial e ícones da lista), do repositório [PokeAPI/sprites](https://github.com/PokeAPI/sprites). Os stats e os tipos são os da geração atual, conferidos com o [Pokémon Database](https://pokemondb.net/pokedex/all) em 11/11/2026. Por isso, alguns Pokémon aparecem diferentes dos jogos antigos: o Clefairy, por exemplo, é do tipo Fada.
- Os dados baixados ficam na pasta `.cache/`, e o tema escolhido fica no arquivo `settings.json`, os dois na pasta do projeto. Para baixar tudo de novo, apague a pasta `.cache/`; para voltar ao tema claro, apague o `settings.json`.
- Fontes: [Press Start 2P](https://fonts.google.com/specimen/Press+Start+2P) (CodeMan38) e [Jersey 10](https://fonts.google.com/specimen/Jersey+10) (Sarah Cadigan-Fried), sob a [SIL Open Font License 1.1](assets/fonts/OFL.txt).
- Pokémon, seus nomes e suas imagens são marcas registradas da Nintendo / Game Freak / The Pokémon Company.
- Projeto criado para fins de estudo/portfólio.

## 👨‍💻 Autor
Gabriel Gonçalves de Oliveira\
📧 ggoncalvesy03@gmail.com
