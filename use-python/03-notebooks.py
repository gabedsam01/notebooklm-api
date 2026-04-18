import requests

BASE_URL = "http://127.0.0.1:8080"

def sync_notebooks():
    """Baixa Notebooks existentes na nuvem do Google para seu Banco SQLite local."""
    print("Sincronizando banco local com o Google...")
    res = requests.post(f"{BASE_URL}/notebooks/sync")
    print(res.json())

def list_notebooks():
    """Lista o banco local."""
    print("\nListando Notebooks Cadastrados:")
    res = requests.get(f"{BASE_URL}/notebooks")
    if res.status_code == 200:
        data = res.json()
        print(f"Encontrados: {data['count']}")
        for nb in data['items']:
            print(f"- [ID Local: {nb['local_id']}] {nb['title']} (Google ID: {nb['notebook_id']})")
    else:
        print("Erro ao listar.")

def create_notebook(title: str):
    """Cria programaticamente."""
    print(f"\nCriando novo Notebook chamado '{title}'...")
    res = requests.post(f"{BASE_URL}/notebooks", json={"title": title})
    if res.status_code == 201:
        data = res.json()
        print(f"Sucesso! ID Local salvo: {data['local_id']}")
        return data['local_id']
    else:
        print(f"Falha: {res.text}")
        return None

def delete_notebook_by_local_id(local_id: int):
    """Deleta limpando o Google e o SQLite."""
    print(f"\nDeletando caderno local_id={local_id}...")
    res = requests.delete(f"{BASE_URL}/notebooks/local/{local_id}")
    print(f"Status HTTP: {res.status_code}. Resposta: {res.json()}")

if __name__ == "__main__":
    sync_notebooks()
    list_notebooks()
    
    # Criar um pra testes
    # new_id = create_notebook("Laboratório de Testes API")
    
    # Se quiser testar o delete
    # if new_id:
    #     delete_notebook_by_local_id(new_id)
