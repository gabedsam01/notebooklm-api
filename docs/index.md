# notebooklm-api docs

## Visao geral

`notebooklm-api` e um projeto HTTP-first para operar NotebookLM com tres interfaces:

- API REST (FastAPI)
- CLI (`notebooklmapi`)
- UI web server-rendered (`/`)

O foco do projeto e oferecer operacao programatica previsivel para:

- criar/remover notebooks
- enviar fontes textuais
- gerar audio/video
- acompanhar jobs assincronos com logs detalhados
- manter catalogo local em SQLite sincronizado com a conta

## Arquitetura resumida

Fluxo de alto nivel:

1. Cliente (curl, n8n, UI, app interna) chama API/CLI.
2. Rotas em `app/api/routes/*` validam payloads (Pydantic).
3. Servicos em `app/services/*` executam regras de negocio.
4. Persistencia local:
   - notebooks em `data/notebooks.db`
   - jobs em `data/jobs/*.json`
   - artefatos em `data/artifacts`
5. Adapter NotebookLM (`real` ou `mock`) executa operacoes remotas.

Componentes principais:

- `app/main.py`: bootstrap, DI via `app.state`, roteadores e lifespan
- `app/services/notebooklm_service.py`: adapter `real`/`mock`
- `app/services/notebook_catalog_service.py`: sincronizacao conta <-> SQLite
- `app/services/job_service.py`: fila local por thread + pipeline de execucao
- `app/web/routes.py`: UI para operacao manual e debug

## Modos de execucao

### Modo real (padrao)

- Config: `NOTEBOOKLM_MODE=real`
- Requer storage state valido (`data/auth/storage_state.json`)
- Usa adapter de integracao com `notebooklm-py` (nao oficial)
- Ideal para operacao real

### Modo dev/mock

- Config: `NOTEBOOKLM_MODE=mock` ou `notebooklmapi start --dev`
- Nao depende de sessao real Google/NotebookLM
- Gera artefatos fake (WAV/MP4) para validar pipeline
- Ideal para desenvolvimento local, testes e CI

## Estrutura de documentacao

- [`docs/api.md`](./api.md): contratos HTTP, rotas, payloads, status codes, exemplos curl/n8n
- [`docs/cli.md`](./cli.md): comandos, comportamento, arquivos gerados e fluxo operacional
- [`docs/auth.md`](./auth.md): storage state, login assistido, `/auth/status`, seguranca
- [`docs/jobs.md`](./jobs.md): modelo de jobs, status, polling, logs, artefatos, limpeza
- [`docs/notebooks.md`](./notebooks.md): ciclo de vida de notebooks, SQLite e sincronizacao
- [`docs/ui.md`](./ui.md): uso da interface web, telas, debug e operacao diaria
- [`docs/docker.md`](./docker.md): build/run, volumes, persistencia, variaveis e notas para VPS
- [`docs/troubleshooting.md`](./troubleshooting.md): problemas comuns e correcoes praticas

## Comeco rapido

1. Rode `notebooklmapi setup`
2. Rode `notebooklmapi start` (ou `notebooklmapi start --dev`)
3. Verifique `GET /health`
4. Configure auth em `/auth/storage-state` (modo real)
5. Consulte `docs/api.md` para fluxos sync/async
