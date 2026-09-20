import json

def analyze_results():
    questions = {}
    with open('results/eval_questions.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            q = json.loads(line)
            questions[q['question_id']] = q

    results = []
    with open('results/baseline/eval_results.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            results.append(json.loads(line))
            
    print("| Q_ID | Category | Ans Len | Retrieved | Expected | Recall | MRR | Faith | Rel | Corr | Cite Prec |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    
    for r in results:
        q_id = r.get("question_id", "N/A")
        q = questions.get(q_id, {})
        category = q.get("type", "unknown")
        expected_chunks = q.get("expected_chunk_ids", [])
        
        ans_len = len(r.get("answer", ""))
        retrieved = r.get("retrieved_chunk_ids", [])
        
        scores = r.get("scores", {})
        recall = scores.get("retrieval_recall@k", 0.0)
        mrr = scores.get("retrieval_mrr", 0.0)
        faith = scores.get("faithfulness", 0.0)
        rel = scores.get("answer_relevance", 0.0)
        corr = scores.get("correctness", 0.0)
        prec = scores.get("citation_precision", 0.0)
        
        print(f"| {q_id} | {category} | {ans_len} | {len(retrieved)} | {len(expected_chunks)} | {recall:.2f} | {mrr:.2f} | {faith:.2f} | {rel:.2f} | {corr:.2f} | {prec:.2f} |")
        
    print("\n--- Diagnostic Inspection of 5 Questions ---")
    for r in results[:5]:
        q_id = r.get("question_id")
        q = questions.get(q_id, {})
        print(f"Question ID: {q_id} ({q.get('type')})")
        print(f"Question: {q.get('question')}")
        print(f"Expected Answer: {q.get('expected_answer')}")
        print(f"Actual Answer: {r.get('answer')}")
        print(f"Scores: {r.get('scores')}")
        print("-" * 40)

if __name__ == '__main__':
    analyze_results()
