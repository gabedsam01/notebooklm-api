import requests

BASE_URL = "http://127.0.0.1:8080"
TEST_NOTEBOOK_ID = 1

def gerar_audio_async():
    """Dispara pra nuvem, liberta o client e devolve a Chave do Tracker."""
    print("Disparando comando de Podcast ASSINCRONO...")
    
    payload = {
        "local_id": TEST_NOTEBOOK_ID,
        "mode": "detailed_analysis", # Enums: "summary", "detailed_analysis", "critical_review", "debate"
        "language": "pt-BR",
        "name": "Análise Profunda" # Um nome para facilitar sua busca na tabela jobs
    }
    
    res = requests.post(f"{BASE_URL}/operations/audio-summary?async=true", json=payload)
    
    if res.status_code == 202:
        print("Requisição aceita!")
        print(f"O seu Job Tracking ID é: {res.json()['job_id']}")
        print("Jogue este ID no rastreador do script 05-jobs.py")
    else:
        print(f"Erro: {res.text}")

def gerar_audio_sync():
    """Trava a thread Python por 5 minutos e devolve binario."""
    print("Disparando Podcast SINCRONO (Sua tela vai travar)...")
    
    payload = {
        "local_id": TEST_NOTEBOOK_ID,
        "mode": "summary",
        "language": "en"
    }
    
    res = requests.post(f"{BASE_URL}/operations/audio-summary?async=false", json=payload)
    
    if res.status_code == 200:
        print("Arquivo recebido na memória RAM! Escrevendo pro HD...")
        with open("podcast_sincrono_ingles.wav", "wb") as f:
            f.write(res.content)
        print("Arquivo salvo com sucesso: podcast_sincrono_ingles.wav")
    else:
        print(f"Falhou! {res.status_code}: {res.text}")

if __name__ == "__main__":
    gerar_audio_async()
    # gerar_audio_sync()
