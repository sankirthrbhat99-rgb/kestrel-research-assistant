# Kestrel Research Assistant

A multi-agent research assistant that answers questions using the internal knowledge base of Kestrel Labs, a product-analytics SaaS.

The system combines hybrid retrieval, multi-agent orchestration, answer synthesis, citation verification, and LangSmith observability to produce grounded and auditable responses.

## Features

- Multi-agent research workflow built with LangGraph.
- Hybrid retrieval using dense embeddings and BM25.
- Evidence-based answer synthesis.
- Citation verification and support checking.
- Verifier retry mechanism for insufficient or unsupported evidence.
- LangSmith tracing for agent execution and retrieval calls.
- Command-line interface for interactive questions.
- Streamlit interface for conversational interaction.
- Evaluation pipeline with retrieval and answer-quality metrics.
- Support for unsupported questions and insufficient evidence.
- Local corpus indexing using Sentence Transformers and BM25.

## Requirements

- Python 3.11 or newer
- Python virtual environment
- Groq API key
- LangSmith API key for tracing and evaluation

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/sankirthrbhat99-rgb/kestrel-research-assistant.git
cd kestrel-research-assistant
2. Create a virtual environment
python -m venv .venv

Windows PowerShell:

.\.venv\Scripts\Activate.ps1

macOS/Linux:

source .venv/bin/activate
3. Install dependencies
pip install -r requirements.txt
4. Configure environment variables

Copy the example environment file:

Windows PowerShell:

Copy-Item .env.example .env

macOS/Linux:

cp .env.example .env

Open .env and configure the required API keys and settings.

Environment Variables
Variable	Description	Default
LLM_PROVIDER	LLM provider (groq or gemini)	groq
LLM_MODEL	Model used for generation	openai/gpt-oss-120b
GROQ_API_KEY	Groq API key	Required for Groq
LANGSMITH_TRACING	Enables LangSmith tracing	true
LANGSMITH_API_KEY	LangSmith API key	Required for tracing
LANGSMITH_PROJECT	LangSmith project name	kestrel-research-assistant
KESTREL_STRATEGY	Retrieval strategy (dense, bm25, or hybrid)	hybrid

Never commit your .env file or expose API keys in the repository.

Models Used
Generation
Provider: Groq
Model: openai/gpt-oss-120b
Embeddings
Model: BAAI/bge-small-en-v1.5
Execution: Local Sentence Transformers model
Architecture

The research assistant follows a multi-stage workflow:

Router
Determines the appropriate processing path for the user's question.
Retriever
Searches the internal knowledge base using the configured retrieval strategy.
Synthesizer
Produces a draft answer using the retrieved evidence.
Verifier
Checks whether the claims in the draft are supported by the retrieved source material and citations.
Retry and Refinement
If the evidence is insufficient, the system can refine the query and perform one additional retrieval attempt.
Finalizer
Removes or rephrases unsupported claims and prepares the final response.

LangSmith tracing provides visibility into the execution of the workflow and its individual components.

Running the Application
One-command execution

macOS/Linux:

./run.sh

Windows PowerShell:

.\run.ps1

The execution script is intended to prepare the local indexes and run the evaluation workflow.

Command-line interface
python -m kestrel.chat
Streamlit interface
streamlit run app.py
Evaluation

The evaluation pipeline supports:

Retrieval Recall@K
Mean Reciprocal Rank (MRR)
Citation Precision
Faithfulness
Answer Relevance
Correctness
Latency tracking
LangSmith run URLs
Verifier verdict tracking

Evaluation outputs are stored in the results/ directory.

The repository also contains retrieval comparison results documenting changes between the baseline and improved retrieval configurations.

LangSmith Observability

LangSmith tracing is integrated into the application.

To enable tracing, configure the relevant LangSmith environment variables in .env:

LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_PROJECT=kestrel-research-assistant

Traces can be viewed in the LangSmith dashboard under the project:

kestrel-research-assistant

The workflow provides visibility into retrieval and agent execution, including:

Router
Retriever
Synthesizer
Verifier
Finalizer
Repository Structure
.
├── kestrel/
│   ├── agents/
│   ├── config.py
│   ├── graph.py
│   ├── llm.py
│   ├── retrieval.py
│   └── state.py
│
├── eval/
│   └── run_eval.py
│
├── results/
│   ├── eval_questions.jsonl
│   ├── eval_results.jsonl
│   ├── metrics_summary.json
│   └── retrieval_comparison.md
│
├── docs/
│   ├── design documentation
│   └── reflection documentation
│
├── tests/
├── app.py
├── corpus.jsonl
├── requirements.txt
├── run.sh
├── run.ps1
├── .env.example
└── README.md
Corpus Integrity

The corpus.jsonl file is treated as the read-only source of truth for the knowledge base.

The corpus SHA-256 hash is:

b401a4f906446f4e93f1d58c714918acf40d94d81a80c6358e5b7edd46cbbb41
Security
API keys must be stored in .env.
.env must not be committed to Git.
Generated indexes and virtual environments should remain excluded from version control.
Do not expose credentials in logs, screenshots, or evaluation artifacts.
License

This project was developed as part of the Kestrel Research Assistant assignment.


### Before replacing your README

Run this in Antigravity's terminal to verify the configuration names:

```powershell
Get-Content .\kestrel\config.py
