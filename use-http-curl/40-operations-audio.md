# 40. Operações com Áudio (Podcast)

Este é o módulo que engatilha o modelo Multimodal de Anfitriões na Nuvem para gerar um WAV (O "Deep Dive").

Você possui duas maneiras de chamar:
1. `?async=true` (Oculta na Cloud e libera seu Terminal com status HTTP 202).
2. `?async=false` (A API prende sua conexão `curl` por 4 minutos em tela preta e no final expele o download diretamente em arquivo físico).

## A. O Modo Assíncrono (`?async=true`) Recomendado
Este é o modo desenhado para N8N, Webhooks e Produção de verdade, porque ele não crachará e passará pra um `Job` gerenciável. 

### `POST /operations/audio-summary`
```bash
curl -X POST "http://127.0.0.1:8080/operations/audio-summary?async=true" \
     -H "Content-Type: application/json" \
     -d '{
  "local_id": 1,
  "mode": "debate",
  "language": "pt-BR",
  "duration": "standard",
  "focus_prompt": "Por favor, atente-se apenas ao segundo paragrafo.",
  "name": "Meu Resumo Audio"
}'
```

**Resposta HTTP 202 (Accepted)**:
Note que não foi devolvido o WAV, mas sim o ID de um `JobRecord` recém listado na fila do backend local. Use esse `job_id` no script do tutorial 30 e 50.
```json
{
  "job_id": "e30e1f7c-7a6c-482c-9d6a-...",
  "detail": "Operacao iniciada de forma assincrona."
}
```

---

## B. O Modo Síncrono / Imediatista (`?async=false`)
A utilidade deste script reside num download direto em um terminal que ficará parado até a nuvem despachar o áudio. Útil para scripts de backup simples noturnos.

> IMPORTANTE: A opção `--output` finaliza redirecionando a saída binária de retorno HTTP pro arquivo no seu OS. Sem ela, seu terminal travaria engasgado vomitando texto corrompido do binário WAV.

### `POST /operations/audio-summary`
```bash
curl -X POST "http://127.0.0.1:8080/operations/audio-summary?async=false" \
     -H "Content-Type: application/json" \
     -d '{
  "notebook_id": "xxxxxx",
  "mode": "summary",
  "language": "pt-BR"
}' --output meu_audio_gerado.wav
```

**Resultado:** Em vez de receber um JSON, seu Bash travará por cerca de alguns minutos. Quando voltar o prompt, digite `ls` e verá o arquivo `meu_audio_gerado.wav` criado na mesma pasta de sua máquina.
