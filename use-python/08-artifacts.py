import requests
import sys

BASE_URL = "http://127.0.0.1:8080"

def download_completed_artifact(job_id: str, save_filename: str):
    """
    Tenta baixar a mídia estática. 
    Se o banco retornar HTTP 409, a API te dá a chance de não estourar Exception,
    pois isso só quer dizer que ainda está processando.
    """
    print(f"Iniciando tentativa de Download para o Job: {job_id}")
    
    # Fazemos streaming caso o video seja de 50mb+
    with requests.get(f"{BASE_URL}/artifacts/{job_id}", stream=True) as res:
        
        if res.status_code == 200:
            # Baixa enchendo o HD
            print("Download iniciado...")
            with open(save_filename, 'wb') as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Arquivo blindado e salvo como: {save_filename}")
            
        elif res.status_code == 409:
            print("HTTP 409: Calma, o Google ainda esta processando isso. Volte mais tarde.")
            
        elif res.status_code == 404:
            print("HTTP 404: Job ID nao existe, ou o processo crachou corrompendo a rede.")
            
        else:
            print(f"Erro desconhecido: HTTP {res.status_code}")

if __name__ == "__main__":
    # Exemplo: rode passando o ID via CLI `python 08-artifacts.py UUID_AQUI`
    if len(sys.argv) > 1:
        target_uuid = sys.argv[1]
        download_completed_artifact(target_uuid, "resultado_api.mp4")
    else:
        print("Passe um job_id. Exemplo de chamada no terminal:")
        print("python 08-artifacts.py e30e1f7c-7a6c-482c-...")
