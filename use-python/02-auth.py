import requests
import time

BASE_URL = "http://127.0.0.1:8080"

def get_auth_status():
    """Consulta o servidor para saber se estamos logados no Google."""
    print("Verificando status de Autenticacao...")
    response = requests.get(f"{BASE_URL}/auth/status")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Status: {data.get('detail')}")
        print(f"Temos cookies? {data.get('storage_state_present')}")
        print(f"O Acesso a API do NotebookLM esta Ok? {data.get('notebooklm_access_ok')}")
        return data.get('notebooklm_access_ok')
    else:
        print("Erro ao verificar status.")
        return False

def inject_cookies_via_json():
    """Forma Direta 1: Você copiou os cookies de um navegador (EditThisCookie)."""
    print("\nInjetando Cookies Manualmente...")
    
    payload = {
        "cookies": [
            {
                "domain": ".google.com",
                "name": "SID",
                "value": "seu_cookie_sid_aqui",
                "path": "/",
                "httpOnly": True,
                "secure": True
            },
            {
                "domain": ".google.com",
                "name": "HSID",
                "value": "seu_cookie_hsid_aqui",
                "path": "/",
                "httpOnly": True,
                "secure": True
            }
        ],
        "origins": []
    }
    
    response = requests.post(f"{BASE_URL}/auth/storage-state", json=payload)
    print(f"Resposta Injeção HTTP {response.status_code}: {response.text}")

def assistente_de_login_interativo():
    """Forma Alternativa 2: Abre o Playwright na máquina host."""
    print("\nIniciando Fluxo de Login Interativo...")
    
    # Passo 1: Abrir
    start_res = requests.post(f"{BASE_URL}/auth/login/start")
    if start_res.status_code != 200:
        print("Falha ao abrir navegador.")
        return
        
    session_id = start_res.json()["session_id"]
    print(f"Navegador aberto! Session ID: {session_id}")
    print("Por favor, va ate a maquina Host do servidor e faça o login no Chromium.")
    print("Aguardando 30 segundos simulados...")
    
    time.sleep(30) # Na vida real, o seu usuário apertaria um botão na sua interface
    
    # Passo 2: Fechar e roubar os cookies
    print("\nAvisando a API para finalizar a captura...")
    complete_payload = {
        "session_id": session_id,
        "storage_state": {"cookies": [], "origins": []}
    }
    
    complete_res = requests.post(f"{BASE_URL}/auth/login/complete", json=complete_payload)
    print(f"Resultado do Fechamento: {complete_res.text}")

if __name__ == "__main__":
    # Teste o fluxo de status:
    is_logged = get_auth_status()
    
    if not is_logged:
        # Escolha uma das abordagens para se logar:
        # inject_cookies_via_json()
        pass
