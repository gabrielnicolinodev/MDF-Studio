# Exportação SVG (Etapa 03)

> **Status de validação.** O SVG foi verificado por testes automatizados e aberto num
> renderizador SVG independente (Qt). **Não foi testado no LightBurn nem em corte
> físico.** Siga a seção "Checklist antes do primeiro corte" abaixo.

## Como exportar

1. **Geradores → Caixa retangular**, preencha os parâmetros e clique em **Gerar projeto**.
2. Na seção **Exportação SVG** (final do formulário), escolha:
   - **Margem externa do SVG (mm):** espaço entre as peças e a borda do desenho.
   - **Incluir identificações:** nome e medidas de cada peça (desligado por padrão).
   - **Incluir linhas auxiliares:** retângulo externo e linhas de base dos recortes
     (desligado por padrão).
3. Confira **"Arquivo SVG: L × A mm"** antes de salvar. É o tamanho do **desenho**
   (peças + margem), **não** o da chapa de MDF.
4. Clique em **Exportar SVG…**. O diálogo abre na **pasta de exportação das
   Configurações** (se ela existir; senão, na sua pasta pessoal) com o nome sugerido
   `caixa_LxPxAmm.svg` (medidas externas). Você pode trocar pasta e nome.
5. Se o arquivo já existir, o app **pergunta** antes de substituir. Cancelar o diálogo
   não grava nada.
6. A mensagem de sucesso só aparece depois que o arquivo foi gravado e **relido e
   validado**. Erros (pasta inexistente, sem permissão, disco cheio) são mostrados
   e nada é dado como gravado.

Se você alterar qualquer parâmetro depois de gerar, a exportação é **bloqueada** até
clicar em **Gerar projeto** de novo, para o arquivo corresponder ao que está na tela.
Projetos com erro (inclusive peças que não cabem na área de trabalho) não exportam.

O espaçamento **entre peças** é o definido em "Disposição das peças".

## Formato do arquivo

```xml
<svg xmlns="http://www.w3.org/2000/svg" version="1.1"
     width="320mm" height="145mm" viewBox="0 0 320 145">
  <title>…</title><desc>unidades, kerf, aviso sobre o LightBurn</desc>
  <g id="corte" fill="none" stroke="#FF0000" stroke-width="0.1">
    <path id="painel-base" d="M x,y L x,y … Z"/>   <!-- um por painel, fechado -->
  </g>
  <g id="identificacao" …>   <!-- opcional: <text> por peça -->
  <g id="auxiliares" …>      <!-- opcional: linhas tracejadas -->
</svg>
```

- **Unidade:** milímetros. `width`/`height` declaram `mm` e o `viewBox` usa os mesmos
  números (1 unidade de usuário = 1 mm). Não há `transform` nem escala implícita.
- **Coordenadas:** origem no canto superior esquerdo, x para a direita, **y para baixo**.
  Conversão: `x_svg = x_projeto + dx`, `y_svg = y_projeto + dy`, com
  `dx = margem − x_mínimo_usado` (idem dy). É só uma **translação**; nenhuma medida
  muda. Valores com precisão de 1e-6 mm.
- **Ids estáveis:** `painel-base`, `painel-top`, `painel-front`, `painel-back`,
  `painel-left`, `painel-right`.
- **Contornos:** `M … L … Z`, fechados, com os mesmos vértices e a mesma ordem da geometria
  do projeto (dedos incluídos). Sem segmentos duplicados, nulos ou autointersectantes
  (validado antes de exportar; se falhar, o app mostra o erro e não grava).
- **Só vetorial simples:** `path`, `text`, `g`. Sem imagens, scripts, filtros, fontes
  externas ou `<style>`.
- **Camadas por grupo e por cor.** Cores padrão: corte `#FF0000`, identificações
  `#0000FF`, auxiliares `#00A000`. Não use a cor como única referência: use os ids dos grupos.
- **Operações:** o SVG **não** define potência, velocidade nem passadas.

## Kerf: sem compensação dupla

Se você informar **kerf > 0** no gerador, o caminho de corte já sai deslocado `kerf/2`
para fora (uma única vez, no motor). O exportador **só copia** esse caminho. Portanto,
**não aplique outro offset/kerf no LightBurn**. Com kerf = 0 nenhuma compensação existe e
você pode (se quiser) compensar no LightBurn. O `<desc>` do arquivo registra qual caso é.

## Importar no LightBurn

> Os nomes de menus abaixo são os usuais do LightBurn e podem variar por versão. Nada
> disto foi executado por mim: é o roteiro para **você** validar.

1. Abra o LightBurn com a Sculpfun S9 configurada e as unidades em **milímetros**.
2. **File → Import…** (ou Ctrl+I) e escolha o `.svg`.
3. Selecione tudo e olhe **largura × altura** nas propriedades da forma: devem bater com
   "Arquivo SVG: L × A mm" mostrado no app (a diferença esperada é só a margem).
4. Confira **cada painel**: selecione-o e compare largura/altura com a lista de peças do app
   (com kerf > 0, cada dimensão fica maior em exatamente o kerf).
5. Dê zoom nos dedos: devem estar completos, sem linhas duplicadas e sem contornos abertos.
6. Se o LightBurn mostrar o desenho com tamanho diferente do declarado, **pare**: use o
   teste de escala abaixo e verifique se a sua versão tem opção de DPI de importação de SVG.

## Teste de escala 100 × 100 mm

1. No gerador, clique em **Teste de escala 100×100** e salve (nome sugerido
   `teste_escala_100x100mm.svg`). O arquivo declara `width="100mm" height="100mm"`
   `viewBox="0 0 100 100"` e contém um quadrado exato de 100 mm.
2. Importe no LightBurn e leia a largura/altura do quadrado: devem ser **100,00 × 100,00 mm**.
3. Opcional, mais rigoroso: grave o quadrado numa sobra de MDF (com potência baixa ou só
   riscando) e **meça com régua/paquímetro**.
4. Se não der 100 mm, não corte o projeto: reporte o valor medido e a versão do LightBurn.

## Configurar as operações de corte

No LightBurn, cada **cor** vira uma camada. Faça assim:

- **Vermelho (`#FF0000`, corte):** modo **Line**; ajuste **velocidade, potência e nº de
  passadas** para o seu MDF e a sua S9.
- **Azul (identificações) e verde (auxiliares):** só existem se você os exportou. Não devem
  cortar: desligue a saída (Output) dessas camadas, use uma camada de ferramenta (se sua
  versão tiver) ou exclua-as antes de enviar.
- Confira a **ordem das peças** e o **ponto de origem/posição na mesa** antes de iniciar.

**Por que o app não define potência/velocidade/passadas:** o valor certo depende da
espessura e da densidade reais do MDF, da potência real do laser, do foco, da altura e
do estado da lente e do ar assistido. Um valor "garantido" no arquivo seria enganoso e
poderia causar corte incompleto ou queima.

## Checklist antes do primeiro corte

1. Medir a espessura **real** do MDF (paquímetro, vários pontos) e usar no app.
2. Rodar o **teste de escala 100×100** e confirmar 100 mm.
3. Fazer um **teste físico de encaixe** numa sobra: caixa pequena (ex.: 50×40×30 mm) com
   os mesmos kerf/folga. Montar e avaliar:
   - justo demais ou não entra → aumente a **folga** em passos de 0,05 a 0,1 mm;
   - frouxo/baila → reduza a folga;
   - medidas externas das peças fora do esperado → revise o **kerf** (e não compense duas vezes).
4. Só então cortar a chapa definitiva.

## O que cada tipo de teste cobre

| Verificação | Automatizada | LightBurn | Física |
|---|---|---|---|
| XML/SVG válido, estrutura, ids, grupos | Sim | — | — |
| `width`/`height` em mm = `viewBox`; sem `transform` | Sim | — | — |
| Coordenadas = geometria do projeto + translação | Sim | — | — |
| Contornos fechados, sem duplicados/autointerseção | Sim | — | — |
| Kerf aplicado uma única vez | Sim | — | — |
| Identificações/auxiliares fora do grupo de corte | Sim | — | — |
| Erros de gravação, sobrescrita, cancelamento | Sim | — | — |
| Renderização por parser independente (Qt) | Feita (manual, uma vez) | — | — |
| **Importação e escala reais no LightBurn** | **Não** | **Pendente (você)** | — |
| **Medidas reais após o corte (régua)** | Não | — | **Pendente (você)** |
| **Ajuste real dos encaixes** | Não | — | **Pendente (você)** |

## Limitações

- Sem validação no LightBurn e sem corte físico (veja a tabela).
- Disposição simples (sem otimização de chapa); o desenho não representa a chapa real.
- Só a caixa retangular exporta; os demais geradores ainda não existem.
- Identificações são texto SVG; o LightBurn pode importá-las como texto editável ou
  convertê-las, conforme a versão. Por isso ficam desligadas por padrão.
