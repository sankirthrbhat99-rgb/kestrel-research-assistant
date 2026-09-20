import os
import logging
import http.client
from dotenv import load_dotenv

def debug_langsmith():
    load_dotenv(".env")
    
    # Enable HTTP debugging
    http.client.HTTPConnection.debuglevel = 1
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    req_log = logging.getLogger('requests.packages.urllib3')
    req_log.setLevel(logging.DEBUG)
    req_log.propagate = True
    
    try:
        from langsmith import Client
        client = Client()
        print("--- SDK Configuration ---")
        print(f"API URL: {client.api_url}")
        print(f"API Key read: {bool(client.api_key)}")
        print(f"Workspace ID mapped: {client.workspace_id}")
        
        print("\n--- Making request ---")
        client.has_dataset(dataset_name="kestrel-eval-dataset")
    except Exception as e:
        print(f"\n--- Exception Details ---")
        print(f"Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Status Code: {e.response.status_code}")
            print(f"Headers: {e.response.headers}")
            print(f"Body: {e.response.text}")

if __name__ == "__main__":
    debug_langsmith()
