"""The six workspace pages: Chat, Documents, Metrics, Agent Activity, Preferences, Settings."""
from __future__ import annotations

import json
import statistics
from typing import Dict, List

import pandas as pd
import streamlit as st

from agents.rag_pro import answer_pro
from chat.conversations import result_from_dict
from learning.dpo_dataset import build_pairs
from learning.feedback import REASONS
from learning.preferences import DEPTHS, LENGTHS, Preferences
from llm.model_router import DEFAULT_MODELS
from metrics.benchmark import to_markdown
from metrics.rag_metrics import health_score
from rag.models import AgentStep, QueryResult
from rag.pdf_parser import PdfProcessingError
from rag.pipeline import answer_query, clear_cache, get_index
from storage.cache import compute_doc_id
from ui import state, widgets

MAX_QUESTION_CHARS = 1000


# =============================================================================
# Answering
# =============================================================================
def ask(question: str, conv, on_step) -> QueryResult:
    s = state.settings()
    indexes = state.active_indexes()
    if s.pipeline_mode == "legacy":  # previous single-agent pipeline (Groq only, one document)
        result = answer_query(question, indexes[0], s, on_step=on_step)
        if len(indexes) > 1:
            result.warnings.append("Legacy mode answers from the first active document only.")
        return result
    return answer_pro(question, indexes, s, state.router(), memory=conv.memory(s.memory_turns),
                      previous_question=conv.last_question(), preferences=state.preferences().load().to_prompt(),
                      on_step=on_step)


def _run_with_status(question: str, conv) -> QueryResult:
    with st.status("Working…", expanded=True) as box:
        def on_step(step: AgentStep) -> None:
            if step.kind in ("stage", "action", "note"):
                box.write(("✓ " if step.kind == "stage" else "🔧 ") + widgets.describe_step(step))
        result = ask(question, conv, on_step)
        box.update(label=f"Done in {result.latency} s", state="complete", expanded=False)
    st.session_state["last_result"] = result
    return result


# =============================================================================
# Chat
# =============================================================================
def _conversation_sidebar(conv) -> None:
    store = state.conversations()
    with st.sidebar:
        st.markdown("#### 💬 Conversations")
        if st.button("➕ New chat", use_container_width=True):
            new = store.create([i.doc_id for i in state.active_indexes()])
            st.session_state["conv_id"] = new.id
            st.rerun()
        convs = store.list()[:30]
        ids = [c.id for c in convs]
        if conv.id in ids:
            pick = st.radio("History", ids, index=ids.index(conv.id), label_visibility="collapsed",
                            format_func=lambda cid: next(c.title for c in convs if c.id == cid))
            if pick != conv.id:
                st.session_state["conv_id"] = pick
                st.rerun()
        c1, c2 = st.columns(2)
        c1.download_button("Export", store.export_markdown(conv), file_name=f"chat_{conv.id}.md",
                           mime="text/markdown", use_container_width=True)
        if c2.button("Delete", use_container_width=True):
            store.delete(conv.id)
            st.session_state.pop("conv_id", None)
            st.rerun()


def _feedback_widget(conv, msg, question: str) -> None:
    if msg.feedback:
        st.caption("Thanks for the feedback: " + ("👍" if msg.feedback["rating"] > 0 else "👎")
                   + (f" ({', '.join(msg.feedback['reasons'])})" if msg.feedback.get("reasons") else ""))
        return
    rating = st.feedback("thumbs", key=f"fb_{msg.id}")
    if rating is None:
        return
    reasons, comment = [], ""
    if rating == 0:
        reasons = st.multiselect("What went wrong?", REASONS, key=f"fbr_{msg.id}")
        comment = st.text_input("Comment (optional)", key=f"fbc_{msg.id}", max_chars=500)
    if st.button("Submit feedback", key=f"fbs_{msg.id}"):
        r = msg.result or {}
        state.feedback().record(conversation_id=conv.id, message_id=msg.id, question=question, answer=msg.content,
                                rating=1 if rating == 1 else -1, reasons=reasons, comment=comment,
                                provider=r.get("provider", ""), model=r.get("model", ""), metrics=r.get("metrics", {}))
        msg.feedback = {"rating": 1 if rating == 1 else -1, "reasons": reasons, "comment": comment}
        state.conversations().save(conv)
        changes = state.preferences().apply_feedback(1 if rating == 1 else -1, reasons)
        st.toast("Feedback saved." + (" Preferences updated: " + "; ".join(changes) if changes else ""))
        st.rerun()


def chat_page() -> None:
    widgets.brand()
    s = state.settings()
    conv = state.current_conversation()
    _conversation_sidebar(conv)
    if not state.active_indexes():
        st.info("Add a PDF on the **Documents** page to start chatting.")
        st.page_link(st.session_state["pages"]["documents"], label="Go to Documents", icon="📄")
        return
    names = ", ".join(i.filename for i in state.active_indexes())
    st.caption(f"Answering from: {names} · {'Legacy pipeline' if s.pipeline_mode == 'legacy' else 'RAG∞ Pro pipeline'}"
               f" · {'ReAct agent' if s.agent_mode == 'agent' else 'Quick'} mode")

    last_q = ""
    assistants = [m for m in conv.messages if m.role == "assistant"]
    for msg in conv.messages:
        with st.chat_message(msg.role):
            if msg.role == "user":
                last_q = msg.content
                st.markdown(msg.content)
                continue
            result = result_from_dict(msg.result) if msg.result else QueryResult("answer", msg.content)
            widgets.render_result(result, s)
            cols = st.columns([1, 1, 4])
            with cols[0].popover("Copy"):
                st.code(msg.content, language="markdown")
            if msg is assistants[-1] and cols[1].button("Regenerate", key=f"regen_{msg.id}"):
                new = _run_with_status(last_q, conv)
                state.conversations().replace_answer(conv, msg.id, new)
                st.rerun()
            _feedback_widget(conv, msg, last_q)

    question = st.chat_input("Ask about your documents…", max_chars=MAX_QUESTION_CHARS)
    if question and question.strip():
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            result = _run_with_status(question.strip(), conv)
        state.conversations().add_exchange(conv, question.strip(), result)
        st.rerun()


# =============================================================================
# Documents
# =============================================================================
def documents_page() -> None:
    widgets.brand()
    st.subheader("Documents")
    s = state.settings()
    uploads = st.file_uploader("Add PDFs", type=["pdf"], accept_multiple_files=True,
                               help=f"Up to {s.max_upload_mb} MB and {s.max_pages} pages each.")
    for up in uploads or []:
        data = up.getvalue()
        try:
            doc_id = compute_doc_id(data)
        except ValueError:
            continue
        if doc_id in state.docs():
            continue
        bar = st.progress(0.0, text=f"Indexing {up.name}…")
        try:
            index, warnings = get_index(data, up.name, s, progress=lambda f, m: bar.progress(min(max(f, 0.0), 1.0), text=m))
            state.add_doc(index)
            for w in warnings:
                st.warning(w)
        except PdfProcessingError as exc:
            st.error(f"{up.name}: {exc.user_message}")
        finally:
            bar.empty()

    if not state.docs():
        st.info("No documents yet. Upload one or more PDFs above. Indexing happens once per file.")
        return
    cols = st.columns(2)
    for i, (doc_id, d) in enumerate(list(state.docs().items())):
        index = d["index"]
        with cols[i % 2]:
            st.markdown(widgets.doc_card(index.filename, index.stats(), index.doc_meta or {}, d["active"]),
                        unsafe_allow_html=True)
            a, b, c = st.columns(3)
            d["active"] = a.toggle("Use in chat", value=d["active"], key=f"act_{doc_id}")
            if b.button("Re-index", key=f"rx_{doc_id}"):
                clear_cache(doc_id, s)
                state.docs().pop(doc_id, None)
                st.toast("Index cleared: upload the file again to rebuild it.")
                st.rerun()
            if c.button("Remove", key=f"rm_{doc_id}"):
                state.docs().pop(doc_id, None)
                st.rerun()
            sections = (index.doc_meta or {}).get("sections") or []
            if sections:
                with st.expander("Sections"):
                    st.markdown("\n".join(f"- {t} (p{p})" for t, p in sections[:60]))


# =============================================================================
# Metrics
# =============================================================================
def _all_results() -> List[Dict]:
    rows = []
    for conv in state.conversations().list():
        for m in conv.messages:
            if m.role == "assistant" and m.result and m.result.get("metrics"):
                rows.append({"conversation": conv.title, **m.result})
    return rows


def metrics_page() -> None:
    widgets.brand()
    st.subheader("Metrics")
    s = state.settings()
    results = _all_results()
    fb = state.feedback().stats()
    if not results:
        st.info("Ask a few questions in Chat; metrics appear here.")
    else:
        df = pd.DataFrame([{**r["metrics"], "question": r.get("question", ""), "provider": r.get("provider", "")}
                           for r in results])
        mean = {k: float(df[k].mean()) for k in df.columns if df[k].dtype.kind in "fi"}
        health = health_score(mean, s.health_weights, fb["ratio"])
        st.markdown(f"**RAG health score: {health} / 100** · application-level composite of faithfulness, "
                    f"relevance, citation accuracy, grounding and user feedback (weights in Settings). "
                    "It is a monitoring aid, not a scientific measure of correctness.")
        widgets.metric_cards({"Faithfulness": mean.get("faithfulness"), "Answer relevance": mean.get("answer_relevance"),
                              "Citation precision": mean.get("citation_precision"),
                              "Citation coverage": mean.get("citation_coverage"),
                              "Numerical grounding": mean.get("numerical_score"), "Grounded rate": mean.get("grounded"),
                              "Context coverage": mean.get("context_coverage"),
                              "User 👍 rate": fb["ratio"]})
        c1, c2, c3 = st.columns(3)
        c1.metric("Answers", len(results))
        c2.metric("Avg latency", f"{mean.get('latency_s', 0):.2f} s")
        c3.metric("Avg tokens / answer", f"{mean.get('tokens', 0):.0f}")

        st.markdown("##### Latency by stage (ms, average)")
        stages: Dict[str, List[float]] = {}
        for r in results:
            for k, v in (r.get("stage_latency") or {}).items():
                if k != "total":
                    stages.setdefault(k, []).append(v)
        if stages:
            st.bar_chart(pd.Series({k: statistics.mean(v) for k, v in stages.items()}, name="ms"))

        st.markdown("##### Agents")
        agg: Dict[str, Dict[str, float]] = {}
        for r in results:
            for name in ("text_agent", "table_agent", "equation_agent", "figure_agent", "document_agent"):
                a = agg.setdefault(name, {"calls": 0, "results": 0, "failures": 0, "latency_ms": 0.0, "skipped": 0})
                st_ = (r.get("agent_stats") or {}).get(name)
                if st_:
                    for k in ("calls", "results", "failures", "latency_ms"):
                        a[k] += st_.get(k, 0)
                else:
                    a["skipped"] += 1
        st.dataframe(pd.DataFrame([{"agent": k, "calls": int(v["calls"]), "skipped": int(v["skipped"]),
                                    "results": int(v["results"]), "failures": int(v["failures"]),
                                    "success rate": f"{(1 - v['failures'] / v['calls']) * 100:.0f}%" if v["calls"] else "-",
                                    "avg latency (ms)": round(v["latency_ms"] / v["calls"], 1) if v["calls"] else 0}
                                   for k, v in agg.items()]), hide_index=True, use_container_width=True)
        with st.expander("All answers"):
            cols = [c for c in ("question", "health_score", "faithfulness", "answer_relevance", "citation_precision",
                                "citation_coverage", "numerical_score", "grounded", "latency_s", "tokens", "provider")
                    if c in df.columns]
            st.dataframe(df[cols], hide_index=True, use_container_width=True)

    st.markdown("##### User feedback")
    st.write(f"👍 {fb['up']} · 👎 {fb['down']}" + (f" · reasons: {fb['reasons']}" if fb["reasons"] else ""))

    st.markdown("##### Benchmark (legacy vs RAG∞ Pro)")
    st.caption("Upload questions with known answer pages, e.g. "
               '[{"question": "What is the peak output current?", "expected_pages": [2]}]. '
               "Retrieval-only: uses no LLM tokens.")
    qfile = st.file_uploader("Questions JSON", type=["json"], key="bench_q")
    idx = state.active_indexes()
    if qfile and idx and st.button("Run benchmark on the first active document"):
        try:
            # The PDF itself is not kept after indexing, so the benchmark runs on the index.
            rep = _benchmark_on_index(idx[0], json.loads(qfile.getvalue()), s)
            st.markdown(to_markdown(rep))
            st.download_button("Download report", to_markdown(rep), "BENCHMARK_REPORT.md")
        except (ValueError, KeyError, TypeError) as exc:
            st.error(f"Could not read the questions file ({type(exc).__name__}).")


def _benchmark_on_index(index, questions, settings) -> Dict:
    from metrics.benchmark import _legacy_pages, _pro_pages, retrieval_scores

    rows = []
    for q in questions:
        row = {"question": q["question"]}
        for name, fn in (("legacy", _legacy_pages), ("pro", _pro_pages)):
            row[name] = retrieval_scores(fn(q["question"], index, settings), q.get("expected_pages", []), 5)
        rows.append(row)
    keys = ("precision@k", "recall@k", "hit", "mrr")
    summary = {n: {k: round(statistics.mean(r[n][k] for r in rows), 3) for k in keys} for n in ("legacy", "pro")}
    return {"document": index.filename, "k": 5, "questions": len(rows), "summary": summary, "rows": rows,
            "with_answers": False, "rerank": settings.rerank}


# =============================================================================
# Agent activity
# =============================================================================
def activity_page() -> None:
    widgets.brand()
    st.subheader("Agent activity")
    result = st.session_state.get("last_result")
    if result is None:
        conv = state.current_conversation()
        last = next((m for m in reversed(conv.messages) if m.role == "assistant" and m.result), None)
        result = result_from_dict(last.result) if last else None
    if result is None:
        st.info("Ask a question in Chat to see how the agents handled it.")
        return
    st.markdown(f"**Question:** {result.question or '(legacy mode)'}")
    if result.plan:
        st.markdown("**Plan** " + " ".join(f'<span class="chip">{widgets.esc(i)}</span>' for i in result.plan.get("intents", [])),
                    unsafe_allow_html=True)
        lines = []
        for name in ("text_agent", "table_agent", "equation_agent", "figure_agent", "document_agent"):
            ran = name in result.plan.get("agents", [])
            st_ = (result.agent_stats or {}).get(name, {})
            lines.append(f"{'✓' if ran else '⏭'} {name.replace('_', ' ')}"
                         + (f": {int(st_.get('results', 0))} candidates, {st_.get('latency_ms', 0):.1f} ms" if ran else " (skipped)"))
        st.markdown("\n".join(f"- {line}" for line in lines))
        st.caption("Tools (ReAct) " + ("used" if result.plan.get("use_tools") else "not needed: one master call"))
    if result.stage_latency:
        st.markdown("**Latency by stage**")
        lat = {k: v for k, v in result.stage_latency.items() if k != "total"}
        st.dataframe(pd.DataFrame([{"stage": k, "ms": round(v, 1)} for k, v in lat.items()]
                                  + [{"stage": "TOTAL", "ms": round(result.stage_latency.get("total", 0), 1)}]),
                     hide_index=True, use_container_width=False)
    st.markdown("**Trace** (actions only; the model's internal reasoning is not shown)")
    widgets.render_trace(result.steps)
    if result.verification:
        st.markdown("**Verification**")
        st.json(result.verification)
    if result.conflicts:
        st.markdown("**Evidence notes**")
        for c in result.conflicts:
            st.write("• " + c)


# =============================================================================
# Preferences
# =============================================================================
def preferences_page() -> None:
    widgets.brand()
    st.subheader("Preferences")
    store = state.preferences()
    p = store.load()
    st.caption("Injected into the master agent's prompt. Thumbs-down reasons such as 'too long' adjust these "
               "automatically (preference adaptation, not model training).")
    with st.form("prefs"):
        length = st.select_slider("Response length", LENGTHS, value=p.response_length)
        depth = st.select_slider("Technical depth", DEPTHS, value=p.technical_depth)
        c = st.columns(4)
        cit = c[0].toggle("Citations", p.citations)
        eq = c[1].toggle("Equations", p.equations)
        fig = c[2].toggle("Figures", p.figures)
        tab = c[3].toggle("Tables", p.tables)
        if st.form_submit_button("Save"):
            store.save(Preferences(length, depth, cit, eq, fig, tab, p.history))
            st.toast("Preferences saved.")
    st.markdown("**Prompt instruction now:** " + store.load().to_prompt())
    if p.history:
        with st.expander(f"Automatic changes ({len(p.history)})"):
            for h in reversed(p.history[-20:]):
                st.write("• " + "; ".join(h["changes"]))
    st.markdown("##### Training data export (DPO)")
    pairs = build_pairs(state.feedback().all())
    st.write(f"{len(pairs)} preference pair(s) available: same question, one answer 👍 and another 👎.")
    st.download_button("Download DPO dataset (.jsonl)", "\n".join(json.dumps(x, ensure_ascii=False) for x in pairs),
                       file_name="dpo_dataset.jsonl", disabled=not pairs)


# =============================================================================
# Settings
# =============================================================================
def settings_page() -> None:
    widgets.brand()
    st.subheader("Settings")
    s = state.settings()
    st.markdown("##### AI providers (free-first)")
    st.caption("Only providers with a key (or ENABLE_OLLAMA_LOCAL=true) are ever called, in this order. "
               "Use free-plan keys: the app cannot see your billing plan and never enables a provider by itself.")
    statuses = state.provider_status()
    for p in statuses:
        if not p.configured:
            st.markdown(widgets.status_line(None, p.label, "not configured"), unsafe_allow_html=True)
        else:
            st.markdown(widgets.status_line(p.connected, p.label, f"connected, {len(p.models)} models" if p.connected
                                            else (p.message or "unavailable")), unsafe_allow_html=True)
    active = [p for p in statuses if p.configured and p.connected]
    if active:
        first = active[0]
        default = s.master_model or DEFAULT_MODELS.get(first.name, {}).get("master", "")
        options = list(dict.fromkeys([default] + first.models))
        model = st.selectbox(f"Master model ({first.label})", options, index=0)
        if model != default:
            state.set_override(master_model=model)

    st.markdown("##### Pipeline")
    c1, c2 = st.columns(2)
    pipe = c1.radio("Pipeline", ["pro", "legacy"], index=0 if s.pipeline_mode == "pro" else 1,
                    format_func=lambda x: "RAG∞ Pro (agents + verification)" if x == "pro" else "Legacy (previous version)")
    mode = c2.radio("Answer mode", ["agent", "quick"], index=0 if s.agent_mode == "agent" else 1,
                    format_func=lambda x: "ReAct agent when needed" if x == "agent" else "Quick (one call)")
    c3, c4, c5 = st.columns(3)
    rerank = c3.toggle("Cross-encoder reranking", s.rerank)
    vllm = c4.toggle("LLM verifier (extra tokens)", s.verify_with_llm)
    regen = c5.number_input("Max regenerations", 0, 2, s.max_regenerations)
    c6, c7, c8 = st.columns(3)
    steps = c6.slider("Max agent tool rounds", 1, 6, s.agent_max_steps)
    memory = c7.slider("Conversation memory (turns)", 0, 10, s.memory_turns)
    top_k = c8.slider("Top-K per retriever", 1, 10, s.top_k)
    c9, c10 = st.columns(2)
    chunk = c9.slider("Chunk size (tokens)", 100, 800, s.max_chunk_tokens, 50)
    overlap = c10.slider("Chunk overlap (tokens)", 0, 150, s.overlap_tokens, 10)
    st.caption("Changing chunk size or overlap re-indexes documents on next upload.")

    st.markdown("##### RAG health score weights")
    names = ["Faithfulness", "Relevance", "Citation accuracy", "Grounding", "User feedback"]
    wcols = st.columns(5)
    weights = [wcols[i].number_input(n, 0.0, 1.0, float(round(s.health_weights[i], 2)), 0.05) for i, n in enumerate(names)]
    total = sum(weights) or 1.0
    state.set_override(pipeline_mode=pipe, agent_mode=mode, rerank=rerank, verify_with_llm=vllm,
                       max_regenerations=int(regen), agent_max_steps=steps, memory_turns=memory, top_k=top_k,
                       max_chunk_tokens=chunk, overlap_tokens=overlap,
                       health_weights=tuple(w / total for w in weights))
    st.caption("Settings apply to this browser session. Defaults come from environment variables / Streamlit secrets.")
