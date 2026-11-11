# PokePython

> 🚧 **Projeto em desenvolvimento**: ainda está incompleto e muda com frequência.

Pokédex de desktop com os **151 primeiros Pokémon**, feita em **Python** com **Tkinter**. Os dados vêm da [PokéAPI](https://pokeapi.co/): nome, número, tipos, imagem oficial, stats base e habilidades.

## Funcionalidades

- [x] Lista com os 151 Pokémon da primeira geração
- [x] Nome, número e tipos (em português)
- [x] Imagem oficial de cada Pokémon
- [x] Stats base: HP, Ataque, Defesa, Ataque Esp., Defesa Esp., Velocidade e Total
- [x] Habilidades, incluindo a habilidade oculta
- [x] Cache local: cada Pokémon é baixado uma vez só e depois funciona offline
- [x] A janela não trava enquanto os dados são baixados

## Dados

Os stats e os tipos são os da geração atual, os mesmos do [Pokémon Database](https://pokemondb.net/pokedex/all). Em 11/11/2026, os 151 Pokémon foram conferidos com o pokemondb.net e todos os stats, totais e tipos bateram.

Por usar os valores atuais, alguns Pokémon aparecem diferentes dos jogos antigos. O Clefairy, por exemplo, aparece como tipo Fada, que só passou a existir na 6ª geração.

## Tecnologias

- [Python 3.12+](https://www.python.org/)
- [Tkinter](https://docs.python.org/3/library/tkinter.html): interface gráfica (já vem com o Python)
- [Pillow](https://pypi.org/project/pillow/): redimensionamento das imagens
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

## Estrutura

```
Pokepython/
├── main.py            # ponto de entrada: monta as peças e abre a janela
├── pokedex/
│   ├── models.py      # dados (Pokemon, PokedexEntry) e o contrato da fonte de dados
│   ├── pokeapi.py     # acesso à PokéAPI e conversão das respostas
│   ├── cache.py       # cache em disco
│   └── ui.py          # janela Tkinter
├── tests/             # testes automatizados
├── requirements.txt   # dependências do projeto
└── README.md
```

---

Dados e imagens: [PokéAPI](https://pokeapi.co/). Pokémon e seus nomes são marcas registradas da Nintendo / Game Freak / The Pokémon Company. Este é um projeto de estudo, sem fins comerciais.
