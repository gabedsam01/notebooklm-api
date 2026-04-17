# Notebooks guide

## Conceitos principais

O projeto trabalha com dois identificadores:

- `notebook_id`: id remoto do NotebookLM
- `local_id`: id local (autoincremento SQLite)

Endpoints e servicos aceitam um ou outro em varias operacoes para facilitar integracao.

## Persistencia SQLite

Banco padrao:

- `data/notebooks.db`

Tabela `notebooks`:

- `id` (local_id)
- `notebook_id` (UNIQUE)
- `title`
- `source_count`
- `artifact_count`
- `origin` (`local_created` ou `imported_from_account`)
- `metadata_json`
- `created_at`
- `updated_at`

Camada responsavel:

- repositorio: `app/services/notebook_repository.py`
- catalogo/sync: `app/services/notebook_catalog_service.py`

## Fluxo de criacao

### API

`POST /notebooks`

1. cria notebook remoto
2. consulta metadados remotos
3. persiste/upsert no SQLite
4. retorna `NotebookResponse` com `notebook_id` + `local_id`

Exemplo:

```bash
curl -X POST http://127.0.0.1:8080/notebooks \
  -H "Content-Type: application/json" \
  -d '{"title":"Notebook de estudo"}'
```

### UI

Formulario "Criar notebook" em `/` chama `/web/notebooks/create`.

## Listagem local

`GET /notebooks` retorna apenas o catalogo persistido no SQLite.

Exemplo de resposta:

```json
{
  "count": 1,
  "items": [
    {
      "local_id": 7,
      "notebook_id": "nb_abc",
      "title": "Notebook de estudo",
      "source_count": 3,
      "artifact_count": 2,
      "origin": "local_created",
      "metadata": {},
      "created_at": "2026-04-17T11:12:00+00:00",
      "updated_at": "2026-04-17T11:18:00+00:00"
    }
  ]
}
```

## Sincronizacao local + remota

`POST /notebooks/sync` e `notebooklmapi list` seguem a mesma logica central:

1. buscar notebooks da conta remota
2. upsert local dos ids existentes na conta
3. identificar locais que nao existem mais remotamente
4. remover locais orfaos

Campos de retorno (`NotebookSyncResponse`):

- `found_in_account`
- `imported_count`
- `stale_local_count`
- `detail`

## Obter notebook especifico

`GET /notebooks/{notebook_id}`:

- tenta refresh remoto
- atualiza SQLite quando remoto disponivel
- se remoto nao existir, cai para registro local (se houver)
- `404` se ausente em ambos

## Delecao

### Por notebook_id

- API: `DELETE /notebooks/{notebook_id}`
- CLI: `notebooklmapi delete <notebook_id>`
- UI: botao "Deletar" na tabela

### Por local_id

- API: `DELETE /notebooks/local/{local_id}`

Resposta de delecao (`NotebookDeleteResultResponse`):

- `status`: `completed`, `completed_with_warnings` ou `failed`
- `deleted_remote`
- `deleted_local`
- `detail`

Exemplo:

```json
{
  "status": "completed_with_warnings",
  "notebook_id": "nb_abc",
  "local_id": 7,
  "deleted_remote": false,
  "deleted_local": true,
  "detail": "Notebook remoto ja estava ausente; Registro local removido"
}
```

## Fontes e resolucao de alvo

Para fontes (`/sources/text`, `/sources/batch`) e operacoes (`/operations/*`):

- informe `notebook_id` ou `local_id`
- validacao garante que ao menos um esteja presente
- internamente, `NotebookCatalogService.resolve_notebook_id(...)` converte para `notebook_id`

## Relacao com jobs e artefatos

- jobs de audio/video incrementam `artifact_count`
- atualizacao de `source_count` acontece apos mutacoes de fontes e refresh do notebook

## Boas praticas

- em automacao, prefira persistir `notebook_id` como chave externa
- use `local_id` para UX local (tabela UI, operacao manual)
- rode sync periodico para evitar drift entre conta e SQLite
- em caso de limpeza remota fora do sistema, rode `POST /notebooks/sync`
