import os
from dotenv import load_dotenv

def test_config():
    # 1. Check .env is detected
    has_env = load_dotenv(".env")
    print(f"Loaded .env file: {has_env}")

    # 2. Check vars
    required_vars = ["GEMINI_API_KEY", "LANGCHAIN_TRACING_V2", "LANGSMITH_API_KEY"]
    for var in required_vars:
        val = os.environ.get(var)
        print(f"{var} present: {bool(val)}")

    # Test LLM Config
    try:
        from kestrel.llm import LLMConfig
        config = LLMConfig.from_env()
        print(f"LLM Provider detected: {config.provider}")
        print(f"LLM Model detected: {config.model}")
        print(f"LLM Base URL detected: {config.base_url}")
        print(f"LLM Configured: {config.configured}")
    except Exception as e:
        print(f"Error loading LLMConfig: {e}")

    # Test Tracing Config
    try:
        from kestrel.tracing import is_tracing_enabled
        enabled = is_tracing_enabled()
        print(f"Tracing enabled via kestrel.tracing: {enabled}")
        
        # also print the tracing var value safely (true/false)
        print(f"LANGCHAIN_TRACING_V2 value: {os.environ.get('LANGCHAIN_TRACING_V2', 'NOT SET')}")
        print(f"LANGCHAIN_PROJECT value: {os.environ.get('LANGCHAIN_PROJECT', 'NOT SET')}")
        print(f"LANGSMITH_PROJECT value: {os.environ.get('LANGSMITH_PROJECT', 'NOT SET')}")
    except Exception as e:
        print(f"Error loading tracing config: {e}")

if __name__ == '__main__':
    test_config()
