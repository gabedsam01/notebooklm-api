# Autenticação e Autorização com NotebookLM

> 💡 **Exemplos Práticos Disponíveis:** Para ver os payloads de Login Assistido e Storage State, veja os exemplos práticos em [curl](../use-http-curl/) e [Python](../use-python/).

A API usa a biblioteca [`notebooklm-py`](https://github.com/nclv/notebooklm-py) que interage não-oficialmente com as páginas do Google. Por este motivo, não existem "Tokens de API". Todo o funcionamento real baseia-se na emulação de cookies capturados de um navegador através do formato padrão do **Playwright** (`storage_state.json`).

---

## Modos de Operação

### Modo `mock`
No modo Mock (acionado via `.env` `NOTEBOOKLM_MODE=mock` ou CLI com a flag `--dev`), **todas as regras de autenticação são ignoradas**. Operações e deleções não consultam o Google. Útil estritamente para testes de front-end ou design da aplicação que consumirá esta API.

### Modo `real` (Produção)
Ativado por padrão. Ele **exige fortemente** a presença de um `storage_state.json` válido para não responder com Erros e Bloqueios.

---

## 1. O Arquivo de Sessão (`storage_state.json`)

O arquivo reside fisicamente em `data/auth/storage_state.json` com permissão de uso restrita (pois garante o controle total da conta do Google atrelada aos cookies).

O NotebookLM exige a injeção dos cookies de autenticação válidos da sua conta, comumente encabeçados pelos cookies obrigatórios:
- `SID`, `HSID`, `SSID`, `APISID`, `SAPISID`
- Preferencialmente exportando de um domínio de navegação da `.google.com`.

### Diferenças da API vs Lib Nativa
A biblioteca oficial `notebooklm-py` busca o `storage_state.json` lendo da home do usuário linux/mac (`~/.notebooklm/storage_state.json`). **Nós burlamos isso**.

O `app/main.py` sincroniza e força a variável de ambiente do sistema `$NOTEBOOKLM_HOME` a apontar na inicialização para a pasta `data/auth`. Isso garante que as operações de Downloads da própria biblioteca apontem com precisão para nosso repositório sem falhas silenciosas.

---

## 2. Fluxo de Configuração da Autenticação

Em vez de manipular o arquivo json manualmente, recomendamos fortemente o uso da nossa API para configurar e salvar o seu perfil.

Existem duas abordagens: **Injeção via Estado Bruto (Headless)** ou o **Assistente de Login (Playwright)**.

### Abordagem A: Injeção do Estado (`POST /auth/storage-state`)
Útil caso você possua uma extensão do navegador que exporte a sessão atual inteira para formato JSON.

A nossa API de injeção exposta em `POST /auth/storage-state` entende o formato padrão e **normaliza-o** instantaneamente pro formato exigido pelo Playwright (mesclando domínios, atributos estritos e origins).

### Abordagem B: Login Assistido
Se a injeção não for viável, a aplicação possui o Assistente Interativo.

1. Chame **`POST /auth/login/start`**. Isso abrirá de forma escondida uma janela de navegador pela própria API aguardando inserção de credenciais. A resposta do terminal ou UI vai exigir input e interação.
2. Siga as instruções do Google.
3. Chame **`POST /auth/login/complete`**. A API confirmará se a sessão logou, exportará o cookie de trás dos panos com segurança e trancará o gerador do arquivo criando o seu `storage_state.json`.

---

## 3. Checagem de Saúde da Conta (`GET /auth/status`)

O endpoint foi idealizado para ser o semáforo verde de integrações da sua empresa.

Ele retorna se a persistência visualizou ou não o arquivo de Cookies, mas **mais importante**, testa uma requisição real de ping `verify_access()` à conta para ver se a mesma continua aceitando chamadas. 
Se os cookies vencerem por decaimento normal do Google, `notebooklm_access_ok` ficará `false` em segundos, barrando imediatamente chamadas de resumos para precaver exceptions inesperadas de timeout de auth.

**Ações Sugeridas caso ocorra bloqueio de sessão (`false`)**:
- Limpar o Storage State antigo (deleção manual de arquivo).
- Re-injetar novos cookies frescos da sua sessão atual.
