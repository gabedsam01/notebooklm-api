# 05. Assistente de Login Playwright (Fim)

Após você visualizar a tela na janela remota/local e atestar que inseriu as credenciais do Google corretamente e passou por qualquer tipo de desafio de captchas, você avisa o servidor que ele já pode roubar os cookies e fechar a aba.

### O Comando (`POST /auth/login/complete`)
Você precisa injetar no payload o ID que foi recebido no passo anterior (`04-auth-login-start`).

```bash
curl -X POST "http://127.0.0.1:8080/auth/login/complete" \
     -H "Content-Type: application/json" \
     -d '{
  "session_id": "8a91fbc2",
  "storage_state": {
    "cookies": [],
    "origins": []
  }
}'
```
> *Nota Técnica*: A propriedade `storage_state` com objetos vazios (`{}`) é obrigatória no schema de Request atual para preenchimento de mock. Deixe os arrays limpos, a API é madura e os ignorará, extraindo por trás dos panos o arquivo diretamente da RAM do Playwright.

### Resposta JSON Esperada

A janela se fechará, a RAM será esvaziada e a resposta informará:
```json
{
  "completed": true,
  "detail": "Login efetuado e storage_state.json salvo com sucesso"
}
```

A partir deste momento, você está livre para utilizar toda a API em Modo Real.
