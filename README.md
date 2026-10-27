# MDF Studio

Aplicação desktop (Python + PySide6) para, nas próximas etapas, criar projetos
paramétricos em MDF (caixas, gavetas, organizadores, divisórias) e exportá-los
em **SVG** compatível com LightBurn / Sculpfun S9.

**Status: Etapa 03 — exportação SVG.** A **caixa retangular** com finger joints
está funcional (geometria, visualização 2D, disposição das peças) e agora **exporta
SVG em milímetros** para o LightBurn. Os demais geradores seguem "Em desenvolvimento".

- Gerador, convenções e limitações: [`docs/GERADOR_CAIXA.md`](docs/GERADOR_CAIXA.md)
- Exportação, importação no LightBurn e checklist de corte:
  [`docs/EXPORTACAO_SVG.md`](docs/EXPORTACAO_SVG.md)

Para usar: **Geradores → Caixa retangular**, preencha as medidas, clique em
**Gerar projeto** e depois em **Exportar SVG…**.

> **Importante:** a compatibilidade com o LightBurn e o ajuste físico dos encaixes
> **ainda não foram testados**. Rode o **teste de escala 100×100** e um corte de teste
> antes de usar uma chapa inteira. O SVG não define potência, velocidade nem passadas.

Funciona totalmente offline: sem nuvem, APIs externas ou contas.

## Requisitos

- Python 3.12 (ou outra versão estável compatível com PySide6)
- Windows, Linux ou macOS com ambiente gráfico

## Instalação

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Executar

```bash
python main.py
```

## Testes

```bash
python -m pytest
```

Os testes de interface usam `QT_QPA_PLATFORM=offscreen` e não precisam de monitor.

## Onde ficam as configurações

Em `settings.json` dentro do diretório de dados do usuário
(`QStandardPaths.AppDataLocation`), por exemplo:

- Windows: `%APPDATA%\MDFStudio\MDF Studio\settings.json`
- Linux: `~/.local/share/MDFStudio/MDF Studio/settings.json`

Se o arquivo não existir, estiver vazio ou com JSON inválido, os valores
padrão são carregados sem erro.

## Estrutura

```
main.py                     ponto de entrada
app/config.py               padrões e validação das configurações
app/storage/settings_store.py   leitura/gravação JSON (sem Qt na lógica)
app/core/                   motor geométrico (sem Qt): parâmetros, validação,
                            geometria, juntas, disposição, verificação 3D
app/generators/             gerador da caixa (orquestra validação+geometria+disposição)
app/export/                 exportador SVG (sem Qt; consome o layout já calculado)
app/ui/                     janela, páginas, tema e widgets
tests/                      pytest
```

A página da caixa (`app/ui/box_generator_page.py`) fica **dentro** de "Geradores",
com botão de voltar, para manter as 5 entradas do menu da Etapa 01.

## Empacotamento futuro (PyInstaller)

> Ainda **não foi gerado nem testado** nenhum executável.

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name "MDF Studio" main.py
```

O resultado ficaria em `dist/`. Valide em uma máquina limpa antes de distribuir.
