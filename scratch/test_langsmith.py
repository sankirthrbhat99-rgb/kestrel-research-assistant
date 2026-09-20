import os
from dotenv import load_dotenv

def test_langsmith():
    has_env = load_dotenv(".env")
    print(f"Loaded .env: {has_env}")
    
    # Check vars
    ls_key = os.environ.get("LANGCHAIN_API_KEY")
    ls_proj = os.environ.get("LANGCHAIN_PROJECT")
    ls_tracing = os.environ.get("LANGCHAIN_TRACING_V2")
    
    print(f"LANGCHAIN_API_KEY present: {bool(ls_key)}")
    print(f"LANGCHAIN_PROJECT: {ls_proj}")
    print(f"LANGCHAIN_TRACING_V2: {ls_tracing}")
    
    # Try Langsmith API
    try:
        from langsmith import Client
        client = Client()
        # Just try to list projects, getting the first one to test auth
        projects = list(client.list_projects(limit=1))
        print("LangSmith authentication successful!")
        if len(projects) > 0:
            print(f"Successfully retrieved project list (e.g., {projects[0].name})")
        else:
            print("Successfully authenticated, but no projects found yet.")
    except Exception as e:
        print(f"LangSmith authentication failed: {e}")

if __name__ == '__main__':
    test_langsmith()
