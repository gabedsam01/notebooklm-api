# Solução de Problemas (Troubleshooting)

Este guia concentra os cenários adversos mais recorrentes e como interpretar a observabilidade da API para resgatá-la da paralisação.

---

## 1. Auth & Cookies (`401 Unauthorized` / Falha Seca)

**Sintoma:** O endpoint `GET /auth/status` subitamente retorna `"notebooklm_access_ok": false` ou você recebe Exceptions gigantes no Python de Playwright informando que o seletor `document.body` não existe na página do Google.

**A Causa:** O Google expira sessões. Trocas de Wi-Fi corporativas, IP ou tempo puro invalidam os cookies cruciais (SID, HSID, SSID).
**A Solução:**
1. Execute o comando `notebooklmapi delete-auth` (se criado) ou remova fisicamente o arquivo `data/auth/storage_state.json`.
2. Em um navegador com aba anônima da sua máquina pessoal, faça login no Google.
3. Use uma extensão como *EditThisCookie* ou *Cookie-Editor* para exportar os cookies em formato JSON.
4. Jogue o array na rota `POST /auth/storage-state`. O serviço normalizará e salvará limpo de volta no local.

---

## 2. Falhas no Job: Limite de Tempo Estourou (`timed_out`)

**Sintoma:** Um Request em `/operations` ficou em `waiting_remote` por horas e logo virou `timed_out`. O arquivo não apareceu.
**A Causa:** As APIs de Front-end do NotebookLM sofrem desconexões silenciosas com web sockets. A geração concluiu lá no servidor nativo, mas a API não percebeu.
**A Solução Automática (Já implementada):**
A API conta com um Fallback. Ao explodir o timeout (padrão em `.env` -> `ARTIFACT_WAIT_TIMEOUT_SECONDS=1800`), ela consulta por fora a raiz do Notebook. Se o arquivo estiver lá, ela sequestra ele.

**Se mesmo o Fallback falhar:**
Isso indica que o Google falhou ao gerar o vídeo ou áudio do lado dele, muitas vezes por conta das fontes que você injetou. O Job local morre em segurança e você precisará lançar outro.

---

## 3. O Famoso `HTTP 409 Conflict` (Artefato Pendente)

**Sintoma:** A requisição em `/artifacts/{job_id}` retorna Status Code 409 ao invés de devolver o MP4/WAV.
**A Causa:** Você tentou efetuar o Download físico de uma requisição que foi aprovada e criada (portanto, não é `404 Not Found`), mas o estado dela contido em disco ainda é `queued`, `running` ou `waiting_remote`.
**A Solução:** O design da nossa API não permite travar o binário para não bloquear conexões TCP da sua interface. Respeite o `HTTP 409`, adicione um `sleep(5)` no seu Worker e tente realizar a rota de novo até retornar `200`.

---

## 4. O Catálogo Local Descolou do Real (Notebooks sumindo)

**Sintoma:** O `GET /notebooks` local retorna 5 arquivos. Você loga no browser do Google, existem 15 notebooks lá. Alguns da API dão erro ao serem manipulados.
**A Causa:** Você operou cadernos manualmente no browser alterando a realidade em que o banco SQLite (`data/notebooks.db`) acreditava estar.
**A Solução:**
- Via API: Envie um payload limpo (sem corpo) para `POST /notebooks/sync`.
- Via Terminal: Rode `notebooklmapi list`.
Ambas as instruções dizem pro `NotebookCatalogService` puxar todos UUIDs reais, criar os novos localmente e destruir os locais que não existem mais lá no servidor, limpando órfãos.

---

## 5. Permissões de Criação de Arquivos em Deploy Linux

**Sintoma:** Exceções do tipo `PermissionError: [Errno 13] Permission denied: 'data/jobs/xxxx.json'` ao realizar o primeiro envio REST da aplicação num servidor de Nuvem Ubuntu rodando Docker.
**A Causa:** O usuário contido na Imagem OCI (root ou appuser) difere do usuário que criou o diretório hospedado `data/` via `bind-mount`.
**A Solução Rápida:**
Acesse o diretório do root do `docker-compose.yml` e execute:
`sudo chmod 777 -R ./data`
**A Solução Profissional:** Descubra o UID do python da imagem e faça `chown` na pasta mapeada.
