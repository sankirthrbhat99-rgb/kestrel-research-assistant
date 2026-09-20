import os
from dotenv import load_dotenv

def test_dataset_api():
    load_dotenv(".env")
    try:
        from langsmith import Client
        client = Client()
        # Try to check for the dataset we actually need
        has = client.has_dataset(dataset_name="kestrel-eval-dataset")
        print(f"Dataset access check successful. has_dataset: {has}")
        print("LangSmith authentication is fully working for the eval script!")
    except Exception as e:
        print(f"Dataset access failed: {e}")

if __name__ == "__main__":
    test_dataset_api()
