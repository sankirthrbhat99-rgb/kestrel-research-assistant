import argparse
import json
import os
import sys
import time

from dotenv import load_dotenv
from langsmith import Client, evaluate
from kestrel.graph import get_graph, run_query_traced
from kestrel.llm import LLMClient

def get_judge_llm(prompt: str) -> str:
    client = LLMClient()
    return client.complete(prompt, max_tokens=100, temperature=0.0)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", type=str, required=True, help="Tag for this run (e.g., baseline, improved)")
    parser.add_argument("--out-dir", type=str, required=True, help="Output directory for results")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(env_path)
    
    ls_client = Client()
    dataset_name = "kestrel-eval-dataset"
    
    # 1. Ensure dataset exists
    if not ls_client.has_dataset(dataset_name=dataset_name):
        dataset = ls_client.create_dataset(dataset_name)
        with open("results/eval_questions.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                inputs = {
                    "question_id": row["question_id"],
                    "question": row["question"],
                    "conversation_id": row.get("conversation_id"),
                    "turn": row.get("turn")
                }
                outputs = {
                    "expected_answer": row["expected_answer"],
                    "expected_chunk_ids": row["expected_chunk_ids"],
                    "type": row["type"]
                }
                ls_client.create_example(inputs=inputs, outputs=outputs, dataset_id=dataset.id)
    
    history_cache = {}
    
    def predict(inputs: dict) -> dict:
        q = inputs["question"]
        cid = inputs.get("conversation_id")
        history = None
        if cid:
            if cid not in history_cache:
                history_cache[cid] = []
            history = list(history_cache[cid]) # Copy
            
        start = time.time()
        state, trace_url = run_query_traced(q, history=history, conversation_id=cid)
        latency = time.time() - start
        
        # update history cache
        if cid:
            history_cache[cid].append({"role": "user", "content": q})
            history_cache[cid].append({"role": "assistant", "content": state["final_answer"]})
            
        return {
            "answer": state["final_answer"],
            "citations": state.get("citations", []),
            "retrieved_chunk_ids": [c["chunk_id"] for c in state.get("evidence", [])],
            "verifier_verdict": state.get("verifier_verdict", "insufficient_evidence"),
            "latency_seconds": latency,
            "langsmith_run_url": trace_url or "https://smith.langchain.com/"
        }

    def retrieval_recall(run, example):
        expected = set(example.outputs["expected_chunk_ids"])
        if not expected:
            retrieved = set(run.outputs.get("retrieved_chunk_ids", []))
            return {"key": "retrieval_recall@k", "score": 1.0 if not retrieved else 0.0}
        
        retrieved = set(run.outputs.get("retrieved_chunk_ids", []))
        if not retrieved:
            return {"key": "retrieval_recall@k", "score": 0.0}
            
        recall = len(expected.intersection(retrieved)) / len(expected)
        return {"key": "retrieval_recall@k", "score": recall}

    def retrieval_mrr(run, example):
        expected = set(example.outputs["expected_chunk_ids"])
        if not expected:
            return {"key": "retrieval_mrr", "score": 1.0}
            
        retrieved = run.outputs.get("retrieved_chunk_ids", [])
        for i, r in enumerate(retrieved):
            if r in expected:
                return {"key": "retrieval_mrr", "score": 1.0 / (i + 1)}
        return {"key": "retrieval_mrr", "score": 0.0}
        
    def faithfulness(run, example):
        if example.outputs["type"] == "unsupported":
            return {"key": "faithfulness", "score": 1.0}
            
        verdict = run.outputs.get("verifier_verdict", "insufficient_evidence")
        score_map = {"supported": 1.0, "partially_supported": 0.5, "conflicting_evidence": 1.0, "insufficient_evidence": 0.0}
        return {"key": "faithfulness", "score": score_map.get(verdict, 0.0)}

    def answer_relevance(run, example):
        q = example.inputs["question"]
        a = run.outputs.get("answer", "")
        prompt = f"Question: {q}\nAnswer: {a}\nDoes the answer address the question? Return strictly JSON: {{\"score\": 1.0}} or {{\"score\": 0.0}}."
        try:
            res = json.loads(get_judge_llm(prompt))
            return {"key": "answer_relevance", "score": float(res.get("score", 0.0))}
        except:
            return {"key": "answer_relevance", "score": 0.0}

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

    evaluators = [retrieval_recall, retrieval_mrr, faithfulness, answer_relevance, correctness, citation_precision]
    
    # We collect results manually from evaluate iterator
    experiment_results = evaluate(
        predict,
        data=dataset_name,
        evaluators=evaluators,
        experiment_prefix=args.tag,
        max_concurrency=1
    )
    
    results = []
    summary_metrics = {}
    type_metrics = {}
    total_latency = 0.0
    
    import collections
    type_counts = collections.Counter()
    
    for r in experiment_results:
        run = r["run"]
        example = r["example"]
        eval_res = r["evaluation_results"]
        
        scores = {}
        for e in eval_res["results"]:
            scores[e.key] = e.score
            
        q_type = example.outputs["type"]
        
        results.append({
            "question_id": example.inputs["question_id"],
            "answer": run.outputs.get("answer", ""),
            "citations": run.outputs.get("citations", []),
            "retrieved_chunk_ids": run.outputs.get("retrieved_chunk_ids", []),
            "verifier_verdict": run.outputs.get("verifier_verdict", "insufficient_evidence"),
            "scores": scores,
            "latency_seconds": run.outputs.get("latency_seconds", 0.0),
            "langsmith_run_url": run.outputs.get("langsmith_run_url", "https://smith.langchain.com/")
        })
        
        total_latency += run.outputs.get("latency_seconds", 0.0)
        type_counts[q_type] += 1
        
        for k, v in scores.items():
            if v is None:
                print(f"WARNING: Evaluator '{k}' failed on question '{example.inputs.get('question_id', 'unknown')}'. Treating score as 0.0.")
                v = 0.0
            summary_metrics[k] = summary_metrics.get(k, 0) + v
            if q_type not in type_metrics:
                type_metrics[q_type] = {}
            type_metrics[q_type][k] = type_metrics[q_type].get(k, 0) + v
            
    n = len(results)
    if n > 0:
        for k in summary_metrics:
            summary_metrics[k] /= n
            
        for q_type, metrics in type_metrics.items():
            for k in metrics:
                metrics[k] /= type_counts[q_type]
            
    from kestrel.llm import LLMConfig
    cfg = LLMConfig.from_env()
    
    summary = {
        "aggregate": summary_metrics,
        "breakdown": type_metrics,
        "total_token_usage": 0, 
        "total_wall_clock_time": total_latency,
        "generation_model": cfg.model if cfg.configured else "unknown",
        "embedding_model": "BAAI/bge-small-en-v1.5"
    }
    
    try:
        from kestrel.llm import LLMClient
        client = LLMClient()
        if client.last_usage:
            summary["total_token_usage"] = client.last_usage.get("total_tokens", 0)
    except Exception:
        pass
        
    with open(os.path.join(args.out_dir, "eval_results.jsonl"), "w", encoding="utf-8") as f:
        for res in results:
            f.write(json.dumps(res) + "\n")
            
    with open(os.path.join(args.out_dir, "metrics_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

if __name__ == "__main__":
    main()
