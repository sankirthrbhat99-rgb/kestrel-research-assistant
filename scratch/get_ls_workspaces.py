import os
import requests
from dotenv import load_dotenv

def get_workspaces():
    load_dotenv(".env")
    key = os.environ.get("LANGCHAIN_API_KEY")
    headers = {"x-api-key": key}
    
    endpoints = [
        "https://api.smith.langchain.com/api/v1/workspaces",
        "https://api.smith.langchain.com/workspaces",
        "https://api.smith.langchain.com/api/v1/tenants"
    ]
    
    for url in endpoints:
        print(f"Trying {url} ...")
        try:
            r = requests.get(url, headers=headers)
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                # data might be a list or a dict with a 'workspaces' key
                workspaces = data if isinstance(data, list) else data.get("workspaces", data.get("tenants", []))
                for w in workspaces:
                    name = w.get("display_name", w.get("name", "N/A"))
                    w_id = w.get("id", "N/A")
                    org_id = w.get("organization_id", w.get("tenant_id", "N/A"))
                    is_personal = w.get("is_personal", "N/A")
                    print(f"- Workspace display_name: {name}")
                    print(f"  Workspace id: {w_id}")
                    print(f"  organization_id: {org_id}")
                    print(f"  is_personal: {is_personal}")
                return
            else:
                try:
                    err = r.json()
                    print(f"Error: {err.get('detail', err)}")
                except:
                    print(f"Error: {r.text[:100]}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    get_workspaces()
