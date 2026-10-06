# 📡 Datasheet RAG Agent

Ask questions about an electronic component datasheet (PDF). A **ReAct agent** running on **Groq** (free tier) searches the datasheet, reasons step by step, does any arithmetic with a calculator tool, and answers in three parts:

* **Answer:** the value, unit and conditions
* **Explanation:** what it means in plain engineering language
* **Equations:** rendered with LaTeX, with every symbol explained, when an equation applies

Every fact is cited as `[REF-n: TYPE pX]`. You can open each source excerpt, and see every step the agent took.

## Features

* PDF parsing with PyMuPDF: text, tables, table rows/pins, equations, figures
* Structural + recursive chunking with parent context and overlap
* Hybrid retrieval: semantic (nomic-embed-text, runs inside the app) + fuzzy + section/context/metadata bonuses
* ReAct agent with tool calling: `search_datasheet`, `read_page`, `calculate`
* Quick mode: one LLM call, for simple lookups
* Citations rewritten to their true labels; invented citations are flagged
* Answers rendered as Markdown + LaTeX (safe: no raw HTML)
* Retrieval/answer metrics, token usage and latency per question
* Free: Groq free tier + Streamlit Community Cloud, no credit card

## How it works

```text
PDF ─► PyMuPDF ─┬─ text ─► sections ─► recursive chunks (+ breadcrumb, overlap)
                ├─ tables ─► table + row/pin nodes
                ├─ equations ─► equation nodes
                └─ figures ─► image files (browse tab)
                         │
                         ▼
          in-app embeddings (nomic-embed-text-v1.5) ─► local index (cached)

Question ─► hybrid retrieval (local, milliseconds) ─► initial excerpts
                                                        │
                         ┌──────────────────────────────┘
                         ▼
        ReAct agent on Groq (openai/gpt-oss-120b)
          Thought ─► Action ─► Observation ─► … (max 3 tool rounds)
          tools: search_datasheet · read_page · calculate
                         │
                         ▼
        Answer / Explanation / Equations (LaTeX) with [REF-n] citations
                         │
                         ▼
        citation check ─► sources ─► metrics ─► Streamlit UI
```

**Why retrieval-first?** The app's own search runs *before* the first Groq call, so the agent starts with good evidence. Most questions are answered in 1–2 Groq calls, which is fast and stays inside the free tier's ~8,000 tokens/minute.

## Run locally

```bash
git clone https://github.com/<you>/datasheet-rag-agent.git
cd datasheet-rag-agent
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate        # Linux / macOS
pip install -r requirements.txt
copy .env.example .env           # Windows (cp on Linux/macOS), then put your GROQ_API_KEY in .env
streamlit run app.py
```

Get a free Groq key at **https://console.groq.com/keys**. No credit card is needed.

## Deploy for free

See **[`DEPLOY.md`](DEPLOY.md)** for step-by-step instructions on Streamlit Community Cloud.

## Configuration

Set these in `.env` locally, or in **Secrets** on Streamlit Cloud. Only `GROQ_API_KEY` is required.

| Setting | Default | Meaning |
|---|---|---|
| `GROQ_API_KEY` | (none) | Your free Groq key (secret) |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Model; `openai/gpt-oss-20b` is faster |
| `AGENT_MODE` | `agent` | `agent` (ReAct, most accurate) or `quick` (one call) |
| `AGENT_MAX_STEPS` | `3` | Max tool rounds before the agent must answer |
| `MAX_UPLOAD_MB` / `MAX_PAGES` | `25` / `300` | Upload limits |

The sidebar's **⚙ Configuration** panel changes the mode, model and agent rounds for your session.

## Limits (free tier)

* Groq free plan: about 30 requests/min, 1,000 requests/day and 8,000 tokens/min per model (see console.groq.com/settings/limits). A typical question uses 1,000–2,500 tokens.
* Streamlit Community Cloud: apps sleep after 12 h without visitors; storage resets on restart.
* Figure reading with a vision model is not included: no vision model is on Groq's free plan. Figures are still extracted and viewable.
* Datasheet excerpts are sent to Groq to generate answers. Don't use confidential documents.

## Project structure

```text
app.py                  Streamlit entry point
config/settings.py      settings from env / Streamlit secrets
rag/
  pdf_parser.py         PDF → nodes (text, tables, equations, figures)
  chunking.py           structural + recursive chunking
  table_extractor.py    tables → table + row/pin nodes
  equation_extractor.py equation / spec lines
  figure_extractor.py   images
  metadata.py           electrical parameter metadata
  embeddings.py         in-app nomic embeddings (fastembed)
  retrieval.py          hybrid scoring (semantic + fuzzy + bonuses)
  tools.py              agent tools + source registry
  agent.py              ReAct loop + answer format prompt
  llm.py                Groq client, friendly errors
  evaluation.py         metrics
  pipeline.py           indexing + question answering
storage/                cache, local vector store, feedback
ui/                     Streamlit components and styles
```
