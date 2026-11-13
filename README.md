# PokePython

> 🚧 **Projeto em desenvolvimento**: ainda está incompleto e muda com frequência.

Pokédex de desktop com os **151 primeiros Pokémon**, feita em **Python** com **CustomTkinter**. Os dados vêm da [PokéAPI](https://pokeapi.co/): nome, número, tipos, imagem oficial, stats base, habilidades, altura e peso.

## Funcionalidades

- [x] Visual no estilo 8-bit, com fontes pixeladas e o card em tom pastel da cor do tipo do Pokémon
- [x] Temas claro e escuro: abre no claro e troca no botão de sol/lua, com o tema antigo esmaecendo sobre o novo; a escolha fica salva
- [x] Lista à direita com os 151 Pokémon da primeira geração e busca por nome ou número
- [x] Nome, número e tipos (em português) no topo do card
- [x] Imagem oficial de cada Pokémon
- [x] Mini ícone em pixel art de cada Pokémon na lista (ícones de menu da 7ª geração)
- [x] Status base com barras: HP, Ataque, Defesa, Ataque Esp., Defesa Esp., Velocidade e Total
- [x] Habilidades, incluindo a habilidade oculta
- [x] Altura e peso
- [x] Cache local: cada Pokémon é baixado uma vez só e depois funciona offline
- [x] A janela não trava enquanto os dados são baixados
- [x] Downloads em paralelo, com novas tentativas se a rede falhar; o Pokémon anterior e o próximo da lista já ficam baixados
- [x] A arte cresce junto com a janela
- [x] Navegação pelo teclado (veja abaixo)
- [x] Contraste de cores conferido para os 18 tipos, nos dois temas (WCAG AA)

## Atalhos de teclado

| Tecla | O que faz |
| --- | --- |
| ↑ / ↓ | Seleciona o Pokémon anterior / seguinte da lista (respeita a busca) |
| Ctrl+F | Vai para a busca |
| Enter (na busca) | Abre o primeiro resultado |
| Esc (na busca) | Limpa a busca |
| Tab / Shift+Tab | Alterna o foco entre o botão de tema, a busca e a lista |
| Enter ou espaço (no botão de tema) | Troca entre os temas claro e escuro |

## Dados

Os stats e os tipos são os da geração atual, os mesmos do [Pokémon Database](https://pokemondb.net/pokedex/all). Em 11/11/2026, os 151 Pokémon foram conferidos com o pokemondb.net e todos os stats, totais e tipos bateram.

Por usar os valores atuais, alguns Pokémon aparecem diferentes dos jogos antigos. O Clefairy, por exemplo, aparece como tipo Fada, que só passou a existir na 6ª geração.

## Tecnologias

- [Python 3.12+](https://www.python.org/)
- [CustomTkinter](https://customtkinter.tomschimansky.com/): interface gráfica moderna, feita sobre o Tkinter
- [Pillow](https://pypi.org/project/pillow/): carregamento e redimensionamento das imagens
- [PokéAPI](https://pokeapi.co/): dados e imagens dos Pokémon
- [Press Start 2P](https://fonts.google.com/specimen/Press+Start+2P) e [Jersey 10](https://fonts.google.com/specimen/Jersey+10): fontes pixeladas, com licença [SIL Open Font License](assets/fonts/OFL.txt)

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

O tema escolhido fica no arquivo `settings.json`. Para voltar ao padrão (tema claro), é só apagar esse arquivo.

## Testes

```bash
python -m unittest
```

Os testes não acessam a internet: usam uma API falsa.

Para conferir o contraste das cores de todos os tipos e da interface, nos dois temas (texto com pelo menos 4,5:1; barras, bordas e ícones com pelo menos 3:1):

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
│   ├── background.py  # tarefas em segundo plano, com o resultado entregue na janela
│   ├── theme.py       # cores (claro e escuro), espaçamentos, fontes e regras de cor por tipo
│   ├── icons.py       # ícones desenhados com o Pillow (lupa, "×", sol, lua, cursor, ♀ e ♂)
│   ├── pixel.py       # fontes pixeladas e pixel art nítidos em qualquer escala de tela
│   ├── settings.py    # salva e restaura o tema escolhido
│   ├── tooltip.py     # dica que aparece sobre o botão de tema
│   ├── pokemon_list.py  # lista de Pokémon, desenhada num canvas só
│   ├── ctk_adapter.py   # ajustes no CustomTkinter e no Windows (cores, barra de título, transição de tema)
│   └── ui.py          # janela (CustomTkinter)
├── assets/
│   ├── icon.ico       # ícone da janela, em pixel art
│   └── fonts/         # Press Start 2P e Jersey 10, com a licença (OFL.txt)
├── scripts/
│   ├── benchmark_ui.py    # mede a interface e o primeiro uso (antes e depois de cada mudança)
│   ├── check_contrast.py  # tabela de contraste das cores, nos dois temas
│   └── make_icon.py       # gera o assets/icon.ico a partir do desenho em icons.py
├── specs/             # diagnóstico e especificações do projeto
├── tests/             # testes automatizados
├── requirements.txt   # dependências do projeto
└── README.md
```

---

Dados e imagens: [PokéAPI](https://pokeapi.co/). Fontes: Press Start 2P (CodeMan38) e Jersey 10 (Sarah Cadigan-Fried), sob a SIL Open Font License 1.1. Pokémon e seus nomes são marcas registradas da Nintendo / Game Freak / The Pokémon Company. Este é um projeto de estudo, sem fins comerciais.
