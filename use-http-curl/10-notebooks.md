# 10. Operando Cadernos (Notebooks CRUD)

Exemplos de como lidar com os blocos mestre (Notebooks) tanto de forma independente quanto sincronizando com o que você já criou pela Interface do Usuário do Google via navegador.

## A. Sincronizando Cadernos Existentes
O seu celular ou laptop acessou o `notebooklm.google.com` e você criou um caderno lá? Avise sua API para que ela puxe o ID da nuvem para o Banco SQLite.

### `POST /notebooks/sync`
```bash
# Sincronização passiva não requer JSON Body
curl -X POST "http://127.0.0.1:8080/notebooks/sync"
```
**Resposta (`200 OK`)**:
```json
{
  "found_in_account": 2,
  "imported_count": 1,
  "stale_local_count": 0,
  "detail": "Sincronizacao concluida: 1 importados, 0 orfaos removidos."
}
```

---

## B. Listando seus Cadernos Locais
### `GET /notebooks`
```bash
curl -X GET "http://127.0.0.1:8080/notebooks"
```
**Resposta (`200 OK`)**:
```json
{
  "count": 1,
  "items": [
    {
      "local_id": 1,
      "notebook_id": "f83b2a-...",
      "title": "Anotações da API",
      "source_count": 0,
      "artifact_count": 0,
      "origin": "SYNC",
      "metadata": {},
      "created_at": "2026-04-18T10:00:00Z",
      "updated_at": "2026-04-18T10:00:00Z"
    }
  ]
}
```

---

## C. Criando um Novo Caderno Programaticamente
Irá bater na API do Google e depois registrar um ID local SQLite.

### `POST /notebooks`
```bash
curl -X POST "http://127.0.0.1:8080/notebooks" \
     -H "Content-Type: application/json" \
     -d '{"title": "Ciências da Computação"}'
```
**Resposta (`201 Created`)**:
```json
{
  "local_id": 2,
  "notebook_id": "ee513a90-...",
  "title": "Ciências da Computação",
  "source_count": 0,
  "artifact_count": 0,
  "origin": "API",
  "metadata": {},
  "created_at": "2026-04-18T10:05:00Z",
  "updated_at": "2026-04-18T10:05:00Z"
}
```

---

## D. Lendo um Notebook por ID (Refresh)
Atualiza a contagem de Sources atual indo buscar o valor mais recente no Google.
### `GET /notebooks/{notebook_id}`
```bash
# Note que a URI espera um ID longo nativo
curl -X GET "http://127.0.0.1:8080/notebooks/ee513a90-..."
```

---

## E. Apagando Cadernos

A API lhe dá duas conveniências: deletar informando o UUID difícil ou informar o int de autoincrement `local_id`.
Isso deletará a pasta do servidor do Google e sua referência Local.

### Apagando via UUID (`DELETE /notebooks/{id}`)
```bash
curl -X DELETE "http://127.0.0.1:8080/notebooks/ee513a90-..."
```

### Apagando via Local ID (`DELETE /notebooks/local/{id}`)
```bash
curl -X DELETE "http://127.0.0.1:8080/notebooks/local/2"
```

**Resposta (`200 OK`)**:
```json
{
  "status": "success",
  "notebook_id": "ee513a90-...",
  "local_id": 2,
  "deleted_remote": true,
  "deleted_local": true,
  "detail": "Notebook excluido do Google e do banco local."
}
```
