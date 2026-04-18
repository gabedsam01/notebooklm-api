# Guia Prático: Python + Requests

Bem-vindo à biblioteca de exemplos práticos em Python para a NotebookLM API. 

Optamos por utilizar a biblioteca síncrona `requests` ao invés de clientes assíncronos (`httpx`, `aiohttp`) pois é a forma mais legível, linear e amplamente utilizada para integração de scripts.

## Instalação de Dependências
Você precisará apenas de:

```bash
pip install requests
```

## Navegue pelos Scripts

Estes scripts não são apenas tutoriais em texto, são arquivos `.py` **100% executáveis**. Copie para o seu projeto, altere os IDs e rode!

1. [Saúde da API (Health)](01-health.py)
2. [Fluxo Inteiro de Autenticação (Status, State e Completo)](02-auth.py)
3. [CRUD de Notebooks e Sincronização](03-notebooks.py)
4. [Injeção Simples e em Batch de Fontes](04-sources.py)
5. [Rastreador Local de Jobs (Polling em Loop)](05-jobs.py)
6. [Gerador de Podcast via Áudio (Async & Sync)](06-operations-audio.py)
7. [Gerador de Vídeos em Lousa](07-operations-video.py)
8. [Script de Download de Artefatos Binários](08-artifacts.py)
9. [A Obra Prima: Fluxos de Automação de Ponta a Ponta](90-end-to-end.py)
