# 04. Assistente de Login Playwright (Início)

Abre o Chromium injetado do próprio Servidor da API e atrela uma sessão que durará por um curto tempo na memória até que o humano preencha usuário/senha/2fa.

### O Comando (`POST /auth/login/start`)
```bash
curl -X POST "http://127.0.0.1:8080/auth/login/start"
```

### Resposta JSON Esperada
A API devolve um ID Único de sessão que você deve armazenar numa variável para fazer o encadeamento do "passo 2".

```json
{
  "session_id": "8a91fbc2",
  "expires_at": "2026-04-18T10:35:00Z",
  "detail": "Navegador aberto. Conclua o login na janela em ate 5 minutos."
}
```

> **Aviso de Fluxo:** Após rodar isso, olhe para a máquina que está hospedando a API. Haverá um navegador piscando nela. Digite seus dados no navegador. Quando você terminar e ver o ícone "Você está logado no Google", execute o Passo 2 descrito no próximo tutorial.
