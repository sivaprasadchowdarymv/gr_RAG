# RAG∞ Pro: Adaptive Multimodal Agentic RAG

Ask questions about datasheets, papers and technical PDFs. RAG∞ Pro reads text, tables, equations and figures locally. Specialist agents gather evidence, one master agent writes a cited answer, and a verifier checks it before you see it.

```text
USER → CHAT UI → ORCHESTRATOR → specialist agents (text · table · equation · figure · document)
     → hybrid retrieval (semantic + fuzzy + BM25) → cross-encoder reranking → evidence fusion
     → MASTER AGENT (ReAct when needed) → VERIFICATION AGENT → answer with [REF-n] citations
     → 👍/👎 feedback → preference adaptation          (+ metrics & latency at every stage)
```

**Free-first:** Groq's and Ollama Cloud's free plans work without a credit card. Everything except answer generation runs inside the app: PDF parsing, embeddings, BM25, reranking, routing and verification.

## Features

| Area | What you get |
|---|---|
| Documents | Multiple PDFs at once; text, tables (TBL_n), equations with variables, units and context (EQ_n), figures with per-image captions (FIG_n), document metadata, scanned-page detection |
| Retrieval | Original hybrid scorer (nomic embeddings + fuzzy + section/context/metadata bonuses) + BM25 + cross-encoder reranker, fused with Reciprocal Rank Fusion |
| Agents | Rule-based orchestrator (about 1 ms) runs only the agents a question needs; one master agent; ReAct tools (`search_datasheet`, `read_page`, `calculate`) only for calculations, comparisons and equations |
| Answers | **Answer / Explanation / Equations** (LaTeX); every fact cited `[REF-n: TYPE pX]`; citations rewritten to their true labels |
| Verification | Zero-token checks: citation precision and coverage, numbers vs evidence (mA↔A aware), equation symbols; one bounded regeneration; optional LLM check |
| Chat | Multiple conversations, bounded memory, follow-ups, regenerate, copy, Markdown export |
| Metrics | Faithfulness, relevance, citation precision/coverage, grounding, stage latency, tokens, per-agent stats, composite health score; benchmark mode for P@K, R@K, Hit rate, MRR |
| Learning | 👍/👎 + reasons, preference profile injected into the prompt, DPO-ready dataset export |
| Providers | Groq, Ollama Cloud, local Ollama; model roles (master/fast/verifier/vision); fallback only to providers you enabled |
| UI | Six pages (Chat, Documents, Metrics, Agent Activity, Preferences, Settings); light and dark theme |

## Quick start (local)

```bash
git clone https://github.com/<you>/gr_RAG.git
cd gr_RAG
python -m venv venv
venv\Scripts\activate              # Windows   (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env             # Windows   (Linux/macOS: cp .env.example .env)
#   put GROQ_API_KEY and/or OLLAMA_API_KEY in .env
streamlit run app.py
```

On first use the app downloads two small models once: the nomic embedding model (~130 MB) and the reranker (~80 MB).

## Providers and keys

| Provider | Key | Default models (master / fast) | Notes |
|---|---|---|---|
| Groq | `GROQ_API_KEY` from console.groq.com/keys | `openai/gpt-oss-120b` / `openai/gpt-oss-20b` | Free plan: about 30 req/min, 1,000 req/day, 8K tokens/min per model |
| Ollama Cloud | `OLLAMA_API_KEY` from ollama.com/settings/keys | `gpt-oss:120b` / `gpt-oss:20b` | Free plan has usage limits; models that need a paid plan are skipped (HTTP 402) |
| Local Ollama | none; set `ENABLE_OLLAMA_LOCAL=true` | `mistral` / `mistral`, vision `llava:7b` | Only where Ollama runs next to the app |

**Free-first / zero-billing safety.**
* A provider is called only if it has a key (or is explicitly enabled) **and** is listed in `LLM_PROVIDERS`.
* Fallback walks that list in order.
* Every answer shows which provider and model produced it.

The app cannot see your billing plan: use free-plan keys and no paid usage is possible.

Override models with `MASTER_MODEL`, `FAST_MODEL`, `VERIFIER_MODEL`, `VISION_MODEL` (these apply to the first provider), or per provider, e.g. `GROQ_MASTER_MODEL`. The full list of settings is in `.env.example`.

## Using it

1. **Documents:** upload one or more PDFs. Each card shows pages, equations, figures and tables. Toggle **Use in chat**.
2. **Chat:** ask questions. Open **Evidence** to see the exact excerpts, figure previews included, and **Agent activity** for the stages and tool actions. Use 👍/👎 (with a reason) and **Regenerate**.
3. **Agent Activity:** the plan, which agents ran or were skipped, latency per stage, and the verification report.
4. **Metrics:** averages across answers, latency by stage, agent statistics, feedback, and the benchmark.
5. **Preferences:** answer length, depth, equations and tables, plus automatic changes from feedback and the DPO export.
6. **Settings:** provider status, master model, Pro/Legacy pipeline, Agent/Quick mode, reranking, verifier, memory, health weights.

## Metrics: what they mean

* **Faithfulness / context coverage:** word-overlap heuristics between the answer, the evidence and the question.
* **Answer relevance:** embedding similarity between question and answer.
* **Citation precision:** the share of citations that point to real evidence. **Citation coverage:** the share of factual paragraphs with a citation.
* **Numerical / equation grounding:** the share of numbers and equation symbols found in the evidence.
* **RAG health score:** a weighted composite (`HEALTH_WEIGHTS`). It is an **application-level monitoring aid**, not a scientific measure of correctness.
* **Precision@K, Recall@K, Hit rate, MRR:** these need ground truth, so they are computed in benchmark mode:
  ```bash
  python -m metrics.benchmark --pdf your.pdf --questions benchmark/sample_questions.json [--answers]
  ```

## Feedback and learning

👍/👎 and reasons are stored in `data/learning/feedback.jsonl`. Simple, visible rules adapt a preference profile; for example, "too long" makes answers shorter. This is **preference adaptation, not RLHF**. Pairs of answers to the same question (one liked, one disliked) can be exported for future DPO training:

```bash
python -m learning.dpo_dataset data/learning/feedback.jsonl dpo.jsonl
```

## Legacy mode

The previous single-agent pipeline is kept for comparison. Choose **Legacy** in Settings, or set `PIPELINE_MODE=legacy` (or `LEGACY_MODE=true`).

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```

43 offline tests cover ingestion, retrieval, routing, agents, master, verification, citations, providers and fallback, chat, feedback, preferences, DPO export and the benchmark. They use fake Groq/Ollama servers and stand-in models (`tests/fakes/`), so they need no keys or downloads.

## Limitations (honest)

* **No OCR.** Scanned pages are detected and flagged, not read: Tesseract isn't available on Streamlit Cloud.
* **Figure understanding beyond captions and nearby text needs a vision model** (`VISION_MODEL`). None is on Groq's free plan.
* **Free tiers have rate limits.** Use Quick mode or a smaller master model if you hit them.
* **Equation extraction reads equations as text lines** (e.g. `PD = (VIN - VOUT) x IOUT`). Typeset math that a PDF stores as graphics isn't recovered.
* **The included benchmark report uses a synthetic datasheet and stand-in models.** Rerun it on your own PDFs.

See [ARCHITECTURE.md](ARCHITECTURE.md), [DEPLOYMENT.md](DEPLOYMENT.md) and [ARCHITECTURE_AUDIT.md](ARCHITECTURE_AUDIT.md).
