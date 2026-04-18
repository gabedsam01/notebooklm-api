import requests

BASE_URL = "http://127.0.0.1:8080"
TEST_NOTEBOOK_ID = 1 # Substitua pelo local_id ou UUID real do seu banco

def add_single_text_source():
    print("Injetando fonte unica...")
    payload = {
        "local_id": TEST_NOTEBOOK_ID,
        "title": "Anotações do Dia 1",
        "content": "A API é capaz de digerir grandes volumes textuais de forma robusta."
    }
    
    res = requests.post(f"{BASE_URL}/sources/text", json=payload)
    print(f"Status: {res.status_code}")
    print(res.json())

def add_batch_text_sources():
    """Forma eficiente de adicionar múltiplos textos sem gargalos na rede HTTP."""
    print("\nInjetando batch de fontes...")
    
    payload = {
        "local_id": TEST_NOTEBOOK_ID,
        "sources": [
            {
                "title": "Capítulo 1: O Início",
                "content": "Conteúdo denso aqui..."
            },
            {
                "title": "Capítulo 2: O Meio",
                "content": "Outra carga considerável..."
            },
            {
                "title": "Capítulo 3: O Fim",
                "content": "Conclusão das anotações."
            }
        ]
    }
    
    res = requests.post(f"{BASE_URL}/sources/batch", json=payload)
    print(f"Status: {res.status_code}")
    print(res.json())

if __name__ == "__main__":
    add_single_text_source()
    add_batch_text_sources()
