import os
import requests
from dotenv import load_dotenv

def inspect_langsmith():
    load_dotenv(".env")
    key = os.environ.get("LANGCHAIN_API_KEY")
    base_url = os.environ.get("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
    
    headers = {"x-api-key": key}
    
    # 1. Check /info
    try:
        r1 = requests.get(f"{base_url}/info", headers=headers)
        print(f"INFO Status: {r1.status_code}")
        if r1.status_code == 200:
            data = r1.json()
            print(f"Info keys: {list(data.keys())}")
            if "tenant_id" in data:
                print("Tenant ID is present in /info.")
        else:
            print(f"INFO Response: {r1.text}")
    except Exception as e:
        print(f"INFO request failed: {e}")

    # 2. Check /auth/me or similar if exists
    try:
        r2 = requests.get(f"{base_url}/auth/me", headers=headers)
        print(f"AUTH Status: {r2.status_code}")
    except Exception as e:
        pass
        
    # 3. Check /workspaces or /tenants
    try:
        r3 = requests.get(f"{base_url}/workspaces", headers=headers)
        print(f"WORKSPACES Status: {r3.status_code}")
        if r3.status_code == 200:
            data = r3.json()
            print(f"Workspaces available: {len(data)}")
        else:
            print(f"WORKSPACES Response: {r3.text}")
    except Exception as e:
        pass

if __name__ == "__main__":
    inspect_langsmith()
