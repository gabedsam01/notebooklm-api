# Guia Prático: curl

Bem-vindo à biblioteca de exemplos práticos em `curl` para a NotebookLM API. 

Estes exemplos demonstram como enviar os payloads em JSON via terminal ou utilizá-los em plataformas como o n8n e Postman.

## Configuração Inicial
As requisições assumem que sua API está rodando localmente.
A **URL Base** é: `http://127.0.0.1:8080/`

## Dica de Leitura JSON
Para que o output JSON retornado pela API não fique quebrado na tela do seu terminal Linux/Mac, você pode adicionar o utilitário `| jq` ao final do comando caso o tenha instalado (`sudo apt install jq`). Todos os comandos aqui estão limpos e puros para melhor entendimento.

## Navegue pelos Exemplos

1. [Saúde da API (Health)](01-health.md)
2. [Consultar Status da Autenticação](02-auth-status.md)
3. [Injetar Storage State](03-auth-storage-state.md)
4. [Início Login Assistido](04-auth-login-start.md)
5. [Finalizar Login Assistido](05-auth-login-complete.md)
6. [Gerenciamento de Notebooks (CRUD)](10-notebooks.md)
7. [Injeção de Fontes de Texto](20-sources.md)
8. [Verificação e Listagem de Jobs](30-jobs.md)
9. [Gerar Resumos em Áudio (Podcast)](40-operations-audio.md)
10. [Gerar Resumos em Vídeo (Quadro)](41-operations-video.md)
11. [Download do Arquivo (Artifacts)](50-artifacts.md)
12. [Fluxos Encapsulados de Ponta a Ponta](90-fluxos-completos.md)
