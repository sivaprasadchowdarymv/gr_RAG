"""
Streamlit building blocks. Everything user-supplied (PDF text, LLM output,
file names) is HTML-escaped before it is rendered with unsafe_allow_html.

Old RAG.py equivalents: `_TYPE_ICONS`, `_make_popup()`, `render_answer()`,
`render_source_card()`, `render_metrics()`, and the sidebar / stats / browse
code inside `main()`.

The answer is rendered as Markdown (never raw HTML), so LaTeX equations
display properly and any HTML injected through a crafted PDF is shown as
plain text instead of being executed.
"""
from __future__ import annotations

import dataclasses
import html
import re
from typing import List, Optional

import pandas as pd
import streamlit as st

from config.settings import Settings
from rag.llm import LLMStatus
from rag.models import AgentStep, DocumentIndex, QueryResult

TYPE_ICONS = {
    "TEXT": "📝", "TABLE": "📊", "ROW": "🔢", "PIN": "📌", "EQUATION": "➗", "FIGURE": "🖼️", "PAGE": "📄",
}
_CITE_RE = re.compile(r"\[REF-(\d+):\s*([A-Z]+)\s*p(\d+)\]")


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


# ---------------------------------------------------------------------------
# Header & status
# ---------------------------------------------------------------------------
def render_header() -> None:
    st.markdown(
        '<div class="app-header"><div class="app-header-inner">'
        '<div class="app-title">📡 Datasheet RAG Agent</div>'
        '<div class="app-sub">A ReAct agent that searches your datasheet, reasons step by step '
        "and cites the exact page, table or equation behind every answer.</div>"
        "</div></div>",
        unsafe_allow_html=True,
    )


def _status_line(ok: Optional[bool], label: str, value: str) -> str:
    cls = "ok" if ok else ("warn" if ok is None else "bad")
    return f'<div class="status-line"><span class="dot {cls}"></span>{esc(label)}: {esc(value)}</div>'


def render_status(status: LLMStatus, settings: Settings) -> None:
    if not status.has_key:
        groq_line = _status_line(False, "Groq", "No API key")
    elif status.connected:
        groq_line = _status_line(True, "Groq", "Connected")
    else:
        groq_line = _status_line(False, "Groq", "Error")
    model_ok = status.has(settings.groq_model) if status.connected else None
    lines = [
        groq_line,
        _status_line(model_ok, "Model", settings.groq_model + ("" if model_ok or model_ok is None else " (not available)")),
        _status_line(True, "Embedding", settings.embed_model.split("/")[-1] + " (in-app)"),
        _status_line(None, "Mode", "ReAct agent" if settings.agent_mode == "agent" else "Quick"),
    ]
    st.markdown("".join(lines), unsafe_allow_html=True)
    if status.message:
        st.error(status.message)
    elif status.connected and not model_ok:
        st.warning(f"Model '{settings.groq_model}' is not available on your Groq account. "
                   "Choose another one under ⚙ Configuration.")


def render_sidebar_config(settings: Settings, status: LLMStatus) -> Settings:
    """Advanced settings; returns this session's settings."""
    with st.expander("⚙ Configuration", expanded=False):
        mode_label = st.radio(
            "Answer mode", ["ReAct agent", "Quick"], key="cfg_mode",
            index=0 if settings.agent_mode == "agent" else 1,
            help="Agent: searches again, reads pages and calculates when needed (most accurate). "
                 "Quick: one call with the top excerpts (fastest, fewest tokens).",
        )
        options = list(dict.fromkeys([settings.groq_model] + (status.models if status.connected else [])))
        model = st.selectbox("Groq model", options, index=0, key="cfg_model",
                             help="All models on Groq's free plan share the same per-minute token limit.")
        steps = st.slider("Max agent tool rounds", 1, 6, settings.agent_max_steps, key="cfg_steps",
                          help="More rounds = more thorough but more tokens.")
        top_k = st.slider("Top-K (hits per search engine)", 1, 10, settings.top_k, key="cfg_topk")
        chunk = st.slider("Chunk size (tokens)", 100, 800, settings.max_chunk_tokens, 50, key="cfg_chunk")
        overlap = st.slider("Chunk overlap (tokens)", 0, 150, settings.overlap_tokens, 10, key="cfg_overlap")
        st.caption("Changing chunk size or overlap re-indexes the document.")
    return dataclasses.replace(
        settings, agent_mode="agent" if mode_label == "ReAct agent" else "quick", groq_model=model,
        agent_max_steps=steps, top_k=top_k, max_chunk_tokens=chunk, overlap_tokens=overlap,
    )


def render_sidebar_stats(index: Optional[DocumentIndex]) -> None:
    st.markdown("#### 📊 Document statistics")
    if index is None:
        st.caption("Upload a datasheet to see its statistics.")
        return
    s = index.stats()
    rows = [("Pages", s["pages"]), ("Text chunks", s["text"]), ("Tables", s["table"]),
            ("Table rows / pins", s["row_pin"]), ("Equations", s["equation"]),
            ("Figures", s["figure"]), ("Average chunk depth", s["avg_depth"])]
    st.markdown("\n".join(f"- {k}: **{v}**" for k, v in rows))


# ---------------------------------------------------------------------------
# Document summary
# ---------------------------------------------------------------------------
def render_document_summary(index: DocumentIndex) -> None:
    s = index.stats()
    items = [("Pages", s["pages"]), ("Text chunks", s["text"]), ("Tables", s["table"]),
             ("Equations", s["equation"]), ("Figures", s["figure"])]
    stats = "".join(f"<span>{k} <b>{v}</b></span>" for k, v in items)
    st.markdown(
        f'<div class="doc-name">📄 {esc(index.filename)}</div><div class="doc-stats">{stats}</div>',
        unsafe_allow_html=True,
    )


def render_warnings(warnings: List[str]) -> None:
    for w in dict.fromkeys(warnings):  # de-duplicated, order kept
        st.warning(w)


# ---------------------------------------------------------------------------
# Answer with citation popups
# ---------------------------------------------------------------------------
def format_answer_markdown(answer: str) -> str:
    """Markdown (with LaTeX) where citations become highlighted badges."""
    def _badge(m: "re.Match[str]") -> str:
        return f":blue-background[REF-{m.group(1)} · {m.group(2)} p{m.group(3)}]"
    return _CITE_RE.sub(_badge, answer or "")


def render_answer(result: QueryResult) -> None:
    st.markdown("### Answer")
    if result.kind == "feedback_override":
        st.info("Saved answer: this question has a human-provided answer.")
    with st.container(border=True):
        st.markdown(format_answer_markdown(result.answer))
    parts = [f"{result.latency} s", "ReAct agent" if result.mode == "agent" else "Quick mode"]
    if result.llm_calls:
        parts.append(f"{result.llm_calls} Groq call{'s' if result.llm_calls != 1 else ''}")
    if result.tokens:
        parts.append(f"~{result.tokens:,} tokens")
    parts.append(f"{len(result.sources)} sources")
    st.caption(", ".join(parts))


_STEP_ICONS = {"thought": "💭 Thought", "action": "🔧 Action", "observation": "👁 Observation",
               "answer": "✅ Answer", "note": "ℹ️ Note"}


def describe_step(step: AgentStep) -> str:
    """One-line, human readable description of a ReAct step."""
    if step.kind == "action":
        if step.tool == "search_datasheet":
            where = step.args.get("source", "any")
            return f'Search {"" if where == "any" else where + " "}for "{step.args.get("query", "")}"'
        if step.tool == "read_page":
            return f"Read page {step.args.get('page')}"
        if step.tool == "calculate":
            return f"Calculate {step.args.get('expression', '')}"
        return f"{step.tool}({step.args})"
    if step.kind == "observation" and step.tool == "hybrid_retrieval":
        return step.text
    return step.text


def render_agent_trace(result: QueryResult) -> None:
    steps = [s for s in result.steps if s.kind in _STEP_ICONS]
    if not steps:
        return
    with st.expander(f"🧠 How the agent worked ({len(steps)} steps)"):
        for step in steps:
            label = _STEP_ICONS[step.kind]
            text = describe_step(step)
            if step.kind == "observation" and step.tool not in ("", "hybrid_retrieval"):
                st.markdown(f"**{label}** · `{step.tool}`")
                st.code(text, language=None, wrap_lines=True)
            else:
                st.markdown(f"**{label}:** {text}")


def render_sources(result: QueryResult) -> None:
    if not result.sources:
        return
    st.markdown("### Sources")
    for i, src in enumerate(result.sources):
        icon = TYPE_ICONS.get(src.tag, "📄")
        with st.expander(f"{icon} REF-{src.ref_num}  |  Page {src.page}  |  {src.tag}  |  {src.section}",
                         expanded=(i == 0)):
            details = [f"Page: {esc(src.page)}", f"Type: {esc(src.tag)}", f"Section: {esc(src.section)}"]
            if src.parent_ctx:
                details.append(f"Path: {esc(src.parent_ctx)}")
            if src.score is not None:
                details.append(f"Score: {esc(src.score)}")
            if src.type == "text":
                details.append(f"Chunk: {src.chunk_idx}, depth {src.depth}")
            st.markdown(f'<div class="src-meta">{"<br>".join(details)}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="src-body">{esc(src.snippet)}</div>', unsafe_allow_html=True)
            meta = {k: v for k, v in (src.meta or {}).items() if k != "figure_file"}
            if meta:
                st.caption("Detected parameters: " + "; ".join(
                    f"{k}: {', '.join(map(str, v[:3])) if isinstance(v, list) else v}" for k, v in meta.items()))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def _color(pct: float) -> str:
    return "var(--ok)" if pct >= 70 else "var(--warn)" if pct >= 40 else "var(--bad)"


def render_metrics(result: QueryResult) -> None:
    m = result.metrics
    if not m:
        return
    st.markdown("### RAG metrics")
    cells = [
        ("Faithfulness", m.get("faithfulness", 0), "Answer words found in the sources"),
        ("Retrieval score", min(m.get("avg_retrieval_score", 0) / 100, 1), "Average best-match score"),
        ("Coverage", m.get("context_coverage", 0), "Question words found in the sources"),
        ("Completeness", m.get("answer_completeness", 0), "Answer length heuristic"),
        ("Source diversity", m.get("source_diversity", 0), "Kinds of sources used"),
        ("Confidence", m.get("confidence", 0) / 100, "Weighted blend of the above"),
    ]
    html_cells = []
    for name, value, tip in cells:
        pct = max(0, min(100, int(round(value * 100))))
        html_cells.append(
            f'<div class="metric"><div class="metric-name">{name}</div>'
            f'<div class="metric-val" style="color:{_color(pct)}">{pct}%</div>'
            f'<div class="meter"><span style="width:{pct}%;background:{_color(pct)}"></span></div>'
            f'<div class="metric-tip">{tip}</div></div>'
        )
    breakdown = "Retrieval + generation time"
    if "retrieval_s" in m and "llm_s" in m:
        breakdown = f"Search {esc(m['retrieval_s'])} s, answer {esc(m['llm_s'])} s"
    html_cells.append(
        f'<div class="metric"><div class="metric-name">Latency</div>'
        f'<div class="metric-val">{esc(m.get("latency_s", result.latency))} s</div>'
        f'<div class="metric-tip">{breakdown}</div></div>'
    )
    st.markdown(f'<div class="metrics">{"".join(html_cells)}</div>', unsafe_allow_html=True)
    with st.expander("Raw metric values"):
        st.json(m)


# ---------------------------------------------------------------------------
# Browse the index
# ---------------------------------------------------------------------------
def render_browser(index: DocumentIndex, max_figures: int = 60) -> None:
    with st.expander("🗂 Browse document contents", expanded=False):
        t_text, t_tables, t_eq, t_fig = st.tabs(["Text chunks", "Tables", "Equations", "Figures"])

        with t_text:
            text_nodes = [n for n in index.nodes if n.type == "text"]
            if not text_nodes:
                st.info("No text chunks found.")
            else:
                st.dataframe(
                    pd.DataFrame([{
                        "Page": n.page, "Section": n.section, "Path": n.parent_ctx,
                        "Depth": n.depth, "Chunk": n.chunk_idx, "Text": n.raw_content[:600],
                    } for n in text_nodes]),
                    width="stretch", hide_index=True,
                )
                depths = pd.Series([n.depth for n in text_nodes]).value_counts().sort_index()
                st.caption("Chunk depth distribution")
                st.bar_chart(depths.rename_axis("depth").rename("chunks"))

        with t_tables:
            tables = [n for n in index.nodes if n.type == "table"]
            if not tables:
                st.info("No tables detected.")
            for n in tables:
                with st.expander(f"Page {n.page}  |  {n.section}"):
                    lines = n.raw_content.split("\n")
                    try:
                        rows = [line.split(" | ") for line in lines]
                        st.dataframe(pd.DataFrame(rows[1:], columns=rows[0]),
                                     width="stretch", hide_index=True)
                    except Exception:
                        st.markdown(f'<div class="src-body">{esc(n.raw_content[:2000])}</div>',
                                    unsafe_allow_html=True)

        with t_eq:
            eqs = [n for n in index.nodes if n.type == "equation"]
            if eqs:
                st.dataframe(pd.DataFrame([
                    {"Page": n.page, "Section": n.section, "Expression": n.raw_content} for n in eqs
                ]), width="stretch", hide_index=True)
            else:
                st.info("No equations detected.")

        with t_fig:
            if not index.figures:
                st.info("No figures found.")
            else:
                if len(index.figures) > max_figures:
                    st.caption(f"Showing the first {max_figures} of {len(index.figures)} figures.")
                cols = st.columns(3)
                for i, fig in enumerate(index.figures[:max_figures]):
                    path = index.figure_path(fig)
                    if path is None:
                        continue
                    with cols[i % 3]:
                        st.image(str(path), caption=f"Page {fig.page}" + (f": {fig.caption[:80]}" if fig.caption else ""),
                                 width="stretch")
