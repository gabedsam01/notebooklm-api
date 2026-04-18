import requests

BASE_URL = "http://127.0.0.1:8080"

def check_health():
    """Verifica se a API está de pé e rodando."""
    print("Checando saude do servidor...")
    
    response = requests.get(f"{BASE_URL}/health")
    
    if response.status_code == 200:
        data = response.json()
        print("Sucesso!")
        print(f"Status: {data['status']}")
        print(f"Versão: {data.get('version', 'Desconhecida')}")
    else:
        print(f"Erro ao conectar. Status HTTP: {response.status_code}")

if __name__ == "__main__":
    check_health()
