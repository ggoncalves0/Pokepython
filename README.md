# PokePython

> 🚧 **Projeto em desenvolvimento**: ainda está incompleto e muda com frequência.

Pokédex de desktop com os **151 primeiros Pokémon**, feita em **Python** com **CustomTkinter**. Os dados vêm da [PokéAPI](https://pokeapi.co/): nome, número, tipos, imagem oficial, stats base, habilidades, altura e peso.

## Funcionalidades

- [x] Visual moderno em tema escuro, com o card em tom pastel da cor do tipo do Pokémon
- [x] Lista à direita com os 151 Pokémon da primeira geração e busca por nome ou número
- [x] Nome, número e tipos (em português) no topo do card
- [x] Imagem oficial de cada Pokémon
- [x] Status base com barras: HP, Ataque, Defesa, Ataque Esp., Defesa Esp., Velocidade e Total
- [x] Habilidades, incluindo a habilidade oculta
- [x] Altura e peso
- [x] Cache local: cada Pokémon é baixado uma vez só e depois funciona offline
- [x] A janela não trava enquanto os dados são baixados
- [x] A arte cresce junto com a janela
- [x] Navegação pelo teclado (veja abaixo)
- [x] Contraste de cores conferido para os 18 tipos (WCAG AA)

## Atalhos de teclado

| Tecla | O que faz |
| --- | --- |
| ↑ / ↓ | Seleciona o Pokémon anterior / seguinte da lista (respeita a busca) |
| Ctrl+F | Vai para a busca |
| Enter (na busca) | Abre o primeiro resultado |
| Esc (na busca) | Limpa a busca |
| Tab / Shift+Tab | Alterna o foco entre a busca e a lista |

## Dados

Os stats e os tipos são os da geração atual, os mesmos do [Pokémon Database](https://pokemondb.net/pokedex/all). Em 11/11/2026, os 151 Pokémon foram conferidos com o pokemondb.net e todos os stats, totais e tipos bateram.

Por usar os valores atuais, alguns Pokémon aparecem diferentes dos jogos antigos. O Clefairy, por exemplo, aparece como tipo Fada, que só passou a existir na 6ª geração.

## Tecnologias

- [Python 3.12+](https://www.python.org/)
- [CustomTkinter](https://customtkinter.tomschimansky.com/): interface gráfica moderna, feita sobre o Tkinter
- [Pillow](https://pypi.org/project/pillow/): carregamento e redimensionamento das imagens
- [PokéAPI](https://pokeapi.co/): dados e imagens dos Pokémon

## Como executar

1. Clone o repositório:
   ```bash
   git clone https://github.com/ggoncalves0/Pokepython.git
   cd Pokepython
   ```

2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

3. Rode o programa (na primeira vez que cada Pokémon é aberto, precisa de internet):
   ```bash
   python main.py
   ```

Os dados baixados ficam na pasta `.cache/`. Para baixar tudo de novo, é só apagar essa pasta.

## Testes

```bash
python -m unittest
```

Os testes não acessam a internet: usam uma API falsa.

Para conferir o contraste das cores de todos os tipos (texto com pelo menos 4,5:1 e barras com pelo menos 3:1):

```bash
python scripts/check_contrast.py
```

## Estrutura

```
Pokepython/
├── main.py            # ponto de entrada: monta as peças e abre a janela
├── pokedex/
│   ├── models.py      # dados (Pokemon, PokedexEntry) e o contrato da fonte de dados
│   ├── pokeapi.py     # acesso à PokéAPI e conversão das respostas
│   ├── cache.py       # cache em disco
│   ├── theme.py       # cores, espaçamentos, fontes e regras de cor por tipo
│   ├── icons.py       # ícones desenhados com o Pillow (lupa e "×")
│   └── ui.py          # janela (CustomTkinter)
├── assets/
│   └── icon.ico       # ícone da janela, em pixel art
├── scripts/
│   ├── check_contrast.py  # tabela de contraste das cores de cada tipo
│   └── make_icon.py       # gera o assets/icon.ico a partir do desenho em icons.py
├── tests/             # testes automatizados
├── requirements.txt   # dependências do projeto
└── README.md
```

---

Dados e imagens: [PokéAPI](https://pokeapi.co/). Pokémon e seus nomes são marcas registradas da Nintendo / Game Freak / The Pokémon Company. Este é um projeto de estudo, sem fins comerciais.
