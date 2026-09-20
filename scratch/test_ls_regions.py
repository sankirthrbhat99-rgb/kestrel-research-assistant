import os
import requests
from dotenv import load_dotenv

def investigate_region():
    load_dotenv(".env")
    key = os.environ.get("LANGCHAIN_API_KEY")
    
    endpoints = [
        "https://api.smith.langchain.com",
        "https://eu.api.smith.langchain.com",
        "https://beta.api.smith.langchain.com"
    ]
    
    headers = {"x-api-key": key}
    
    for url in endpoints:
        print(f"Testing {url} ...")
        # Try /workspaces
        try:
            r = requests.get(f"{url}/workspaces", headers=headers)
            print(f"  /workspaces Status: {r.status_code}")
            if r.status_code == 200:
                print("  SUCCESS! This is the correct region.")
                data = r.json()
                print(f"  Found {len(data)} workspaces.")
                for w in data:
                    print(f"  - ID: {w.get('id')}, Name: {w.get('display_name')}")
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    investigate_region()
