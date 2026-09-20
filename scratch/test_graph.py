from kestrel.graph import get_graph, run_query_traced
import os

print(f"KESTREL_LLM_MODEL: {os.environ.get('KESTREL_LLM_MODEL', 'Not Set')}")
print(f"GEMINI_API_KEY present: {bool(os.environ.get('GEMINI_API_KEY'))}")

question = "What is the maximum number of custom dashboards allowed on the Growth plan?"
print(f"\nQuestion: {question}")
try:
    state, trace_url = run_query_traced(question)
    print("\n--- Final Answer ---")
    print(state.get('final_answer', 'NO ANSWER'))
    print("\n--- Citations ---")
    for c in state.get('citations', []):
        print(f"- {c['title']} ({c['chunk_id']})")
except Exception as e:
    import traceback
    traceback.print_exc()
