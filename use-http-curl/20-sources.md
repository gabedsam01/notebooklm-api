# 20. Adição de Fontes (Sources)

Após criar ou achar seu Notebook, você pode preenchê-lo com textos para alimentar a inteligência artificial do resumo. Você pode informar o alvo da fonte via UUID (`notebook_id`) ou via Chave Primária Interna SQLite (`local_id`).

## A. Inserção Simples
Adiciona apenas um texto de até 120 mil caracteres por vez.

### `POST /sources/text`
```bash
curl -X POST "http://127.0.0.1:8080/sources/text" \
     -H "Content-Type: application/json" \
     -d '{
  "local_id": 1,
  "title": "Primeiro Artigo de Teste",
  "content": "No início do ano de 2026, avanços em arquitetura LLM permitiram que..."
}'
```

**Resposta (`200 OK`)**:
```json
{
  "notebook_id": "f83b2a-...",
  "added_count": 1,
  "source_ids": []
}
```

---

## B. Inserção em Lote (Batch)
Se você estiver extraindo dezenas de páginas da Web simultaneamente em seu scraper, não sofoque a rede. Envie o vetor na mesma request.

> **Importante:** Se o conjunto JSON enviado for incrivelmente colossal e a requisição HTTP falhar com Payload Too Large, fracione manualmente do seu lado em blocos de no máximo 30 itens, pois existe limitação nativa nas chamadas HTTP. A API python em background possui limitação de chunk nativa para evitar ban do IP do Google, ou seja, se você mandar 100 itens aqui, ela enviará para a Cloud de 15 em 15.

### `POST /sources/batch`
```bash
curl -X POST "http://127.0.0.1:8080/sources/batch" \
     -H "Content-Type: application/json" \
     -d '{
  "local_id": 1,
  "sources": [
    {
      "title": "Capitulo 1",
      "content": "Conteudo macico numero um..."
    },
    {
      "title": "Capitulo 2",
      "content": "Conteudo macico numero dois..."
    }
  ]
}'
```

**Resposta (`200 OK`)**:
```json
{
  "notebook_id": "f83b2a-...",
  "added_count": 2,
  "source_ids": []
}
```
