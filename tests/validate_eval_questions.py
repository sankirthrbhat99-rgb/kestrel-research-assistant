import json
import sys
import os

def validate():
    corpus_file = os.path.join(os.path.dirname(__file__), "..", "corpus.jsonl")
    eval_file = os.path.join(os.path.dirname(__file__), "..", "results", "eval_questions.jsonl")
    
    # 1. Load corpus chunk_ids
    valid_chunk_ids = set()
    with open(corpus_file, "r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            valid_chunk_ids.add(data["chunk_id"])

    # 2. Check each line of eval_questions
    type_counts = {"single_hop": 0, "multi_hop": 0, "conflicting": 0, "unsupported": 0, "follow_up": 0}
    
    with open(eval_file, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                print(f"Line {i}: Invalid JSON")
                sys.exit(1)
            
            # required fields
            required = {"question_id", "question", "type", "expected_answer", "expected_chunk_ids"}
            if not required.issubset(set(row.keys())):
                print(f"Line {i}: Missing required fields. Got {list(row.keys())}")
                sys.exit(1)
                
            q_type = row["type"]
            if q_type not in type_counts:
                print(f"Line {i}: Invalid type {q_type}")
                sys.exit(1)
                
            type_counts[q_type] += 1
            
            # expected_chunk_ids validation
            if not isinstance(row["expected_chunk_ids"], list):
                print(f"Line {i}: expected_chunk_ids must be a list")
                sys.exit(1)
                
            for cid in row["expected_chunk_ids"]:
                if cid not in valid_chunk_ids:
                    print(f"Line {i}: chunk_id {cid} not found in corpus")
                    sys.exit(1)
            
            if q_type == "unsupported":
                if row["expected_answer"] is not None:
                    print(f"Line {i}: unsupported must have null expected_answer")
                    sys.exit(1)
                if len(row["expected_chunk_ids"]) > 0:
                    print(f"Line {i}: unsupported must have empty expected_chunk_ids")
                    sys.exit(1)
            else:
                if row["expected_answer"] is None:
                    print(f"Line {i}: {q_type} must have expected_answer")
                    sys.exit(1)
                    
            if q_type == "follow_up":
                if "conversation_id" not in row or "turn" not in row:
                    print(f"Line {i}: follow_up must have conversation_id and turn")
                    sys.exit(1)
            else:
                if "conversation_id" in row and row["conversation_id"] is not None:
                    print(f"Line {i}: non follow_up should not have conversation_id")
                    sys.exit(1)

    # 3. Check counts
    expected_counts = {"single_hop": 5, "multi_hop": 5, "conflicting": 3, "unsupported": 3, "follow_up": 4}
    if type_counts != expected_counts:
        print(f"Type counts mismatch: got {type_counts}, expected {expected_counts}")
        sys.exit(1)
        
    print("All validation checks passed!")

if __name__ == "__main__":
    validate()
