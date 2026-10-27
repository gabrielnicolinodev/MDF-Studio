# Gerador de caixa retangular (Etapa 02)

Tudo em **milímetros**. O motor (`app/core`) não depende do Qt e é testado sem janela.

## Parâmetros

| Parâmetro | Significado | Limites |
|---|---|---|
| Largura / Profundidade / Altura | Medidas externas ou internas, conforme o modo | 5 a 1000 mm |
| Espessura | Espessura **real medida** do MDF (a nominal costuma diferir) | 1 a 25 mm |
| Modo | Medidas externas ou internas | — |
| Tipo | Fechada (6 painéis) ou aberta (5, sem tampa) | — |
| Dedos | Automático, ou nº de segmentos por junta (ímpar, 3 a 99) | — |
| Folga de montagem | Folga total entre dente e encaixe | 0 a 1 mm |
| Kerf | Largura removida pelo laser (0 = desligado) | 0 a 0,6 mm |
| Espaçamento / Área de trabalho | Só para a disposição das peças | 1–50 mm / 50–5000 mm |

Valores não numéricos, NaN, infinito, zero, negativos ou fora dos limites são
rejeitados com mensagem em português. Combinações inviáveis (ex.: junta curta
demais para 3 dedos de 2 mm) também são rejeitadas, nunca "corrigidas" em silêncio.

## Convenção geométrica

- Mundo 3D: x = largura, y = profundidade (frente em y=0), z = altura (base em z=0).
- Cada painel é um retângulo **cheio** da face externa, com recortes de profundidade
  igual à espessura nas arestas de junta:
  base/tampa W×D, frente/traseira W×H, laterais D×H.
- Sistema local do painel: origem no canto inferior esquerdo, u→direita, v→cima,
  contorno anti-horário. `PanelFrame` posiciona o painel no mundo 3D.
- Internas: externas − 2t em x e y; em z, − 2t (fechada) ou − t (aberta).
  No modo "internas" a conta é inversa. As medidas pedidas se tornam exatamente as do resumo.
- Posse dos cantos: base (e tampa) ficam com os cantos horizontais. Nas juntas
  verticais esses trechos são **neutros** (recorte nos dois painéis). Frente e
  traseira têm os dentes das pontas; na caixa aberta o topo da junta vertical é livre.

## Como as juntas são calculadas

Cada junta (`Joint`) liga uma aresta de um painel a uma aresta de outro e é definida
explicitamente em `plan_joints` (12 juntas na fechada, 8 na aberta). Ao longo dela:
duas zonas de canto de comprimento `t`, e o miolo dividido em **N segmentos iguais**
(N ímpar ≥ 3) alternando A, B, A, …, A. Não há sobra de arredondamento nem dente
de largura zero. No modo automático, a largura-alvo é max(3·t, 6 mm); a largura
mínima de um dedo é 2 mm. O contorno de cada painel é o retângulo menos os recortes,
calculado numa grade inteira de 1e-6 mm (determinístico).

Verificação: um teste 3D amostra milhares de pontos da casca e confirma que cada
ponto pertence a **exatamente um** painel (sem sobreposição e sem buracos) e que
nenhum painel invade a cavidade.

## Folga e kerf

São três grandezas separadas: espessura real, folga e kerf.

- **Folga** `c`: cada painel estreita os **seus** dentes em `c/4` por lado, então a
  folga total em cada interface é `c`. Lados que tocam o canto do painel não mudam,
  portanto a folga nunca altera as dimensões externas.
- **Kerf** `k`: o contorno `contour` é sempre o **nominal**. O `cut_path` é o
  caminho de corte deslocado `k/2` para fora (exato para contornos ortogonais),
  aplicado **uma única vez**. Com `k = 0` é idêntico ao nominal e a interface informa
  "sem compensação". Se usar kerf aqui, **não** aplique offset no LightBurn.
- Kerf e folga nunca mudam o número de dedos nem as dimensões nominais (testado).
- Kerf + folga grandes demais para a largura do dedo são rejeitados.

## Disposição e visualização

Disposição em prateleiras, determinística, sem sobreposição e com espaçamento mínimo,
usando a caixa-limite do `cut_path`. Origem no canto superior esquerdo, y para baixo
(como SVG). Padrão 410×400 mm: só uma **referência**, não é a chapa real. Se não
couber, o erro é mostrado e as peças continuam visíveis. A visualização desenha o
mesmo `PanelLayout` que o exportador usará. Linhas de referência são dados separados
(`reference_lines`) e nunca fazem parte de `contour`/`cut_path`.

## Limitações conhecidas

- Sem calibração: **não há garantia de ajuste físico perfeito**. Faça um corte de
  teste e ajuste folga/kerf.
- Sem visualização 3D. A exportação SVG está descrita em `EXPORTACAO_SVG.md`.
- Disposição simples (sem otimização de aproveitamento de chapa).
- Só finger joint; sem tampa articulada, gavetas ou caixas poligonais.
- Compensação de kerf apenas para contornos ortogonais (todos os atuais).
- Só mm; a janela mínima (720 px) deixa a visualização pequena (use zoom).
