# 000 — Diagnóstico (Fase 0)

Levantamento feito antes de qualquer mudança no app, no commit `36d73a5`.
Serve de linha de base para as especificações 001 a 003: toda otimização
é comparada com os números daqui, com o mesmo método e na mesma máquina.

## Ambiente

| Item | Valor |
|---|---|
| Sistema | Windows 11 Enterprise 10.0.26200, escala de tela 100% |
| Python | 3.15.2 |
| CustomTkinter | 6.0.0 |
| Pillow | 13.0.0 |
| Commit | `36d73a5` (árvore limpa) |

## Estado inicial

| Verificação | Resultado |
|---|---|
| `python -m unittest` | 29 testes, todos passando |
| `python scripts/check_contrast.py` | "Tudo certo." nos dois temas |
| `ruff check pokedex` (regras padrão) | 1 aviso: I001 (ordem dos imports em `ui.py`) |
| `ruff check` com E, W, F, I, UP, B, N | 2 avisos: I001 e B905 (`zip` sem `strict=`) |
| `ruff format --check pokedex` | 6 arquivos seriam reformatados |
| `mypy pokedex` (padrão) | 9 erros em 4 arquivos |
| `mypy --strict pokedex` | 21 erros em 5 arquivos: `type-arg` 6, `import-untyped` 3, `assignment` 3, `no-untyped-def` 2, `no-any-return` 2, `misc` 2, `attr-defined` 2, `arg-type` 1 |

O Ruff e o mypy rodaram num ambiente virtual temporário, fora do projeto;
nenhuma ferramenta foi instalada no ambiente do app.

## Medições

Todas com `scripts/benchmark_ui.py`, criado nesta fase.

### Interface com dados falsos (151 Pokémon, sem rede)

Mediana de 5 repetições, em duas execuções seguidas do script. Cada tempo
tem duas leituras:
- até o fim de `update_idletasks()`;
- até o fim de `update()`, que inclui a pintura da janela no Windows.

| Medida | Até `update_idletasks()` | Até `update()` |
|---|---|---|
| Widgets do CustomTkinter | 669 (606 na lista) | — |
| Widgets do Tk no total | 1664 (1516 na lista) | — |
| Montar a lista | 676 a 800 ms | — |
| Tema claro → escuro | 143 a 155 ms | 503 a 513 ms |
| Tema escuro → claro | 144 a 153 ms | 510 a 522 ms |
| Filtrar "char" (3 resultados) | 78 a 88 ms | 95 a 97 ms |
| Limpar a busca (volta às 151 linhas) | 545 a 603 ms | 619 a 631 ms |

### Primeiro uso (PokéAPI de verdade, cache vazio em pasta temporária)

`python scripts/benchmark_ui.py --primeiro-uso`, três execuções seguidas.

| Medida | 1ª | 2ª | 3ª | Mediana |
|---|---|---|---|---|
| Lista na tela | 1,8 s | 1,7 s | 1,8 s | 1,8 s |
| Primeiro ícone | 2,0 s | 1,7 s | 1,8 s | 1,8 s |
| 151 ícones na tela | 32,0 s | 7,3 s | 6,9 s | 7,3 s |
| Clique → card completo, #150 sem cache | 290 ms | 158 ms | 157 ms | 158 ms |
| Clique → card completo, #094 sem cache | 364 ms | 155 ms | 160 ms | 160 ms |
| Clique → card completo, #006 sem cache | 260 ms | 171 ms | 270 ms | 260 ms |
| Clique → card completo, #150 em cache | 116 ms | 105 ms | 98 ms | 105 ms |

Atenção à variação: a 1ª execução levou 32 s para os ícones; as outras,
cerca de 7 s. A causa provável é a CDN do GitHub, que guarda os arquivos
depois do primeiro pedido. Para o critério "4 vezes mais rápido" (D), a
comparação precisa usar a mediana de várias execuções na mesma rede. A
alternativa é um servidor local com latência fixa, que torna a medida
reproduzível (decisão para o design).

## Bugs

Método de reprodução: roteiros que abrem a janela com dados falsos e os
ícones reais do cache (PNG com fundo transparente). Uma thread separada
fotografa a tela a cada ~3 ms enquanto o laço do Tk roda normalmente.
- A janela de teste fica "sempre por cima" durante a captura.
- Quadros em que outra janela aparece são descartados.
- O tema de abertura é forçado no roteiro; o `settings.json` não é lido
  nem gravado.

### A. Quadrados do tema inicial ao clicar no ×

**Passo a passo tentado:**
1. Abrir o app num tema (claro ou escuro).
2. Trocar para o outro tema.
3. Buscar "char".
4. Limpar a busca pelo × (`invoke()` no botão, com o mouse sobre ele), por Esc ou apagando o texto.
5. Repetir 20 vezes em cada combinação.

**Causa (pré-condição) confirmada:**
- Todo widget do CustomTkinter é um `tkinter.Frame` com um canvas por cima.
- A cor do Frame é definida uma única vez, na criação (`ctk_base_class.py`, linha 68).
- `_draw()` não a atualiza (linhas 104 a 108, atualização comentada de propósito). `configure(bg_color=…)` também não: só guarda a cor e redesenha o canvas (linhas 122 a 130).
- Medido: o app abre no claro, vai para o escuro, e o Frame das linhas da lista continua `#f8f9fb`, a cor da lateral no tema claro. No sentido contrário, continua `#1f2029`.
- Isso vale para qualquer mudança de cor depois da criação (hover, seleção, troca do pastel), não só para a troca de tema.

**Sintoma visual: reproduzido no vídeo do Gabriel**
(`2026-11-13 08-39-21.mp4`, 28,5 s, quadros analisados a cada 0,5 s).

Passo a passo do vídeo:
1. Abrir o app no tema claro.
2. Rolar a lista até o #042, de modo que as primeiras linhas saiam da vista.
3. Trocar o tema pelo botão de sol/lua (com a dica "Mudar para tema escuro" na tela).
4. Digitar uma busca sem resultado ("asdsa"). Aparece "Nenhum Pokémon encontrado".
5. Clicar no ×.

Resultado (9 s e 11 s do vídeo):
- As 151 linhas voltam como três blocos sólidos cada, no lugar do ícone, do número e do nome.
- Os blocos têm a cor do tema de abertura: brancos no escuro e, no segundo trecho (abriu escuro, foi para o claro), escuros no claro.
- **Os blocos ficam na tela.** Cada linha só se corrige quando o mouse passa por cima (9,5 s), porque o hover muda a cor da linha e força o redesenho.
- Aos 10 s, a barra de rolagem reaparece como um bloco branco. É o mesmo defeito: ela entra e sai da tela com `grid()`/`grid_remove()`.

Os roteiros automáticos não reproduziram os blocos:
- 100 tentativas filmadas a ~3 ms por quadro, com ×, Esc e apagar, nos dois sentidos;
- a sequência exata do vídeo, inclusive a lista rolada e a busca sem resultado, com e sem a janela "sempre por cima".

Falta algo da interação real, provavelmente o clique de verdade no botão de tema com a dica aberta; o roteiro não conseguiu abrir a dica com um mouse simulado. Por isso a verificação da 001 usa a pré-condição, que é determinística:

| Momento | Widgets da CTk com o Frame na cor errada |
|---|---|
| App aberto no claro | 9 de 669 |
| Depois de trocar para o escuro | **668 de 669** |
| De volta ao claro | 9 de 669 |

"Cor errada" quer dizer que `tkinter.Frame.cget(widget, "bg")` é diferente da cor que o próprio widget usa como fundo no tema atual. Mesmo no tema de abertura, 9 widgets já estão errados: os que mudaram de cor depois de criados, como os filhos do card que ganha o pastel. A meta é 0 em qualquer momento. Além disso, o roteiro do vídeo entra como teste manual.

### B. Glitch ao digitar rápido (e ao rolar rápido)

**Passo a passo tentado:**
- Digitar "charizard" e "pidgeotto" a 10 teclas por segundo, com o evento de tecla real no `tk.Entry` interno.
- Arrastar a lista por 60 posições em ~1 s.
- Filmar a lista e contar faixas de linha vazias.

**Confirmado por leitura:**
- `_apply_filter` roda a cada `<KeyRelease>`, sem espera (`ui.py`, linha 610).
- Cada mudança de texto passa pelas 151 linhas (`grid()`/`grid_remove()`, linhas 1108 a 1113).

**Medido:**
- Filtrar custa ~90 ms.
- Voltar às 151 linhas (apagar o último caractere ou limpar) congela a janela por ~600 ms. Esse congelamento é o candidato mais forte para o "glitch".

**Rolagem: reproduzida no vídeo (4,5 a 5 s).**
- Arrastando a barra de rolagem rápido, as linhas aparecem rasgadas: pedaços de linhas sobrepostos, "#074 Geodude" repetido em alturas diferentes e textos cortados ao meio.
- Acontece no tema de abertura, sem troca de tema antes, então é independente do A.
- Causa provável:
  - cada uma das 151 linhas é uma janela própria do Windows (1516 janelas na lista);
  - ao rolar, o canvas move todas, e o conteúdo de cada uma é repintado depois, em momentos diferentes.
- Meus roteiros (`yview_moveto` em 60 posições) não reproduziram o rasgo, porque contavam faixas vazias, e o rasgo não deixa faixa vazia. O roteiro do vídeo entra como teste manual da 001.

**Digitação:**
- No vídeo, a digitação não mostra defeito próprio. O que aparece são os blocos do A ao limpar e o bloco da barra de rolagem.
- Nos meus roteiros, a 10 teclas/s, também não apareceu área vazia.
- O congelamento de ~600 ms ao voltar às 151 linhas continua medido, e continua sendo o defeito da digitação.

### C. A tela "apaga" ao trocar o tema

**Passo a passo:** com o app aberto, trocar o tema e filmar a janela inteira.

**Reproduzido.** Logo depois da troca, a janela fica lisa, só com a cor de fundo do tema novo e nenhum widget, até todos se redesenharem. O vídeo mostra o mesmo:
- aos 6 s, a janela inteira fica branca;
- aos 6,5 s, a lista aparece só como retângulos escuros, ainda sem texto nem ícones.

**Causas confirmadas:**
1. **Redesenho um a um, como você diagnosticou.**
   - `ctk.set_appearance_mode` chama 671 callbacks (`appearance_mode_tracker.py`, linhas 65 a 79).
   - Cada widget roda `_draw()` e `update_idletasks()` (`ctk_base_class.py`, linhas 220 a 223).
   - Medido: ~150 ms até `update_idletasks()` e ~510 ms até a janela terminar de pintar.
2. **Faltava no diagnóstico:** no Windows, a janela principal chama `withdraw()` e `deiconify()` em `_windows_set_titlebar_color` (`ctk_tk.py`, linhas 276 a 330), para repintar a barra de título. A janela some e volta antes de os widgets serem redesenhados; daí o quadro vazio.
3. **Observação:** `update_callbacks` engole qualquer exceção (`except Exception: continue`), então um erro durante a troca passaria em silêncio.

### D. Lentidão no primeiro uso

**Passo a passo:** abrir o app com cache vazio, esperar os ícones, clicar em Pokémon fora do cache.

**Confirmado por leitura e medição:**
- `_load_icons` baixa os 151 ícones em sequência, com um único worker, e para no primeiro erro (`ui.py`, linhas 863 a 884). Na 3ª execução: 6,9 s; 32 s com a CDN fria.
- `pokeapi.download` abre uma conexão HTTPS nova a cada pedido, com `urlopen` sem reaproveitamento (`pokeapi.py`, linhas 34 a 38).
- O Pokémon clicado espera na fila de um worker só (`_executor`, linha 246).
  - `cancel()` só descarta pedidos que ainda não começaram.
  - Ao navegar rápido por Pokémon fora do cache, cada um espera o anterior.
- O card não muda até os dados chegarem. O clique só pinta a linha de cinza (`_select`, linhas 1141 a 1152).
- A lista é montada na thread da interface (676 a 800 ms), e os ícones também são decodificados nela (`_show_icons`, linhas 886 a 902).

**Achado a mais:** o resultado de cada tarefa em segundo plano é conferido a cada 50 ms (`CHECK_INTERVAL_MS`). Isso soma até 50 ms em todo clique, inclusive com o Pokémon em cache (105 ms medidos).

## Revisão do código, por gravidade

### Alta

1. **A interface pode ficar presa em "Carregando...".**
   - `_wait_for` só trata `OSError` e `ValueError` (`ui.py`, linha 1306). Qualquer outra exceção na tarefa (`KeyError` de um tipo desconhecido, `TypeError` de um item antigo do cache em `Pokemon(**data)`) sobe pelo `after`.
   - O aviso "Carregando X..." fica na tela e a linha fica cinza para sempre.
   - Nada é registrado em log.
2. **Os ícones param no primeiro erro, para a sessão inteira.**
   - `download_all` sai do laço em qualquer `OSError` (linha 879). Um 404 ou uma falha momentânea deixa os ícones restantes sem carregar.
   - Se a tarefa levantar outra exceção, o marcador de fim nunca é enviado, e `_show_icons` continua se reagendando a cada 50 ms (linha 902) até a janela fechar.
3. **Um item corrompido no cache nunca se recupera.**
   - `FileCache.get_or_create` devolve o que estiver no disco (`cache.py`, linha 17). Se o JSON estiver estragado, `json.loads` levanta `ValueError`, que vira "Sem conexão com a PokéAPI." (mensagem errada), e o item nunca é baixado de novo.
   - Um ícone estragado é ignorado em silêncio (linha 898).
4. **Gravação do cache insegura entre threads.**
   - O nome temporário é fixo (`nome.tmp`, `cache.py`, linha 22). Duas threads gravando o mesmo item (por exemplo, pré-carga e clique, como pede a 001) usariam o mesmo arquivo temporário.
   - No Windows, `replace` pode falhar com `PermissionError` se o arquivo estiver aberto.
5. **Versões soltas, com dependência de API privada.**
   - `requirements.txt` aceita `customtkinter>=6,<7` e qualquer Pillow, mas o código depende de detalhes internos da 6.0.0:
     - `_scrollbar` e `_parent_canvas` (linhas 478, 489, 915, 1080, 1121);
     - os internos do `CTkImage` em `PixelImage` (`pixel.py`);
     - o `focus` do `CTkButton` em `IconButton`.
   - Uma versão 6.x nova pode quebrar o app sem aviso.

### Média

6. **`PokedexWindow` faz tudo** (`ui.py`, 1327 linhas): estado, regras, montagem e desenho na mesma classe. Nada da lógica de seleção e busca é testável sem abrir uma janela.
7. **Sem `logging` no projeto.** Erros silenciados:
   - `save_theme` (`settings.py`, linha 26);
   - `_set_window_icon` (`ui.py`, linha 1243);
   - ícones e itens do cache estragados.
8. **`settings.json` gravado sem troca atômica** (`settings.py`, linha 24). Se o app fechar no meio da gravação, a escolha se perde (ele volta ao padrão sem avisar).
9. **`_scroll_to` chama `update_idletasks()` a cada seleção** (`ui.py`, linha 1077). Isso força o layout inteiro a cada ↑/↓.
10. **O botão de tema usa a cor do tipo no anel de foco** (`ui.py`, linha 533). A busca passou a usar `FOCUS_COLOR` justamente porque vermelho parecia erro.
11. **Rede sem novas tentativas e sem limite de conexões simultâneas** (`pokeapi.py`). Hoje só há uma conexão por vez, mas a 001 pede paralelismo.

### Baixa

12. **Selos de tipo destruídos e recriados a cada Pokémon** (`clear(self._badges)`, linha 1204). Funciona, mas cria e destrói widgets à toa.
13. **Callback de escala nunca removido.** `ScalingTracker.add_widget(self._snap_title_fonts, ...)` (linha 332) fica registrado depois de fechar a janela.
14. **Linha de base do Ruff e do mypy:** I001, B905, 6 arquivos fora do `ruff format` e 21 erros no `mypy --strict`.
15. **`settings.json` fica na pasta do projeto** (`ui.py`, linha 125). Funciona para um projeto de estudo, mas mistura dados do usuário com o código.

## O que muda na proposta da 001

- **C:** a causa inclui o `withdraw()`/`deiconify()` da janela principal, e o design precisa tratar isso. Os ~150 ms medidos até `update_idletasks()` não incluem a pintura; até `update()` são ~510 ms. Proponho que o critério "≤ 200 ms" use a medida até `update()`.
- **A:** reproduzido no vídeo. O teste automático usa a pré-condição: nenhum widget com o Frame na cor errada, contra 668 de 669 hoje. O roteiro do vídeo entra como teste manual, em 20 repetições.
- **B:** o rasgo ao rolar está no vídeo e entra como teste manual. Para digitação, os critérios de tempo (espera de 150 ms e filtro ≤ 30 ms) atacam o congelamento medido.
- **D:** confirmado. Os 50 ms de consulta entram como causa extra, e o critério "4 vezes mais rápido" precisa definir a mediana de várias execuções, ou um servidor local com latência fixa.

## Correção rápida de A e C (antes da Fase 1)

Decisão do Gabriel, depois do diagnóstico: corrigir A e C antes de seguir o
SDD. As especificações 001 a 003 partem deste estado. Se a 001 trocar a
lista (por exemplo, por uma lista virtualizada), estes ajustes podem ser
revistos.

### O que mudou

- **`pokedex/ctk_adapter.py` (novo).** É o único lugar com API privada do CustomTkinter introduzida por esta correção. Cada ajuste traz o motivo e as linhas da biblioteca:
  - **C, barra de título:** muda pela API do Windows (`DwmSetWindowAttribute`), sem `withdraw()`/`deiconify()`. Na abertura, quando a janela ainda não apareceu, segue o código original.
  - **C, redesenho:** sai o `update_idletasks()` de cada widget na troca de tema, e a janela se redesenha uma vez só.
  - **A, cor do Frame:** `sync_backgrounds()` acerta a cor do Frame de um widget e dos filhos. É chamada logo antes de o widget voltar à tela, ainda escondido.
  - **A, repintura:** `repaint()` pede ao Windows a repintura que o hover fazia no vídeo.
- **`pokedex/ui.py`:**
  - chama `ctk_adapter.install()` antes de criar a janela;
  - chama `sync_backgrounds()` antes de mostrar de novo as linhas da busca, o aviso sem resultado, o ×, a barra de rolagem, o "OCULTA" e o cursor ▶;
  - chama `repaint()` depois de a busca devolver as linhas e de a barra de rolagem voltar.
- **`tests/test_ctk_adapter.py` (novo, 4 testes com janela Tk).** Os 4 falham com os ajustes desligados e passam com eles ligados.
- **`scripts/benchmark_ui.py`:** passou a medir também as linhas que voltam depois da busca com o Frame na cor errada.

### Alternativa descartada

Acertar a cor do Frame de todos os ~670 widgets a cada troca de tema, dentro do `_draw()`. Funciona, mas cada mudança de cor de um `tkinter.Frame` faz o Tk refazer o layout do pai.

Medido com variantes alternadas, na mesma máquina, até o fim de `update()`:

| Variante | Troca de tema |
|---|---|
| Sem ajustes | 554 a 690 ms |
| Só os ajustes do C | 201 a 205 ms |
| C + cor de todos os Frames na troca | 606 a 1169 ms |
| C + cor só ao voltar à tela (escolhida) | 199 a 348 ms |

Isso não faz falta: os Frames do Tk no Windows têm `WS_CLIPCHILDREN`, então só aparecem onde os filhos não se pintam. Isso acontece nos widgets que voltam à tela.

### Antes × depois

Medições com `scripts/benchmark_ui.py`, na mesma máquina, com o PC em uso. Nas rodadas com carga, os tempos variaram até 50%. Abaixo, a rodada mais limpa de cada lado.

| Medida | Antes | Depois |
|---|---|---|
| Linhas que voltam depois da busca com o Frame na cor errada (troca de tema, busca sem resultado, ×) | 604 de 604 | **0 de 604** |
| Trocar o tema, até `update()` | ~510 ms | **~212 ms** |
| Janela durante a troca | some e volta vazia (> 1,5 s no filme, com a captura disputando a CPU) | sempre com conteúdo; 1 quadro intermediário (~30 ms) |
| Barra de título | acompanha o tema | acompanha o tema: (243, 243, 243) no claro e (32, 32, 32) no escuro |
| Filtrar "char", até `update()` | ~96 ms | ~103 ms |
| Limpar a busca, até `update()` | ~625 ms | ~676 ms |
| Testes | 29 | 33 |

Custo conhecido: a primeira limpeza de busca depois de uma troca de tema acerta a cor das linhas escondidas, cerca de 140 ms a mais. As seguintes quase não pagam nada, porque as cores já estão certas.

### O que falta

- **A, verificação visual:** o sintoma não se reproduz nos roteiros automáticos (veja a seção do bug A). A confirmação final é o Gabriel repetir o passo a passo do vídeo, 20 vezes, alternando os temas.
- **B:** não foi tratado. O rasgo ao rolar e o congelamento de ~600 ms ao limpar a busca ficam para a 001.
- **D:** não foi tratado. Fica para a 001.
- **Critério da 001 para C (≤ 200 ms e 5 vezes mais rápido):** 212 ms é 2,4 vezes mais rápido que os ~510 ms da Fase 0. O restante depende de reduzir os ~670 widgets, também na 001.

## Correção de B e D, do × e da troca de tema (antes da Fase 1)

Pedido do Gabriel, depois da correção de A e C:
- tratar B e D;
- verificar um pequeno bug visual ao buscar um Pokémon e clicar no ×;
- deixar a troca de tema "mais dinâmica e suave".

Como na correção anterior, isto vem antes da Fase 1. As especificações 001 a 003 partem deste estado.

### O × deixava a lista vazia

- **Passo a passo:** buscar "pikachu" e clicar no ×.
- **Filmado:** o contador voltava a "151 Pokémon" em ~60 ms, mas a lista ficava vazia por mais de 800 ms. Era o tempo de as 151 linhas (606 widgets, 1516 janelas do Windows) voltarem com `grid()` e se pintarem.
- **Causa:** a mesma do congelamento do B. A lista em canvas (abaixo) resolve os dois: no filme, a lista inteira volta em ~44 ms, mesmo com a captura disputando a CPU.

### O que mudou

**B: lista em canvas (`pokedex/pokemon_list.py`, novo).**
- A lista é um único `tk.Canvas`. Cada linha é feita de itens de desenho (ícone, número, nome, ♀ e ♂), sem widgets.
- Hover, seleção e anel de foco são retângulos com cantos em degrau, como pixel art.
- Filtrar só move e esconde itens. Trocar o tema só muda as cores.
- A busca roda uma vez só, 150 ms depois da última tecla (`FILTER_DELAY_MS`). Enter e as setas aplicam na hora. O × aparece e some a cada tecla.

**D: primeiro uso.**
- **`pokedex/background.py` (novo):** roda tarefas em threads, com prioridade e cancelamento, e entrega o resultado na thread do Tk.
  - Os resultados são conferidos a cada 10 ms (antes, 50 ms), só enquanto há tarefas.
  - Erros vão para quem pediu ou para o log.
- **Três filas, para o clique nunca esperar as outras:**
  - o Pokémon escolhido, com 2 threads;
  - a pré-carga dos vizinhos, com 1;
  - os ícones, com 4. Os das linhas visíveis vêm primeiro, e a decodificação é feita fora da thread do Tk.
- **`pokedex/pokeapi.py`:**
  - reaproveita a conexão (keep-alive, uma por thread);
  - tenta de novo até 3 vezes, esperando 0,5, 1 e 2 s, em falha de rede, erro 5xx ou 429; não tenta de novo em 404 nem nos outros 4xx;
  - faz no máximo 6 pedidos ao mesmo tempo;
  - segue redirecionamentos e manda User-Agent e tempo limite;
  - descarta e baixa de novo um item corrompido do cache (JSON ou PNG); um download que não é PNG não vai para o cache.
- **`pokedex/cache.py`:** grava num arquivo temporário de nome único e troca de uma vez. Duas threads gravando o mesmo item não colidem.
- **Card de espera:**
  - Se os dados não chegam em 50 ms, o card mostra nome, número e "Carregando...". Se o download falhar, mostra a mensagem de erro.
  - Antes de mostrar o card de espera, o app entrega o que já ficou pronto. Com o Pokémon no cache, o card completo entra direto e o de espera não pisca.
- **Pré-carga:** depois de cada Pokémon, o anterior e o próximo da lista são baixados. Vizinhos de uma escolha anterior que ainda não começaram são cancelados.

**Troca de tema suave (`ctk_adapter.WindowCover`).**
- Ao trocar, uma foto da janela (`PrintWindow`) cobre o app numa camada do Windows (`UpdateLayeredWindow`).
- O tema muda por baixo da foto, e ela esmaece em 220 ms: 12 passos, rápido no começo e suave no fim.
- A camada não recebe mouse nem foco e fica sempre logo acima da janela.

**`scripts/benchmark_ui.py`.** Passou a usar a lista nova. A contagem de Frames das linhas na cor errada saiu, porque as linhas não são mais widgets. Entraram a troca de tema pelo botão e o tempo até o card "Carregando...".

### Alternativas descartadas

- **Capa feita com uma `Toplevel` do Tk e a foto num `Label`.**
  - Na primeira versão, a capa surgia ~250 ms depois do tema novo, por causa da animação do Windows ao mostrar uma janela.
  - Desligar essa animação (`DWMWA_TRANSITIONS_FORCEDISABLED`) só resolveu a primeira troca.
  - Da segunda em diante, a foto só aparecia quando o Tk repintava o `Label`, ~100 ms depois do tema novo. A troca piscava: tema novo, cinza, tema novo.
  - Medido sem filmar, lendo um pixel do fundo 40 ms depois da troca: só a 1ª de 6 trocas tinha a foto por cima. Com a camada do Windows, as 6.
- **Filmar a transição com uma thread do próprio app.** A captura disputa o GIL com a interface, e os tempos ficavam inflados. A medição final filma de outro processo.

### Antes × depois

Mesma máquina e mesmo método da Fase 0. Com dados falsos: mediana de 5 repetições, em duas execuções seguidas.

| Medida | Fase 0 | Depois de A e C | Agora |
|---|---|---|---|
| Widgets do CustomTkinter | 669 (606 na lista) | 669 | **63** (1 na lista: a barra de rolagem) |
| Widgets do Tk no total | 1664 (1516 na lista) | 1664 | **147** (3 na lista) |
| Montar a lista | 676 a 800 ms | — | **24 a 26 ms** |
| Trocar o tema, até `update()` | 503 a 522 ms | ~212 ms | **29 a 31 ms** |
| Trocar o tema pelo botão (foto + troca), até `update()` | — | — | **57 a 60 ms**, e depois a foto esmaece em 220 ms |
| Filtrar "char", até `update()` | 95 a 97 ms | ~103 ms | **10 ms** |
| Limpar a busca, até `update()` | 619 a 631 ms | ~676 ms | **8 ms** |
| Testes | 29 | 33 | **57** |
| `ruff check pokedex` | 1 aviso (I001) | — | **nenhum** |
| `mypy pokedex` | 9 erros em 4 arquivos | — | 9 erros em 6 arquivos: 7 de "customtkinter sem tipos" (os módulos novos também o importam) e os 2 `NEAREST` de antes |

Numa execução logo depois de mudar o código, montar a lista levou 185 ms. As duas seguintes ficaram em 24 e 26 ms.

Filmado de outro processo, a troca pelo botão leva ~80 ms até a foto começar a esmaecer. O tema novo aparece por inteiro ~300 ms depois do clique. Nas 3 trocas filmadas, o fundo vai do tema antigo ao novo sem voltar atrás nem piscar.

Primeiro uso, com a PokéAPI de verdade e cache vazio: três execuções seguidas.

| Medida | Fase 0 (mediana) | Agora | Mediana |
|---|---|---|---|
| Lista na tela | 1,8 s | 0,3 / 0,4 / 0,3 s | **0,3 s** |
| Primeiro ícone | 1,8 s | 0,3 / 0,4 / 0,4 s | **0,4 s** |
| 151 ícones na tela | 7,3 s | 0,7 / 0,6 / 0,9 s | **0,7 s** |
| Clique → "Carregando..." no card | — (o card não mudava) | 75 a 87 ms | **77 ms** |
| Clique → card completo, #150 sem cache | 158 ms | 112 / 283 / 112 ms | **112 ms** |
| Clique → card completo, #094 sem cache | 160 ms | 111 / 187 / 94 ms | **111 ms** |
| Clique → card completo, #006 sem cache | 260 ms | 242 / 87 / 78 ms | **87 ms** |
| Clique → card completo, #150 em cache | 105 ms | 51 / 53 / 52 ms | **52 ms** |

Em cada clique em cache, o trabalho fica assim:
- os dados ficam prontos em 1 a 11 ms;
- montar o card leva ~25 ms;
- desenhar leva ~13 ms.

Numa execução anterior, com a CDN lenta, os ícones levaram 7,1 s. Essa rodada também mostrou um defeito, corrigido antes das medidas acima: a pré-carga ocupava as 2 threads do clique, e um Pokémon em cache esperou 251 ms. Daí a fila própria da pré-carga.

### Critérios da 001, como propostos

| Critério | Medido | Situação |
|---|---|---|
| A: limpar a busca depois de trocar o tema não mostra a cor do outro tema | as linhas da lista não são mais widgets; o que volta à tela continua com `sync_backgrounds()` | falta o teste manual (roteiro do vídeo, 20 vezes) |
| B: busca roda uma vez, 150 ms depois da última tecla, em até 30 ms | 8 a 10 ms | ok |
| B: rolar rápido sem rasgar nem mostrar áreas vazias | 52 quadros filmados rolando rápido, sem rasgo | falta o teste manual (roteiro do vídeo) |
| C: troca em até 200 ms, 5 vezes mais rápida, sem quadro em branco | troca em 29 a 31 ms (cerca de 17 vezes mais rápida); sem quadro em branco | **conflito:** com o esmaecimento, a transição visível termina em ~300 ms (veja abaixo) |
| D: ícones 4 vezes mais rápidos, os visíveis primeiro | 7,3 s → 0,7 s (10 vezes) | ok |
| D: ícone que falha é tentado de novo até 3 vezes, sem parar os outros | testes de `DownloadTest` | ok |
| D: nome, número e "carregando" no card em até 100 ms | 75 a 87 ms | ok |
| D: com cache, card completo em até 150 ms | 51 a 53 ms | ok |
| D: anterior e próximo pré-carregados | fila própria, com cancelamento | ok |

### O que falta

- **A e B, verificação manual:** repetir o roteiro do vídeo, alternando os temas, e arrastar a barra de rolagem rápido.
- **C, decisão para a 001:** o critério diz "termina em no máximo 200 ms", mas o esmaecimento pedido depois dura 220 ms a mais. Há dois caminhos:
  - medir o critério até o tema novo estar desenhado por baixo da foto (57 a 60 ms) e tratar a animação como requisito à parte;
  - encurtar o esmaecimento para ~130 ms, para a transição inteira caber nos 200 ms.
