# Interface do Usuário (Web UI)

Enquanto a premissa primária do projeto seja uma API REST orientada a integrações de sistemas de terceiros (como N8N, Make, ou front-ends React isolados), a API também despacha de forma nativa e embutida uma aplicação Web Server-Rendered.

Isso é excelente para finalidades de Debug, acompanhamento manual de processos, gerência de dados e operação assistida do dia-a-dia.

Acesse a UI rodando o server e acessando a raiz `http://127.0.0.1:8080/`.

---

## 1. Stack Tecnológico da Interface

Toda a web UI é servida via FastAPI e utiliza os seguintes padrões:
- **Rotas HTML**: Contidas inteiramente no arquivo `app/web/routes.py`. As views processam as respostas via biblioteca padrão injetada `Jinja2`.
- **Estilização Dinâmica**: Foram inseridas utility classes similares ao Tailwind diretamente no template central.
- **Engine de Reatividade**: Utiliza a biblioteca [HTMX](https://htmx.org/) via CDN no header. O HTMX varre marcações especiais do HTML devolvendo novas fatias processadas da API para o DOM, provendo interatividade *Single Page Application* sem precisar escrever uma linha de Javascript complexo.

---

## 2. Tabelas e HTMX (A mágica do Polling)

A aplicação conta com dois módulos centrais de exibição.

### Gerenciador de Notebooks (Cadernos)
Tabela carregada sob o endpoint `/web/notebooks` com parciais do HTML Jinja. Lista e permite exclusões síncronas através de botões HTTP `hx-delete` e confirmações amigáveis no navegador.

### Tabela de Jobs (Acompanhamento Real-Time)
É a *killer feature* nativa da observabilidade. O arquivo de template `app/templates/partials/jobs_table.html` lista todos os IDs do disco.
A raiz da div possui a marcação `hx-get="/web/jobs" hx-trigger="every 5s"`.

Isso provoca recarregamentos dinâmicos, que exibem de forma visual (com badges coloridas) o avanço dos arquivos `JobStatus` do backend de `running` para `completed`.

---

## 3. Preservação de Estado `<details>` UX

Devido a natureza de polling agressivo (atualização a cada 5 segundos da tabela inteira pelo HTMX), se o usuário clicasse no accordion HTML genérico nativo `<details>` para investigar e abrir o Log daquele Job, a tabela desabaria instantes depois e fecharia o Log (perdendo estado natural do HTML renderizado).

Para consertar isso e entregar uma experiência rica, inserimos no script base do front-end (`index.html`) duas interceptações nativas de LifeCycle do HTMX:
- `htmx:beforeSwap`: Grava na RAM do navegador (JavaScript `Set`) todos os `<details>` abertos na tela que contêm o ID único que modelamos para eles.
- `htmx:afterSwap`: Reconstrói a tabela do DOM re-injetando o atributo estático `open` nas respectivas tags gravadas na RAM do browser.

Assim, o usuário pode ler pacificamente relatórios massivos JSON contidos no painel enquanto a página ao redor evolui, brilha e carrega sem interrupção agressiva da leitura.

---

## 4. O Botão "Baixar Remoto"

Recentemente integrados a funcionalidade do "Download Tardio e de Resgate" do Backend.

A tabela exibe Jobs em estado `completed` que já perderam suas conexões e nunca mais precisariam de alteração. Entretanto, caso a inicialização nativa faça o Sync iterativo, jobs passados da conta do Usuário ganham vida local e aparecem como Concluídos sem um arquivo linkado (são gerados a partir da listagem oficial).

Ao invés de barrar a interface, um botão renderizado condicionalmente pelo Jinja2 permite acionar a rota `/web/jobs/{job_id}/download-remote`.
- Ele emite uma promessa visual instantânea recarregando o card, informando "Baixando remotamente...".
- Ao fundo, disparamos a Task assíncrona do Python `_background_download` contida no `job_service.py` injetado pelo Router.
- O botão se inativará quando o Polling visual da tabela perceber que o arquivo chegou fisicamente no caminho local `data/artifacts/`.
