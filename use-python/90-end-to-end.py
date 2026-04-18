import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8080"

def automacao_ponta_a_ponta_do_zero(titulo_caderno: str, texto_longo: str):
    """
    Fluxo Corporativo Oficial.
    Ele unifica tudo que você viu nas pastas do 01 ao 08.
    Cria caderno > Adiciona > Dispara Async > Fica em While Loop > Baixa Wav > Deleta caderno.
    """
    print("="*60)
    print("🚀 INICIANDO AUTOMAÇÃO DE PONTA A PONTA")
    print("="*60)
    
    # --- PASSO 1: CRIAR ---
    print("\n1. Criando Notebook novo...")
    res_nb = requests.post(f"{BASE_URL}/notebooks", json={"title": titulo_caderno})
    if res_nb.status_code != 201:
        print(f"Falha na criação. Certifique-se que o Auth esta verde. {res_nb.text}")
        sys.exit(1)
        
    local_id = res_nb.json()["local_id"]
    print(f"--> Caderno criado com Sucesso (Local ID: {local_id})")
    
    # --- PASSO 2: ALIMENTAR ---
    print("\n2. Inserindo Conhecimento Textual...")
    res_src = requests.post(f"{BASE_URL}/sources/text", json={
        "local_id": local_id,
        "title": "Documento Unico",
        "content": texto_longo
    })
    
    if res_src.status_code != 200:
        print("Falha ao colocar o arquivo texto.")
        sys.exit(1)
    print("--> Texto inserido!")

    # --- PASSO 3: DISPARAR ORDEM DE JOB ---
    print("\n3. Solicitando ao Servidor um Podcast (Audio) Assincrono...")
    res_op = requests.post(f"{BASE_URL}/operations/audio-summary?async=true", json={
        "local_id": local_id,
        "mode": "summary",
        "language": "pt-BR",
        "name": f"Podcast: {titulo_caderno}"
    })
    
    job_id = res_op.json()["job_id"]
    print(f"--> Job enfileirado! ID a ser rastreado: {job_id}")
    
    # --- PASSO 4: O POLLING ---
    print("\n4. Entrando em modo Tracker/Polling (Vai demorar alguns minutos)...")
    while True:
        res_job = requests.get(f"{BASE_URL}/jobs/{job_id}")
        job_data = res_job.json()
        
        st = job_data["status"]
        if st == "completed":
            print("\n--> Mídia Processada e pronta para Coleta!")
            break
        elif st in ["failed", "timed_out"]:
            print(f"\n--> TRAGEDIA NO JOB: {job_data['error']}")
            sys.exit(1)
        
        # Log interativo na tela
        msg = job_data.get("logs", [{"message": "Iniciando..."}])[-1]["message"]
        print(f"   ⏳ {st.upper()} : {msg}")
        time.sleep(15)

    # --- PASSO 5: DOWNLOAD FINAL ---
    print("\n5. Efetuando Download da Midia para a maquina rodando python...")
    res_dl = requests.get(f"{BASE_URL}/artifacts/{job_id}", stream=True)
    filename = f"Resultado_Automacao_Python_{local_id}.wav"
    
    if res_dl.status_code == 200:
        with open(filename, 'wb') as f:
            for chunk in res_dl.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"--> DOWNLOAD FINALIZADO: {filename}")
    else:
        print("--> Erro catastrofico no endpoint do binario!")

    # --- PASSO 6: LIXEIRA ---
    print("\n6. Limpeza de rastro (Deletando Caderno no Google)")
    requests.delete(f"{BASE_URL}/notebooks/local/{local_id}")
    print("--> Limpo. Programa Encerrado com Excelência.")

if __name__ == "__main__":
    # Teste vocẽ mesmo!
    
    TEXTO = """
    A inteligência artificial generativa tem avançado muito nos últimos dois anos.
    Com a chegada de arquiteturas modulares, grandes empresas...
    (Este texto deveria ser enorme para o podcast ficar bom)
    """
    automacao_ponta_a_ponta_do_zero("Caderno Via N8N/Python", TEXTO)
