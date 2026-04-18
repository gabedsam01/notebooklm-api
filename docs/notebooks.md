# Catálogo de Cadernos & SQLite

Todos os Notebooks do Google que você gerenciar via API são espelhados em um pequeno banco relacional físico de persistência local para entregar altíssima disponibilidade em consultas, poupar tráfego HTTP repetitivo no NotebookLM e manter metadados estruturados (contagem de fontes e de artes geradas).

## 1. O Banco Local (SQLite)

Localizado por padrão no `data/notebooks.db`. A API cria as tabelas automaticamente se não existirem no startup da injeção no `NotebookCatalogService`.

### Entidade `NotebookRecord`
A entidade principal que navega no projeto. Ela é composta de dois identificadores importantes, explicados abaixo:

1. **`local_id`**: Integer Autoincrement criado unicamente no SQLite. Permite que o projeto funcione e crie relacionamentos rápidos.
2. **`notebook_id`**: O ID alfanumérico gigante nativo/oficial (UUID) atribuído pelo Backend do próprio Google no NotebookLM.
3. **`title`**: O nome.
4. **`source_count` e `artifact_count`**: Inteiros cacheados da quantidade de dados brutos que alimentam a LLM, e dados audiovisuais gerados.

**Diferença de Exclusão (Delete)**:
Os Endpoints da nossa API possuem a facilidade de aceitar remoções por qualquer um dos identificadores:
- `DELETE /notebooks/{notebook_id}`
- `DELETE /notebooks/local/{local_id}`
Ambas as formas acionam o script de deletar na Conta Real, e assim que houver retorno HTTP 200 do Google, um comando SQL cascateia e apaga os rastros e metadados locais na SQLite, mantendo os registros sempre higiênicos e sincronizados sem deixar resíduos orfãos.

---

## 2. A Operação Vital de `Sync`

Ao invés de carregar a estrutura local a todo momento ou reescrever banco (comportamentos perigosos), nossa API desenhou a ação de Sincronização.

Acionável através de:
- API Rest: `POST /notebooks/sync`
- CLI: `notebooklmapi list`

### Como funciona:
O `NotebookCatalogService.sync_from_account()` é quem rege as regras de Upsert e de Pruning (Limpeza de Órfãos).
Ele consome o Array mestre remoto de cadernos via web scraping (NotebookLMService) e, a partir de seu Snapshot oficial, opera comparações.
1. Se o `notebook_id` remoto existir e não tiver cadastro interno na `notebooks.db`, o sistema injeta um INSERT na tabela com a nova row, preenchendo as métricas nativas do Google.
2. Após salvar e atualizar campos que foram alterados via interface externa, a engine busca todos os IDs de banco onde o `notebook_id` foi excluído lá de fora. Ou seja, varre os UUIDs antigos abandonados na SQLite. Ao encontrar, emite comandos brutais SQL de `DELETE FROM`.
3. Essa técnica permite que, em uma eventual migração de VPS, você apenas arraste o diretório de dados `.json`, aplique o comando `sync`, e o catálogo volte instantaneamente reconstruído na SQLite.

---

## 3. As Fontes (Sources)

Documentos de base crua, PDFs (nesta aplicação suportado apenas texto) são categorizados nativamente e indexados pelo banco vetorial secreto do Google. 

Quando você envia o Payload no endpoint `POST /sources/text`, a API local simplesmente retransmite como Documento Nativo associado ao UUID do `notebook_id`. 

Note as proteções anti-limites que injetamos:
O Payload em `POST /sources/batch` entende a falha humana e quebra a lista nativa gigantesca JSON em pequenos lotes assíncronos no loop do python para não incorrer em erros `HTTP 413 Request Entity Too Large` que o Google devolve se o Header ultrapassar limites seguros do gateway web, o que inviabilizaria uploads maiores.
