import requests
import time

BASE_URL = "http://127.0.0.1:8080"

def list_recent_jobs():
    """Busca a tabela de Jobs (padrão decrescente por data)."""
    print("Buscando últimos Jobs da fila...")
    res = requests.get(f"{BASE_URL}/jobs")
    if res.status_code == 200:
        data = res.json()
        print(f"Total na base: {data['count']}")
        for job in data['items'][:5]: # Mostra só os 5 primeiros
            print(f"- [{job['status'].upper()}] ID: {job['id']} | Tipo: {job['type']}")

def watch_job_until_completion(job_id: str):
    """
    Simulação de Polling perfeita.
    É desta maneira exata que sua Aplicação Client ou Front-end deve consultar a API
    quando despachar um ?async=true.
    """
    print(f"\nIniciando Rastreio do Job: {job_id}")
    
    while True:
        res = requests.get(f"{BASE_URL}/jobs/{job_id}")
        
        if res.status_code != 200:
            print("Job não encontrado ou deletado!")
            break
            
        job_data = res.json()
        status = job_data['status']
        
        # Pega a ultima log message pro usuario saber o que ta rolando
        last_log = "Sem logs"
        if len(job_data.get('logs', [])) > 0:
            last_log = job_data['logs'][-1]['message']
            
        print(f"[Status: {status}] -> {last_log}")
        
        if status == "completed":
            print("\n✔️ JOB CONCLUIDO COM SUCESSO!")
            print(f"Caminho do Artefato Salvo: {job_data.get('artifact_path')}")
            break
        elif status in ["failed", "timed_out"]:
            print(f"\n❌ Falha catastrofica no Job: {job_data.get('error')}")
            break
            
        # O Google demora, espere educadamente 15 segundos antes de reconsultar o DB.
        time.sleep(15)

if __name__ == "__main__":
    list_recent_jobs()
    # Descomente e coloque o ID gerado nas pastas 06 ou 07
    # watch_job_until_completion("SEU_UUID_GERADO_PELO_ASYNC_AQUI")
