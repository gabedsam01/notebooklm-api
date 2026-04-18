import requests

BASE_URL = "http://127.0.0.1:8080"
TEST_NOTEBOOK_ID = 1

def gerar_video_async():
    """Modo Lousa Dinâmica Assíncrono."""
    print("Disparando comando de Vídeo ASSINCRONO...")
    
    payload = {
        "local_id": TEST_NOTEBOOK_ID,
        "mode": "explanatory_video",
        "style": "summary",
        "language": "pt-BR",
        "focus_prompt": "Crie uma aula focada apenas no capitulo final.",
        "name": "Video Final"
    }
    
    res = requests.post(f"{BASE_URL}/operations/video-summary?async=true", json=payload)
    
    if res.status_code == 202:
        print("Operacao enfileirada no backend local.")
        print(f"Tracking UUID: {res.json()['job_id']}")
    else:
        print(f"Erro: {res.text}")

if __name__ == "__main__":
    gerar_video_async()
