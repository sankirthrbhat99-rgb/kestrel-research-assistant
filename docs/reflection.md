# Reflection

## Trade-offs and Observations

1. **Local Embeddings vs Hosted APIs:** By keeping embeddings local (`bge-small-en-v1.5`), we eliminated latency issues related to network requests and API rate limits during ingestion. However, this forced the initial ingestion to run entirely on the local CPU, which took noticeable wall-clock time and slightly constrained the semantic complexity of searches.
2. **Sequential Agent Calls:** The choice to enforce sequential LLM calls (due to rate limits) dramatically improved stability but sacrificed latency. End-to-end question answering regularly took between 30 to 60 seconds (as seen in the baseline `metrics_summary.json` latency averages), and occasionally longer when rate-limit backoff kicked in. 
3. **Groq Daily Token Limits:** As discovered during the improved evaluation run, Groq's Tokens Per Day (TPD) limit of 200,000 for free-tier users creates a hard ceiling for continuous, un-cached CI/CD or batched evaluation loops. The evaluation blocked completely on question 8.

## What Worked
- **LangGraph State Management:** The TypedDict-based shared state was exceptionally reliable. Having explicit bounds on what each agent reads and writes prevented cross-talk and made tracing trivial.
- **Offline Fallbacks:** Defining heuristic offline paths for every agent allowed us to test the entire application topology and UI without constantly spending tokens or waiting on network I/O.
- **LangSmith Tracing:** The built-in integration between LangGraph and LangSmith meant that zero extra effort was needed to trace complicated cyclical loops, such as the Verifier kicking back to the Retriever. 

## What Didn't
- **Evaluation Turn-Around Time:** Because the free-tier API forced sequential queries and frequently demanded exponential backoff, iterating on prompt engineering based on full 20-question evaluation runs proved painfully slow. The TPD limit actively prevented a complete "improved" run.

## Next Steps
1. **Implement Semantic Cache:** Add a local caching layer (e.g., Redis or a simple SQLite store) for LLM queries to bypass rate limits during repetitive evaluation or testing.
2. **Context Window Optimization:** The currently returned chunk payloads include large swathes of text. Trimming these down to exact relevant sentences before passing them to the Synthesiser would significantly reduce token usage and improve Groq throughput.
3. **Multi-query Expansion Strategy:** Implement query rewriting inside the Retriever (or Router) to explicitly formulate both a keyword search and a semantic search independently based on the user's input, rather than just fusing the raw string.
4. **Agent Parallelization:** Once a paid API tier is accessible, redesign the graph to allow the Verifier to check distinct claims in parallel to dramatically cut down wall-clock latency.
