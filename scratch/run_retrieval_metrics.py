import json
from collections import defaultdict
from kestrel.retrieval import Retriever

def compute_mrr(retrieved_ids, expected_ids):
    for i, rid in enumerate(retrieved_ids):
        if rid in expected_ids:
            return 1.0 / (i + 1)
    return 0.0

def compute_recall(retrieved_ids, expected_ids):
    if not expected_ids:
        return 0.0
    hits = sum(1 for eid in expected_ids if eid in retrieved_ids)
    return hits / len(expected_ids)

def run():
    questions = []
    with open("results/eval_questions.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))
                
    retriever = Retriever()
    
    results = {
        "baseline": {"total_mrr": 0, "total_recall": 0, "count": 0, "by_type": defaultdict(lambda: {"mrr": 0, "recall": 0, "count": 0})},
        "improved": {"total_mrr": 0, "total_recall": 0, "count": 0, "by_type": defaultdict(lambda: {"mrr": 0, "recall": 0, "count": 0})}
    }
    
    for q in questions:
        expected = q["expected_chunk_ids"]
        q_type = q["type"]
        
        # Baseline (Dense)
        dense_chunks = retriever.dense_search(q["question"], k=5)
        dense_ids = [c.chunk_id for c in dense_chunks]
        d_mrr = compute_mrr(dense_ids, expected)
        d_recall = compute_recall(dense_ids, expected)
        
        results["baseline"]["total_mrr"] += d_mrr
        results["baseline"]["total_recall"] += d_recall
        results["baseline"]["count"] += 1
        results["baseline"]["by_type"][q_type]["mrr"] += d_mrr
        results["baseline"]["by_type"][q_type]["recall"] += d_recall
        results["baseline"]["by_type"][q_type]["count"] += 1
        
        # Improved (Hybrid)
        hybrid_chunks = retriever.hybrid_search(q["question"], k=5, candidates=15)
        hybrid_ids = [c.chunk_id for c in hybrid_chunks]
        h_mrr = compute_mrr(hybrid_ids, expected)
        h_recall = compute_recall(hybrid_ids, expected)
        
        results["improved"]["total_mrr"] += h_mrr
        results["improved"]["total_recall"] += h_recall
        results["improved"]["count"] += 1
        results["improved"]["by_type"][q_type]["mrr"] += h_mrr
        results["improved"]["by_type"][q_type]["recall"] += h_recall
        results["improved"]["by_type"][q_type]["count"] += 1

    # Average out
    metrics = {"baseline": {"overall": {}, "by_type": {}}, "improved": {"overall": {}, "by_type": {}}}
    
    for strategy in ["baseline", "improved"]:
        count = results[strategy]["count"]
        metrics[strategy]["overall"] = {
            "mrr": results[strategy]["total_mrr"] / count if count else 0,
            "recall_at_5": results[strategy]["total_recall"] / count if count else 0
        }
        for qt, stats in results[strategy]["by_type"].items():
            metrics[strategy]["by_type"][qt] = {
                "mrr": stats["mrr"] / stats["count"],
                "recall_at_5": stats["recall"] / stats["count"]
            }
            
    with open("results/retrieval_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
        
    # Write markdown
    md = "# Retrieval Evaluation Comparison\n\n"
    md += "This report strictly measures retrieval quality (Dense vs. Hybrid) using local indexes, circumventing the LLM rate limits.\n\n"
    
    md += "## Overall Metrics (Top-5)\n\n"
    md += "| Strategy | MRR | Recall@5 |\n"
    md += "|----------|-----|----------|\n"
    b_mrr = metrics["baseline"]["overall"]["mrr"]
    b_rec = metrics["baseline"]["overall"]["recall_at_5"]
    i_mrr = metrics["improved"]["overall"]["mrr"]
    i_rec = metrics["improved"]["overall"]["recall_at_5"]
    
    md += f"| Baseline (Dense) | {b_mrr:.3f} | {b_rec:.3f} |\n"
    md += f"| Improved (Hybrid) | {i_mrr:.3f} | {i_rec:.3f} |\n\n"
    
    md += "## Breakdown by Question Type\n\n"
    md += "| Type | Baseline MRR | Improved MRR | Baseline Recall | Improved Recall |\n"
    md += "|------|--------------|--------------|-----------------|-----------------|\n"
    
    for qt in metrics["baseline"]["by_type"]:
        b = metrics["baseline"]["by_type"][qt]
        i = metrics["improved"]["by_type"].get(qt, {"mrr": 0, "recall_at_5": 0})
        md += f"| {qt} | {b['mrr']:.3f} | {i['mrr']:.3f} | {b['recall_at_5']:.3f} | {i['recall_at_5']:.3f} |\n"
        
    with open("results/retrieval_comparison.md", "w", encoding="utf-8") as f:
        f.write(md)
        
    print("DONE")

if __name__ == "__main__":
    run()
