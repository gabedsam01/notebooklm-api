# Deploy com Contêineres (Docker)

O ecossistema `notebooklm-api` desenha limites rígidos entre "Código Descartável" e "Estado Crítico". Todo o Estado Crítico foi projetado intencionalmente para residir exclusivamente no sub-diretório estrito `/app/data/`.

Isso facilita a criação de Imagens OCI efêmeras sem o risco de perda de Jobs e Cookies durante os updates.

---

## Estrutura do Volume Persistente
A raiz do ambiente possui a pasta `data/`. Se você não a mapear explicitamente em suas configurações de Host Docker, ela ficará alocada na ramificação anonimizada do daemon docker e você perderá a conta ao recriar o contêiner.

O mapeamento exato da pasta inclui:
- `data/auth/` (Seu `storage_state.json`)
- `data/notebooks.db` (Banco local)
- `data/jobs/` (Estado atual da Background Task)
- `data/artifacts/` (Todos os WAV/MP4 gigantescos)

## 1. Usando Docker puro (CLI)

Gere a imagem primária do projeto usando o repositório como raiz.

```bash
docker build -t notebooklm-api:latest .
```

Instancie acoplando volumes estritos e expondo a porta `8080` base.
Utilize a flag `-v` para amarrar o diretório local do servidor.

```bash
docker run -d \
  --name nblm-backend \
  -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  -e NOTEBOOKLM_MODE=real \
  -e APP_HOST=0.0.0.0 \
  -e APP_PORT=8080 \
  notebooklm-api:latest
```

## 2. Orquestração com Docker Compose (Recomendado)

A abordagem declarativa com o `docker-compose.yml` embutido é mais propícia a manutenções.

Crie no seu host linux/vps um arquivo `docker-compose.yml` isolado:
```yaml
version: '3.8'

services:
  api:
    image: notebooklm-api:latest
    build: .
    container_name: notebooklm-api
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./data:/app/data
    environment:
      - NOTEBOOKLM_MODE=real
      - APP_HOST=0.0.0.0
      - APP_PORT=8080
      - ARTIFACT_WAIT_TIMEOUT_SECONDS=1800
      - ARTIFACT_POLL_INTERVAL_SECONDS=15.0
```

E para iniciar:
```bash
# Sobe e constrói em background silenciosamente
docker-compose up -d --build

# Visualizar o console do servidor Uvicorn logando eventos
docker-compose logs -f api
```

## 3. Segurança e Considerações de Permissões POSIX

A maior armadilha no Docker com mapeamento `bind-mount` (o `-v ./data:/app/data`) é o conflito do UID/GID do usuário raiz do seu servidor com o UID/GID do Python rodando dentro do Ubuntu/Alpine da Imagem.

Se a aplicação Docker lançar exceções de *Access Denied* ao tentar salvar:
1. Certifique-se de pre-criar o diretório `/data` no host local e aplicar `chmod 777 -R ./data` temporariamente para garantir acesso global, ou;
2. Descubra o UID do contêiner e utilize um `chown` na pasta hospedada.
3. Não versionar a pasta `data/` no seu Git, pois carrega seus cookies e áudios privativos. O arquivo `.gitignore` do repositório já se responsabiliza por isso nativamente.
