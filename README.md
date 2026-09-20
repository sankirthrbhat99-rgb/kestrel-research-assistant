# Kestrel Research Assistant

A multi-agent research assistant over the internal knowledge base of Kestrel Labs (a product-analytics SaaS).

## Requirements
- Python 3.11+
- Virtual environment (`venv`)

## Setup
1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your API keys.

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | `groq` or `gemini` | `groq` |
| `LLM_MODEL` | The model string for generation | `openai/gpt-oss-120b` (for Groq) |
| `GROQ_API_KEY` | Groq API Key | (Required if using Groq) |
| `LANGSMITH_TRACING` | Set to `true` to enable tracing | `true` |
| `LANGSMITH_API_KEY` | LangSmith API Key | (Required) |
| `LANGSMITH_PROJECT` | LangSmith Project Name | `kestrel-research-assistant` |
| `KESTREL_STRATEGY` | Retrieval strategy (`dense`, `bm25`, `hybrid`) | `hybrid` |

## Models Used
- **Generation:** Groq (`openai/gpt-oss-120b`)
- **Embedding:** Local Sentence Transformers (`BAAI/bge-small-en-v1.5`)

## One-Command Run
To ingest the corpus and run the evaluation suite end-to-end:
```bash
./run.sh
```
*(On Windows PowerShell, use `.\run.ps1`)*

To run the Streamlit UI:
```bash
streamlit run app.py
```

## Viewing Traces
LangSmith tracing is fully integrated. If `LANGSMITH_TRACING=true` and your API key is set, you can view the complete tree of every request at:
[LangSmith Dashboard](https://smith.langchain.com/) under the project `kestrel-research-assistant`. Each node of the LangGraph execution (router, retriever, synthesiser, verifier, finaliser) appears as a child span.

## Repo Layout
- `kestrel/`: Core library (agents, state, graph, llm, retrieval, config).
- `app.py`: Streamlit UI application.
- `eval/`: Evaluation harness (`run_eval.py`).
- `results/`: Evaluation results and artifacts.
- `docs/`: Design and reflection documentation.
- `index/`: Generated Chroma DB and BM25 persistent indexes (ignored by git).
- `corpus.jsonl`: The read-only source of truth for all documents.

## Corpus Note
The `corpus.jsonl` file remains completely unchanged from its original state.
Its SHA-256 hash is:
`b401a4f906446f4e93f1d58c714918acf40d94d81a80c6358e5b7edd46cbbb41`
