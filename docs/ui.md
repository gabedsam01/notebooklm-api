# UI guide

## Visao geral

A interface web em `GET /` e uma console operacional para:

- importar storage state
- criar/sincronizar/remover notebooks
- adicionar fontes (unica e lote)
- criar jobs de audio/video
- monitorar jobs, logs, resultado e download de artefatos

Stack de UI:

- Jinja2 (server-rendered)
- HTMX (interacoes sem SPA)
- Tailwind CSS

Arquivos principais:

- rotas web: `app/web/routes.py`
- templates: `app/templates/index.html` e `app/templates/partials/*`
- estilo: `app/static/styles.css`

## Como acessar

1. iniciar API: `notebooklmapi start`
2. abrir `http://127.0.0.1:8080/`

## Secoes da tela

### 1) Auth status

No topo, a UI mostra:

- estado atual (`Conectado`, `Configurado` ou `Pendente`)
- contagem de cookies quando disponivel
- detalhe retornado por `/auth/status`

### 2) Importar Storage State

Formulario com JSON de storage state. Pode ser o objeto Playwright completo ou apenas um array JSON bruto de cookies (que sera convertido automaticamente).

- endpoint interno: `POST /web/auth/storage-state`
- retorno em card de resultado com status/tempo e refresh automatico da pagina para atualizar o status no topo.

### 3) Criar notebook e sincronizar

- criar: `POST /web/notebooks/create`
- sync conta->SQLite: `POST /web/notebooks/sync`

### 4) Fontes

- fonte unica: `POST /web/sources/text`
- lote JSON: `POST /web/sources/batch`

Ambos aceitam `notebook_id` ou `local_id`.

### 5) Jobs de audio e video

- audio: `POST /web/jobs/audio`
- video: `POST /web/jobs/video`

Criacao e assincrona. A UI mostra `job_id` imediatamente.

### 6) Painel de resultado de acoes

Area `#action-result` recebe respostas HTML parciais (cards):

- sucesso/erro
- mensagem de retorno
- payload de detalhes em JSON
- tempo de execucao da acao

### 7) Tabela de notebooks

- render parcial: `partials/notebooks_table.html`
- refresh automatico: `every 5s`
- acao de delecao com confirmacao HTMX

Colunas:

- `local_id`
- `notebook_id`
- titulo
- source_count
- artifact_count
- origem
- acoes

### 8) Tabela de jobs com debug

- render parcial: `partials/jobs_table.html`
- refresh automatico: `every 3s`
- filtro por `job_id` e `name`

Para cada job, a UI mostra:

- status (`queued`, `running`, `completed`, `failed`)
- notebook alvo
- duracao
- link de download (quando existe artefato)
- bloco expansivel com logs por etapa e resultado JSON

## Downloads e artefatos

Quando `artifact_path` existe no job, a tabela exibe link:

- `GET /artifacts/{job_id}`

Se o arquivo nao estiver pronto, o endpoint devolve erro (ex.: `409`).

## Fluxo recomendado de uso (operacao manual)

1. importar storage state
2. criar notebook ou sincronizar conta
3. adicionar fontes
4. iniciar job de audio/video
5. acompanhar status em jobs
6. baixar artefato

## Logs e debug pratico

Para investigar falhas:

1. abrir detalhes do job
2. checar `stage` e `message` em ordem temporal
3. revisar `result` ou `error`
4. validar auth no topo da pagina

## Limitacoes atuais

- sem autenticacao propria da UI (uso operacional local/rede confiavel)
- sem pagina de historico paginada (carrega ultimos registros)
- sem upload de arquivo binario de fonte (foco em texto)

Para operacao em producao, considere proteger acesso por proxy reverso/autenticacao externa.
