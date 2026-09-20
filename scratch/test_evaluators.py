import json

def get_judge_llm(prompt):
    return '{"score": 1.0}'

def correctness(run, example):
    q_type = example.outputs["type"]
    answer = run.outputs.get("answer", "")
    if q_type == "unsupported":
        prompt = f"Answer: {answer}\nDoes the answer clearly state that the documents do not settle or contain the information? Return strictly JSON: {{\"score\": 1.0}} or {{\"score\": 0.0}}."
        try:
            res = json.loads(get_judge_llm(prompt))
            return {"key": "correctness", "score": float(res.get("score", 0.0))}
        except:
            return {"key": "correctness", "score": 0.0}
            
    expected_chunks = set(example.outputs["expected_chunk_ids"])
    raw_citations = run.outputs.get("citations", [])
    cited_chunks = {c["chunk_id"] if isinstance(c, dict) else c for c in raw_citations}
    if not expected_chunks.intersection(cited_chunks):
        return {"key": "correctness", "score": 0.0}
        
    expected_ans = example.outputs["expected_answer"]
    prompt = f"Expected: {expected_ans}\nActual: {answer}\nIs the actual answer correct given the expected? Return strictly JSON: {{\"score\": 1.0}} or {{\"score\": 0.0}}."
    try:
        res = json.loads(get_judge_llm(prompt))
        return {"key": "correctness", "score": float(res.get("score", 0.0))}
    except:
        return {"key": "correctness", "score": 0.0}

def citation_precision(run, example):
    expected_chunks = set(example.outputs["expected_chunk_ids"])
    raw_citations = run.outputs.get("citations", [])
    cited_chunks = {c["chunk_id"] if isinstance(c, dict) else c for c in raw_citations}
    if not cited_chunks:
        return {"key": "citation_precision", "score": 1.0 if not expected_chunks else 0.0}
    
    correct = len(expected_chunks.intersection(cited_chunks))
    return {"key": "citation_precision", "score": correct / len(cited_chunks)}

class MockExample:
    def __init__(self, outputs):
        self.outputs = outputs
        self.inputs = {"question_id": "test-1"}

class MockRun:
    def __init__(self, outputs):
        self.outputs = outputs

def test_evaluators():
    example = MockExample(outputs={"type": "single_hop", "expected_chunk_ids": ["chunk_1", "chunk_2"], "expected_answer": "It is true."})
    
    # 1. Dict citations
    run1 = MockRun(outputs={"answer": "It is true.", "citations": [{"chunk_id": "chunk_1", "content": "text"}, {"chunk_id": "chunk_3", "content": "text"}]})
    print(f"Test 1 Correctness (Dicts): {correctness(run1, example)}")
    print(f"Test 1 Precision (Dicts): {citation_precision(run1, example)}")
    
    # 2. String citations (legacy)
    run2 = MockRun(outputs={"answer": "It is true.", "citations": ["chunk_1", "chunk_3"]})
    print(f"Test 2 Correctness (Strings): {correctness(run2, example)}")
    print(f"Test 2 Precision (Strings): {citation_precision(run2, example)}")

if __name__ == "__main__":
    test_evaluators()
