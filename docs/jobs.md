# Jobs Assíncronos & Fila de Processamento

Dado que a geração de resumos em Inteligência Artificial requer frequentemente de 3 a 10 minutos no serviço do Google, o `notebooklm-api` possui uma camada nativa de gerenciamento de background baseada na classe interna `JobService`.

Todo o fluxo que passa um `async=true` retornará um Código **HTTP 202** instanciando um Tracking ID persistente (O identificador do Job).

---

## 1. O Ciclo de Vida do Job (State Machine)

Jobs são representados na memória de disco (`data/jobs/{job_id}.json`) pelo enum `JobStatus`.

1. **`queued`**: A solicitação foi computada e foi listada para ser enviada na próxima Thread da Pool de workers (`ThreadPoolExecutor`).
2. **`running`**: O Worker engajou no request e está operando comunicação com as funções internas síncronas de Python/Scraping.
3. **`waiting_remote`**: A ordem de gerar áudio/vídeo já foi entregue ao servidor do Google e a API agora está em *Polling* agressivo na nuvem consultando por atualizações. 
4. **`completed`**: O arquivo final foi gerado, baixado para a máquina do Gateway (`data/artifacts/`) e o rastreio terminou.
5. **`failed`**: A API local crachou, o processo sofreu um erro não tratado ou a Thread perdeu integridade. O campo `.error` conterá o trace final da stack.
6. **`timed_out`**: A contagem final superou a tolerância em segundos estipulada no `.env`. 

---

## 2. A Camada de Polling e a Rede de Segurança (Fallback)

Ao cair em estado `waiting_remote`, o `JobService` passa a perguntar ao servidor do Google a cada `ARTIFACT_POLL_INTERVAL_SECONDS` pelo status. 

### O Problema do Timeout Falso
Existem casos relatados e observados na API do Google onde a geração chega a 100%, o artefato é liberado na visualização, mas a requisição de polling se perde num limbo, mantendo o processo refém até explodir o `TimeoutError` limitador de segurança configurado (Padrão 30 minutos).

### O Método Fallback
Esta API está vacinada contra Timeout Falsos. Ao explodir o Timeout na thread de Worker, a aplicação invoca a mecânica de `_find_ready_artifact_fallback`.
1. A API faz uma listagem forçada não de status, mas do diretório real da sua conta no NotebookLM (`list_artifacts`).
2. Ela varre buscando por um artefato de formato congruente (Áudio/Vídeo) com estado flag `is_completed=True`.
3. Se o artefato mais recente de data corresponder a uma geração bem sucedida do backend ignorado, a API sequestra ele pro Job pendente, efetua o download físico e consolida a vitória em estado `completed` forçadamente.

---

## 3. Logs de Tracking Detalhado Interno

O arquivo não fica vazio durante o processamento. Diferente de sistemas blockbox, há a inclusão estruturada em `job.logs`.
Considere inspecionar o Job e exibir o campo `logs` nas suas aplicações front-end:

```json
"logs": [
  { "at": "2026-04-18T10:00:01Z", "stage": "gerar_audio", "message": "Enviando comando..." },
  { "at": "2026-04-18T10:00:04Z", "stage": "waiting_remote", "message": "status remoto: RUNNING" },
  { "at": "2026-04-18T10:01:04Z", "stage": "waiting_remote", "message": "status remoto: GENERATING_AUDIO" },
  { "at": "2026-04-18T10:02:04Z", "stage": "download", "message": "artefato de audio disponivel" }
]
```
Essas linhas reportam a fase de geração, falhas e polling a cada verificação.

---

## 4. O Comportamento de Download Síncrono Tardio

Antigamente, se você perdesse o rastreio da API ou abrisse sua conta em um computador físico, os dados e artes geradas sumiriam do radar da API para o resto da vida pois não possuiriam um "Job atrelado".

A API dispõe da funcionalidade de **Importação Tardelada de Artefatos**. Ao acionar um evento de sync da conta (`POST /notebooks/sync`), além de varrer notebooks ausentes:
1. O backend navega iterativamente pelo catálogo nativo do Google lendo todos os Mídia arquivos contidos.
2. É criado no disco rígido local, `JobRecords` inteiros com a flag `completed` sintetizados, de trás para frente.
3. Isso habilita o que definimos como **"Baixar remoto"** na UI Web. A integração `trigger_artifact_download` permite iniciar um `asyncio.create_task` solto em background para pegar esse velho ID atrelado sem necessitar de recriar gerações completas.

---

## 5. Extração Honesta de Metadados e Arquivos

Quando os arquivos são finalizados e guardados em `data/artifacts/`, a API usa a inteligência de recuperação de metadado na origem do pacote HTTP. 

Ela ignora preenchimento de Job UUID e, ao invés disso, aplica Sanitização Regex, gravando o Mídia file em HD nativamente com o exato `.title` customizado originado pela AI baseada no resumo, produzindo nomes como: `Resumo_Fisica_Quantica.mp4`.
