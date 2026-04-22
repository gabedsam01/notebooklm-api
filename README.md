# NotebookLM API

A **NotebookLM API** é uma solução independente para operar o [NotebookLM do Google](https://notebooklm.google.com/) de forma programática (HTTP-first), oferecendo interfaces via **API REST (FastAPI)**, um utilitário **CLI (`notebooklmapi`)**, e uma **UI Web Server-rendered**.

## Novidade: arquitetura multi-account

O projeto agora suporta **múltiplas contas NotebookLM/Google** com isolamento por conta.

### Estrutura por conta

```text
data/
  auth/storage_state.json          # conta default / compatibilidade retroativa
  accounts/
    acc_xxx/
      meta.json
      storage_state.json
      chrome-profile/
```

### Capacidades principais

- múltiplas contas com `account_id`
- conta default para compatibilidade com rotas antigas
- seleção por header `X-NotebookLM-Account-Id`
- `storage_state.json` isolado por conta
- status por conta (`healthy`, `warming`, `degraded`, `challenge_required`, `expired`, `disabled`)
- verificação/refresh best-effort por conta
- lock global para downloads reais quando `notebooklm-py` depende de `NOTEBOOKLM_HOME`

### Novos endpoints

- `POST /accounts`
- `GET /accounts`
- `GET /accounts/{account_id}`
- `GET /accounts/{account_id}/status`
- `POST /accounts/{account_id}/bootstrap`
- `POST /accounts/{account_id}/verify`
- `POST /accounts/{account_id}/refresh`
- `POST /accounts/{account_id}/disable`
- `POST /accounts/{account_id}/enable`

### Como selecionar conta

Por padrão, a API usa a conta `default`.

Para escolher outra conta em qualquer rota relevante, envie:

```http
X-NotebookLM-Account-Id: acc_xxx
```

### Limitação real importante

A solução melhora bastante o isolamento, mas **não garante sessão eterna**. O NotebookLM continua dependendo de sessão web/cookies do Google. Se o Google invalidar a sessão ou exigir challenge/2FA novamente, será necessário renovar a autenticação da conta.

### Concorrência e `NOTEBOOKLM_HOME`

A biblioteca `notebooklm-py` ainda usa `NOTEBOOKLM_HOME` em partes do fluxo de download. Por isso, downloads reais usam um **lock global** para evitar vazamento de autenticação entre contas concorrentes no mesmo processo.
