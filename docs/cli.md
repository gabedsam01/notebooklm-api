# CLI guide

## Visao geral

O comando `notebooklmapi` e instalado pelo script entrypoint definido em `pyproject.toml`.

- comando principal: `notebooklmapi`
- funcao alvo: `app.cli:main`
- foco: setup rapido, controle de processo e operacoes de catalogo

## Como o comando e resolvido

Diferente de `npm -g`, o binario nao vira global automaticamente so por existir no projeto.

Voce pode usar em 3 modos:

1. venv ativado (`source .venv/bin/activate`)
2. chamar binario direto (`.venv/bin/notebooklmapi ...`)
3. instalar com `pipx` (global isolado)

## Comandos disponiveis

### `notebooklmapi setup`

Prepara ambiente local de forma idempotente:

- cria `.venv` se nao existir
- instala deps com `pip install -e .[dev]`
- cria `.env` a partir de `.env.example` se estiver ausente
- prepara diretorios de dados
- valida bootstrap da app (`from app.main import app`)

Exemplo:

```bash
notebooklmapi setup
```

### `notebooklmapi start`

Inicia API em background:

- host/porta efetivos: `0.0.0.0:8080`
- modo padrao: `NOTEBOOKLM_MODE=real`
- grava PID em `data/run/notebooklmapi.pid`
- grava log em `data/run/notebooklmapi.log`
- evita multiplas instancias quando PID ativo existe

Exemplo:

```bash
notebooklmapi start
```

### `notebooklmapi start --dev`

Mesmo fluxo de start, forcando backend mock:

- injeta `NOTEBOOKLM_MODE=mock` no processo filho
- ideal para desenvolvimento local sem sessao real

```bash
notebooklmapi start --dev
```

### `notebooklmapi off`

Desliga processo em background:

- le PID file
- envia `SIGTERM`
- fallback `SIGKILL` se necessario
- limpa PID file ao final

```bash
notebooklmapi off
```

### `notebooklmapi status`

Mostra estado atual:

- online/offline
- PID atual (quando online)
- endpoint esperado
- caminho do log

```bash
notebooklmapi status
```

### `notebooklmapi list`

Sincroniza e lista notebooks:

- consulta notebooks da conta NotebookLM
- compara com SQLite local
- importa notebooks faltantes no banco
- remove registros locais que sumiram da conta
- imprime resumo de sync e lista final

```bash
notebooklmapi list
```

Saida esperada (exemplo):

```text
[list] encontrados no Google: 3
[list] encontrados no banco: 2
[list] adicionados ao banco: 1
[list] removidos do banco: 0
[list] lista final:
  - local_id=1 notebook_id=nb-1 title=Notebook 1
```

Se o acesso remoto estiver indisponivel, o comando:

- retorna codigo de saida `1`
- informa indisponibilidade remota
- ainda imprime o estado local do SQLite

### `notebooklmapi list --dev`

Executa list/sync usando backend mock.

```bash
notebooklmapi list --dev
```

### `notebooklmapi delete <notebook_id>`

Remove notebook remoto/local em fluxo tolerante a falhas:

- tenta remover remoto quando existir
- remove registro local se presente
- imprime `deleted_remote`, `deleted_local` e detalhe textual

```bash
notebooklmapi delete <notebook_id>
```

## Arquivos e diretorios gerados/usados

Durante setup/start, a CLI trabalha com:

- `.venv/`
- `.env`
- `data/notebooks.db`
- `data/jobs/`
- `data/artifacts/`
- `data/tmp/`
- `data/auth/storage_state.json`
- `data/run/notebooklmapi.pid`
- `data/run/notebooklmapi.log`

## Codigos de saida (pratica)

- `0`: sucesso operacional
- `1`: erro de execucao ou indisponibilidade remota em fluxos como `list`

## Fluxo operacional recomendado

1. `notebooklmapi setup`
2. `notebooklmapi start` (ou `start --dev`)
3. `notebooklmapi status`
4. `notebooklmapi list`
5. usar API/UI conforme necessidade
6. `notebooklmapi off` ao encerrar

## Dicas de uso avancado

- a CLI resolve `project_root` automaticamente buscando `pyproject.toml` em diretorios pais
- para scripts CI/CD, prefira binario absoluto (`.venv/bin/notebooklmapi`)
- em ambiente sem `.venv`, `start` usa o `python` atual como fallback
