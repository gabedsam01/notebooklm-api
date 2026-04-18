# 50. Resgatando o Artefato Gerado

Toda operação assíncrona da API culmina em um Arquivo Físico no disco do Backend da API em `data/artifacts/`.
Para não expor e rotear arquivos brutos, este Endpoint permite baixar diretamente a mídia pelo código do seu App Cliente, vinculada ao Hash (`job_id`).

### `GET /artifacts/{job_id}`
O comando abaixo intercepta a stream de bits via curl e salva no destino final.

```bash
curl -X GET "http://127.0.0.1:8080/artifacts/e30e1f7c-7a6c-482c-9d6a-..." \
     --output meu_download.wav
```

### Como lidar com os Códigos de Erro desta Rota
Não tente varrer a pasta nem deduzir os retornos; o Endpoint está fortemente mapeado.

- **`200 OK`**: O arquivo desceu e já está sendo escrito no seu HD (Ou RAM se você não usou `--output`).
- **`409 Conflict`**: Significa que o Job existe na tabela `jobs` do servidor, *MAS* o campo status não está `"completed"`. A API recusará que você baixe porque ela mesma ainda está num Worker Thread processando. Seu código em loop não deve quebrar aqui, deve apenas pausar a Thread por mais 15s e tentar rodar o curl de novo.
- **`404 Not Found`**: O Job não existe na base, ou o campo `artifact_path` ficou corrompido fisicamente. Mande seu client alertar falha ao invés de ficar retentando em loop, pois esse erro é permanente.
