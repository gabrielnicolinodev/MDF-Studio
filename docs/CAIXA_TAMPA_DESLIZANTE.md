# Caixa com tampa deslizante (Etapa 04)

> **Status de validação.** Geometria verificada por testes automatizados (incluindo uma
> verificação 3D da montagem). **Nenhum corte físico foi feito com este modelo.** O SVG usa o
> mesmo exportador da caixa retangular, que o autor do projeto relatou ter conferido no
> LightBurn (medidas e encaixes); o **deslizamento real da tampa ainda precisa de um corte de
> teste**.

## Como funciona

A caixa tem **6 peças**: fundo, frente, traseira, lateral esquerda, lateral direita e tampa.
Só há cortes vazados 2D (não existe ranhura "cega" no corte a laser), então a guia é um
**rasgo vazado** nas laterais:

```
        trilho  (altura r)  ──────────────────────────┐   preso ao corpo
  ┌───────────────────────────────────────────────────┤   pela PONTE traseira
  │  canaleta (altura t + c): rasgo vazado, aberto    │   (largura s)
  │  na aresta da FRENTE  ─────────────────────────── ┤
  └─ corpo da lateral (piso da canaleta = topo da frente)
```

- **Entrada:** a tampa entra pela **frente**, passa por cima da frente baixa e desliza nas
  canaletas até o batente traseiro. Para fora, desliza livremente.
- **Presa na vertical:** o trilho (acima) e o corpo da lateral (abaixo) prendem as orelhas da
  tampa; ela não pode ser levantada, só deslizada para a frente.
- **Não é uma tampa apoiada:** as orelhas correm *dentro* dos rasgos das laterais.

## Peças e recortes

| Peça | Dimensões | O que tem de especial |
|---|---|---|
| Fundo | W × D | igual à caixa retangular (finger joints nas 4 bordas) |
| Traseira | W × H | igual à caixa aberta; altura total |
| Frente | W × zf | **mais baixa** (zf = H − r − t − c); topo liso = piso da canaleta |
| Lateral (×2) | D × H | **rasgo da canaleta** (y de 0 a ys, z de zf a zf + t + c), aberto na frente |
| Tampa | (W − c) × L | **orelhas** e **recortes nos cantos traseiros** para passar pela ponte |

Fórmulas (W, D, H externas; t espessura; c folga da tampa; r trilho; s batente):

- `zf = H − r − t − c`, `ys = D − t − s`, canaleta de altura `t + c`.
- Tampa: largura `W − c`; comprimento máximo `D − t − c`; orelhas de comprimento
  `ys − c`; plano em z de `zf + c/2` até `zf + c/2 + t`.
- Folgas: vertical total da tampa = `c` (`c/2` acima e abaixo), lateral = `c/2` por lado,
  `c` até o batente. A ponte centraliza a tampa fechada.

## Parâmetros

| Parâmetro | Significado | Limites / padrão |
|---|---|---|
| Largura, Profundidade | externas ou internas (como na caixa retangular) | 5 a 1000 mm |
| **Altura** | modo externo: altura total das **laterais**; modo interno: altura livre do topo da base até o **piso da canaleta** | 5 a 1000 mm; padrão 60 |
| Espessura | espessura **real** medida do MDF | 1 a 25 mm |
| Dedos | automático ou nº ímpar de segmentos por junta | 3 a 99 |
| Folga de montagem | folga dos finger joints (a mesma da caixa retangular) | 0 a 1 mm |
| Kerf | compensação do corte (0 = desligado) | 0 a 0,6 mm |
| **Folga da tampa** | folga de deslizamento; deve ser **menor que a espessura** | 0,05 a 1,5 mm; padrão 0,3 |
| **Comprimento da tampa** | "auto" = máximo; ou um valor menor | 5 a 1000 mm |
| **Altura do trilho** | material acima da canaleta; "auto" = 2 × espessura | ≥ espessura, até 50 mm |
| **Batente traseiro** | ponte que prende o trilho e para a tampa; "auto" = 2 × espessura | ≥ espessura, até 50 mm |

Folga de montagem, folga da tampa e kerf são **três grandezas independentes**. Com tampa
mais curta que o máximo, o app avisa que sobra uma abertura nos fundos.

Entradas inviáveis são **rejeitadas com mensagem**, nunca "corrigidas": altura que deixe a
frente baixa demais para as juntas, canaleta com menos de 10 mm, tampa maior que a caixa,
folga da tampa maior que a espessura etc.

## Kerf e exportação SVG

O kerf funciona como na caixa retangular: o contorno nominal nunca muda e o caminho de corte
sai deslocado `kerf/2` para fora, **uma única vez**. Isso estreita a canaleta no caminho de
corte (o laser alarga de volta ao valor nominal). O exportador é o mesmo e **não foi alterado**:
o SVG tem em mm `width`/`height`/`viewBox` coerentes, um caminho fechado por peça
(`painel-base`, `painel-front`, `painel-back`, `painel-left`, `painel-right` e `painel-top`,
que é a **tampa**) e a mesma geometria da prévia. Veja `docs/EXPORTACAO_SVG.md`.

## Teste físico recomendado antes da chapa inteira

1. Meça a espessura real do MDF (paquímetro, vários pontos).
2. Corte uma **caixa pequena** (ex.: 60 × 50 × 45 mm) com o mesmo kerf e folgas.
3. Confira se a tampa entra pela frente e desliza até o batente sem forçar.
4. Tampa travando: aumente a **folga da tampa** em passos de 0,1 mm. Tampa frouxa: reduza.
5. MDF incha com umidade: deixe alguma folga; cera ou parafina nos trilhos ajuda.
6. Confira a firmeza do trilho (peça fina em balanço): se flexionar, aumente a **altura do trilho**.

## Limitações conhecidas

- **Sem corte físico:** o deslizamento real da tampa não foi testado.
- **Folga lateral enquanto desliza:** como o rasgo é vazado (não existe ranhura cega em 2D),
  a tampa é guiada na vertical pelo trilho e pelo corpo da lateral, mas tem folga lateral
  enquanto desliza. Fechada, a ponte a centraliza (`c/2` de cada lado).
- **Rasgo visível por fora:** a borda da tampa aparece no rasgo das laterais.
- **Trilho em balanço:** o trilho é uma tira fina presa só pela ponte traseira; no MDF fino
  pode ser frágil (o app avisa abaixo de 2 × a espessura).
- **Sem trava na frente:** a tampa sai por inteiro pela frente (não há trava de retenção).
- **Disposição simples,** sem otimização de chapa; o desenho não representa a chapa real.
- O catálogo mantém "Caixa com tampa" (removível/articulada) como **em desenvolvimento**:
  é outro modelo.
