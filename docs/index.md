# Guia e Arquitetura - NotebookLM API

A documentação da `notebooklm-api` foi idealizada como um manual de operações completo. Este documento serve como índice para aprofundamento nos módulos específicos, além de apresentar a arquitetura técnica da solução.

## Visão Estrutural

O projeto foi construído para encapsular a natureza "instável" de requisições de scraper da integração com o NotebookLM e envelopá-la em uma abstração programática previsível, orientada a status de Jobs Assíncronos.

Ao invés de simplesmente expor endpoints REST com respostas bloqueantes de vários minutos, o sistema opera utilizando:
- **Backend HTTP (FastAPI)** provendo portas `/jobs`, `/operations` com `HTTP 202 Accepted`.
- **Fila de Background (`JobService`)** para gerenciar threads isoladas e relatar o status a cada atualização ou erro.
- **Camada Persistente SQLite** com referências de `local_id` vs `notebook_id` do Google.
- **Fallback e Retentativas** para capturar URLs de arquivos gerados tardiamente pelo Google.

## Mapa do Manual

Navegue abaixo por cada pilar da solução baseando-se em sua responsabilidade técnica. Se você encontrar inconsistências, estas documentações mapeiam **exatamente** o que o código faz hoje.

1. **[Referência da API REST](api.md)**
   > Modelos Pydantic, Payload JSON, Endpoints `/auth`, `/jobs`, `/operations`, `/notebooks` e respostas HTTP.

2. **[Utilitário CLI (`notebooklmapi`)](cli.md)**
   > Gerenciamento do daemon, setup de ambiente, listas remotas e validações via linha de comando local.

3. **[Fluxo de Autenticação & Cookies](auth.md)**
   > Explica a dependência do `storage_state.json` (Playwright), extração de cookies e limitações do modo `real`.

4. **[Pipelines Assíncronos & Jobs](jobs.md)**
   > Polling local, ThreadPools, status de lifecycle, extração de título original do artefato e fluxo do Fallback de Timeout.

5. **[Modelagem de Cadernos & Fontes (Notebooks)](notebooks.md)**
   > Sync local de catálogo SQLite, relação de arquivos com contas remotas. Diferenças do Local ID e UUID Google.

6. **[Experiência de Usuário: UI Web](ui.md)**
   > O front-end em HTMX no `/` que usa renderizações Jinja2 para observar tempo real sem quebrar estado HTML.

7. **[Deploy e Contêineres (Docker)](docker.md)**
   > Mapeamento de volumes da `data/`, como segregar variáveis sensíveis e gerir permissões POSIX de runtime.

8. **[Solução de Problemas (Troubleshooting)](troubleshooting.md)**
   > Se o download retornou `409 Conflict`, o auth caiu, o cookie "SID" sumiu, ou o "job ID sumiu", veja esta seção de respostas.

## Arquitetura: Direcionamento do `app/`

Tudo se conecta na root FastAPI em `app/main.py`. As injeções passam pelos endpoints recebendo serviços pré-estanciados em `app.state`.

```text
app/
├── api/
│   └── routes/      <- Camada Web: Valida schemas Pydantic e aciona as funções core. (FastAPI APIRouter)
├── core/            <- Pydantic Settings, inicialização base e formato de log root.
├── models/          <- DTOs: Representações REST e validação restrita (Pydantic). Enumerações exatas do sistema.
├── services/        <- Lógica Pura (JobService, NotebookLMService, Catalog): Operações e persistência de dados.
├── templates/       <- Camada View: Componentes parciais Jinja2 (jobs_table, notebooks_table) consumidos pelo HTMX.
├── utils/           <- Funções Helpers estáticas (timers, file sanitize).
└── web/             <- Endpoints exclusivos HTML p/ consumo humano via Navegador.
```

## Como a aplicação opera?
1. Uma automação chama o `/operations/audio-summary?async=true` informando o ID do Notebook.
2. A camada da **API** traduz o JSON para `GenerateAudioSummaryJobRequest`.
3. Chama o **JobService** (injetado via `app.state`).
4. O `JobService` cria o Job em memória no disco `data/jobs/{id}.json` (em modo `queued`).
5. A Background Thread pega esse Job e muda para `running`, disparando requisições com a lib interna `notebooklm_service`.
6. O status remoto vira `waiting_remote`, enquanto o Job faz polling (`ARTIFACT_POLL_INTERVAL_SECONDS`) em busca de conclusão e salva tudo internamente (`.log` do job).
7. Se um timeout acontecer, a lógica de Fallback descobre o arquivo e efetua o download em `data/artifacts/`.
8. O status se torna `completed`.

Toda essa operação é visível simultaneamente se alguém abrir a **UI web**, graças aos parciais HTMX atualizando a leitura JSON do `JobService`.
