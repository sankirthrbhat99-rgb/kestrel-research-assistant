import json
import sys
from typing import Any
from kestrel.state import make_initial_state, VerifiedClaim
from kestrel.agents import route_after_verifier, verifier_node
from kestrel.graph import build_graph, get_graph

def run_tests():
    print("Testing graph compilation...")
    try:
        g = get_graph()
        print("Graph compiled successfully.")
    except Exception as e:
        print(f"Graph compilation failed: {e}")
        sys.exit(1)

    print("Testing route_after_verifier...")
    state1 = make_initial_state("test")
    state1["verification_verdict"] = "insufficient_evidence"
    state1["retries"] = 0
    route1 = route_after_verifier(state1)
    print(f"Route with retries=0, insufficient_evidence: {route1}")
    assert route1 == "retriever", "Failed retries=0 route"

    state2 = make_initial_state("test")
    state2["verification_verdict"] = "insufficient_evidence"
    state2["retries"] = 1
    route2 = route_after_verifier(state2)
    print(f"Route with retries=1, insufficient_evidence: {route2}")
    assert route2 == "finaliser", "Failed retries=1 route"

    state3 = make_initial_state("test")
    state3["verification_verdict"] = "supported"
    state3["retries"] = 0
    state3["verified_claims"] = [
        {"claim": "a", "verdict": "supported", "chunk_ids": [], "reason": ""},
        {"claim": "b", "verdict": "insufficient_evidence", "chunk_ids": [], "reason": ""}
    ]
    route3 = route_after_verifier(state3)
    print(f"Route with retries=0, unsupported_claim: {route3}")
    assert route3 == "retriever", "Failed unsupported claim route"
    
    state4 = make_initial_state("test")
    state4["verification_verdict"] = "supported"
    state4["retries"] = 1
    state4["verified_claims"] = [
        {"claim": "a", "verdict": "supported", "chunk_ids": [], "reason": ""},
        {"claim": "b", "verdict": "insufficient_evidence", "chunk_ids": [], "reason": ""}
    ]
    route4 = route_after_verifier(state4)
    print(f"Route with retries=1, unsupported_claim: {route4}")
    assert route4 == "finaliser", "Failed retries=1 unsupported claim route"

    print("All route tests passed!")

if __name__ == "__main__":
    run_tests()
