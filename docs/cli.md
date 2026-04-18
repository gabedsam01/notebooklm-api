# Interface de Linha de Comando (CLI)

O `notebooklm-api` expõe seu CLI como `notebooklmapi`.
Este comando é registrado através da configuração `project.scripts` do `pyproject.toml` (`notebooklmapi = "app.cli:main"`). 

O CLI funciona majoritariamente de forma agnóstica na raíz do projeto com suporte inteligente de busca de `pyproject.toml` em diretórios pais para localizar a raiz do workspace.

---

## Estrutura Global do CLI

A base do módulo reside em `app/cli.py`. O parser lida com os seguintes subcomandos:

### `notebooklmapi setup`
**Objetivo**: Validar ou realizar o bootstrap limpo da aplicação local.
**Fluxo do Código (`run_setup`)**:
1. Busca ou cria o ambiente virtual isolado Python na raiz (`.venv`).
2. Verifica binários válidos de Python e PIP.
3. Faz a instalação de dependências iterativa `pip install -e .[dev]` bloqueando checks remotos longos.
4. Espelha `.env.example` para `.env` (caso inexistente).
5. Prepara toda a infra de arquivos da constante de settings (folders `data/`, `data/auth/`, etc).
6. Valida boot (Importa o `main.py` e valida a propriedade Pydantic `app.title` para garantir sanity-check sem crashs no startup daemonizado).

### `notebooklmapi start`
**Objetivo**: Inicializar o daemon FastAPI HTTP Uvicorn desatrelado do shell.
**Argumentos**:
- `--dev`: Se anexado, força a variável `NOTEBOOKLM_MODE=mock`.
**Fluxo do Código (`run_start`)**:
1. Confere no disco se existe um Tracking PID vivo. (`data/run/notebooklmapi.pid`). 
2. Se houver e pertencer à API ativa, bloqueia a execução relatando *"aplicação já em execução"*.
3. Cria processo desatrelado utilizando Python `subprocess.Popen` atrelando o terminal ao logger file cego em `data/run/notebooklmapi.log`.
4. Inicia *Ping Backoff* na porta atrelada checando em `http://127.0.0.1:8080/health`. Se timeout for extrapolado (> 12 segs), encerra o processo abortado e limpa cache. Se OK, escreve PID File e avisa o sucesso do `start`.

### `notebooklmapi status`
**Objetivo**: Checar integridade sem travar o process pipeline.
**Fluxo do Código (`run_status`)**:
- Verifica `pid_file`. Executa instrução `os.kill(pid, 0)` do OS para garantir a persistência. Retorna os dados do Log em disco e do URI Web caso "Online".

### `notebooklmapi off`
**Objetivo**: O encerramento cirúrgico (Graceful Shutdown) da camada Uvicorn.
**Fluxo do Código (`run_off`)**:
- Se processo estiver listado em `notebooklmapi.pid`: envia um sinal limpo via `os.kill(pid, signal.SIGTERM)`. 
- Executa loop aguardando por 8.0 segundos.
- Caso o processo ainda esteja segurando portas nativas TCP: invoca `signal.SIGKILL` limpando de maneira forçada o lock, exclui o pidfile e limpa cache.

### `notebooklmapi list`
**Objetivo**: Sincronizar catálogo da nuvem Google diretamente pelo terminal.
**Argumentos**:
- `--dev`: Opera a listagem ignorando HTTP reais.
**Fluxo do Código (`run_list`)**:
- Instancia e chama o `NotebookCatalogService`.
- Sincroniza estado de autorização atual (se o storage state é inválido, recusa e lista apenas itens que já estiverem salvos no Banco SQLite).
- Varre o UUIDs do cloud vs local. Adiciona faltantes na SQLite.
- Poda (Pruning): Remove dados locais onde `notebook_id` deixou de existir.
- Imprime contadores finais (Encontrados no Google, No Banco, Adicionados e Removidos).

### `notebooklmapi delete <notebook_id>`
**Objetivo**: Deleção unificada nativa.
**Fluxo do Código (`run_delete`)**:
1. Exclui a entidade remota (caso logado).
2. Se bem-sucedido ou falho no remoto, avança para tentar limpar o respectivo `notebook_id` de dentro do Storage SQLite local.
3. Mostra output formatado com `deleted_remote` booleano e explicações por detalhe de log na tela.

---

## Dependência de Local de Execução
Em virtude da leitura da flag do `Path`, você não deve isolar o script em `.venv/bin/` sem a referência raiz atrelada, por isso utilizamos as execuções recomendadas no documento principal (`README.md`).
