# NotebookLM API

A **NotebookLM API** é uma solução independente para operar o [NotebookLM do Google](https://notebooklm.google.com/) de forma programática (HTTP-first), oferecendo interfaces via **API REST (FastAPI)**, um utilitário **CLI (`notebooklmapi`)**, e uma **UI Web Server-rendered**.

Este projeto foi desenhado primariamente para possibilitar automações (n8n, curl, scripts customizados) extraindo dados e resumos multimodais de cadernos (notebooks) com previsibilidade, fila de processamento local, e um log minucioso para cada operação.

---

## 🚀 Principais Recursos

- **API FastAPI Extensível**: Rotas totalmente tipadas (via Pydantic) cobrindo notebooks, upload de fontes (únicas ou em lote), jobs, operações de IA (resumos em áudio e vídeo), e autenticação.
- **Fila Assíncrona e Logs Locais**: Geração de mídia (WAV/MP4) através de Jobs com sistema de pooling, acompanhamento em tempo real, fallback de descoberta de artefato e tratamento de tolerância a falhas.
- **Integração Real e Mock**: Modo `real` integrando-se via lib comunitária `notebooklm-py` ao Google e modo `mock` para testar fluxos no desenvolvimento sem bater em serviços externos.
- **Catálogo Offline Sincronizado**: Persistência de Notebooks em SQLite com referenciamento cruzado (ID local vs ID remoto).
- **UI de Observabilidade**: Visualizador web (HTMX + Jinja2) em tempo real da execução dos jobs, gerenciador de notebooks, e facilidade para "Baixar remoto".

---

## 🏗️ Arquitetura Resumida

O sistema obedece um padrão de Injeção de Dependências em FastAPI (`app.state`), permitindo um desacoplamento forte entre as camadas:

- **Roteadores HTTP (`app/api/routes` e `app/web/routes.py`)**: Validação de payload.
- **Serviços de Negócio (`app/services/*`)**:
  - `NotebookLMService`: Comunicação externa (`real` ou `mock`).
  - `JobService`: Pipeline assíncrono em *thread background*, fallback timeout, conversão para MP4/WAV.
  - `NotebookCatalogService`: Banco de dados SQLite, controle de órfãos, e sincronização `local_id`.
  - `StorageStateService`: Conversão e injeção do arquivo mágico (`storage_state.json`) de Auth.

---

## 🛠️ Instalação e Execução

### Pré-requisitos
- Python >= 3.11
- Gerenciador de pacote (como pip ou pipx)

### Instalando e Ligando
Recomendamos o uso com ambiente virtual ou `pipx`. O pacote fornece o comando CLI nativo `notebooklmapi`.

```bash
git clone https://github.com/gabedsam01/notebooklm-api.git
cd notebooklm-api

# 1. Cria o ambiente, instala dependências e inicializa arquivos base (como .env)
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# 2. Roda a configuração inicial (cria diretórios, base de dados SQLite)
notebooklmapi setup

# 3. Dá o start na API em background (Porta 8080)
notebooklmapi start
```

### Configurações Importantes (`.env`)
Após o setup, o `.env` gerado tem o essencial:
```ini
# Configuração base de acesso da API
APP_HOST=0.0.0.0
APP_PORT=8080

# Modo de integração: 'real' para integração com a conta do Google ou 'mock' para testes falsos
NOTEBOOKLM_MODE=real

# Locais de Arquivos
DATA_DIR=data
SQLITE_DB_PATH=data/notebooks.db
STORAGE_STATE_PATH=data/auth/storage_state.json

# Controle de Resiliência de Job
ARTIFACT_WAIT_TIMEOUT_SECONDS=1800
ARTIFACT_POLL_INTERVAL_SECONDS=15.0
```

---

## 💻 Visão Geral dos Comandos CLI

O aplicativo exporta o CLI interativo `notebooklmapi`. Ele controla o estado do daemon, listas, e integridade.

| Comando | Descrição |
| --- | --- |
| `notebooklmapi setup` | Valida Python, instala pacotes, inicializa `.env` e prepara pastas do sistema (`data/`). |
| `notebooklmapi start` | Lança a aplicação daemonizada usando uvicorn. Grava PID e envia saída para `.log`. |
| `notebooklmapi start --dev`| Lança a aplicação em modo Mock (força `NOTEBOOKLM_MODE=mock`). |
| `notebooklmapi status` | Informa se a aplicação está online, rodando em qual porta e em qual PID. |
| `notebooklmapi off` | Finaliza a aplicação via arquivo PID usando `SIGTERM` (e depois `SIGKILL` como fallback). |
| `notebooklmapi list` | Sincroniza e lista o catálogo de Notebooks (Remoto vs Local). Exibe orfãos deletados. |
| `notebooklmapi list --dev` | Lista o catálogo falso em modo mock para testes. |
| `notebooklmapi delete <id>`| Deleta um notebook de forma programática. Remove remoto e limpa registro local em cascata. |

---

## 🌐 Visão Geral da API REST

A API roda por padrão em `http://127.0.0.1:8080`.
Ela é focada na transição fluida entre fluxos Assíncronos (Jobs) ou Síncronos.

### Módulos (Grupos de Rotas)
1. **Auth (`/auth/*`)**: Gerenciamento do Storage State para login real no NotebookLM.
2. **Notebooks (`/notebooks/*`)**: Inclusão, Visualização e Deleção (por `local_id` ou `notebook_id`), e Sincronização em Lote (`/notebooks/sync`).
3. **Sources (`/sources/*`)**: Inclusão de textos isolados ou múltiplos (*batching* automático).
4. **Operations (`/operations/*`)**: Core principal. Aciona resumos com prompts (`/operations/audio-summary` e `/operations/video-summary`). Retornam 202 Async ou arquivo direto.
5. **Jobs (`/jobs/*`)**: Fila local persistida em JSON em disco para acompanhar a evolução de Operations, logs do que ocorre dentro das chamadas.
6. **Artifacts (`/artifacts/*`)**: Download final do aquivo MP4 / WAV concluído pelo Job.

> **💡 Dica:** Se `async=true` (padrão) nas operações, a API responde `HTTP 202 Accepted` e um ID de Job. O arquivo será criado no diretório `data/artifacts/` eventualmente. Se `async=false`, a chamada TCP da requisição fica aberta e só responde retornando o arquivo em buffer nativo.

---

## 📚 Documentação Exaustiva (Manual Oficial)

A API e suas especificidades superam a capacidade deste README. O projeto contém uma documentação modular conectada contendo as regras e capacidades atuais exatas:

- [Visão Geral & Índice](docs/index.md): Um sumário abrangente detalhando a arquitetura.
- [Referência Completa da API](docs/api.md): Todos os enums, modelos Pydantic, limitações de campos de Request e exemplos práticos para Postman ou Curl.
- [Ciclo de Vida de Jobs & Artefatos](docs/jobs.md): Como funciona o tracking em background, descoberta proativa (fallback), e download remoto.
- [Referência Autenticação](docs/auth.md): Entenda o `storage_state.json` exigido pela integração, cookies que importam e o assistente de Start/Complete.
- [Referência Notebooks & Fontes](docs/notebooks.md): Compreenda a diferença entre o `local_id` do banco e o ID nativo da API do Google.
- [Interface Gráfica (UI Web)](docs/ui.md): Um guia rápido sobre o visualizador de tempo real e logs expansíveis na root local `/`.
- [Referência CLI](docs/cli.md): Como o motor do `.venv` funciona atrás de cada comando e manipulação de PID.
- [Containers (Docker)](docs/docker.md): Como colocar para rodar no Docker e configurações recomendadas de segurança para deploy na VPS.
- [Guia de Troubleshooting](docs/troubleshooting.md): Como destrinchar o log, timeouts de job que estouraram, ou erros do `notebooklm-py` de autenticação.

---

## ⚠️ Limitações Conhecidas

- **Suporte Oficial**: O Google não possui uma API Rest pública para o NotebookLM. Esta aplicação provê e mapeia uma interface em cima do `notebooklm-py` através de extração de chamadas Playwright/cookies. É instável por natureza. Use cookies atualizados (`SID`, `HSID`, `SSID`, etc.).
- **Tamanho de Fontes**: Operações em `/sources/batch` dependem da tolerância da requisição HTTP. Fontes massivas darão erro 400.
- **Processamento Concorrente**: Diferentes de provedores serverless, os jobs são rodados em uma `ThreadPool` na máquina local para manter os metadados JSON do Job e sincronizar a persistência.
