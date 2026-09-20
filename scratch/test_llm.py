from kestrel.llm import LLMClient

def test():
    c = LLMClient()
    print(f"Configured: {c.config.configured}")
    print(f"Provider: {c.config.provider}")
    print(f"Model: {c.config.model}")
    
    print("\nTesting single complete()...")
    try:
        response = c.complete("Hello, this is a single question test to verify the LLM works.")
        print(f"Response: {response}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    test()
