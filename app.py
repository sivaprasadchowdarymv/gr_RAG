"""
Datasheet RAG Agent — Streamlit entry point.

    streamlit run app.py

A ReAct agent (Groq, free tier) answers questions about an uploaded
datasheet, citing every fact. Parsing, chunking, tables, equations,
embeddings and hybrid search all run inside this app.
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Datasheet RAG Agent", page_icon="📡", layout="wide")

from config.settings import get_logger, load_settings, setup_logging  # noqa: E402
from rag import llm  # noqa: E402
from rag.embeddings import warm_up  # noqa: E402
from rag.models import AgentStep  # noqa: E402
from rag.pdf_parser import PdfProcessingError  # noqa: E402
from rag.pipeline import answer_query, clear_cache, get_index, save_feedback  # noqa: E402
from storage.cache import compute_doc_id  # noqa: E402
from ui import components as ui  # noqa: E402
from ui.styles import CSS  # noqa: E402

BASE_SETTINGS = load_settings()
setup_logging(BASE_SETTINGS.log_level)
log = get_logger("app")

MAX_QUESTION_CHARS = 500
EXAMPLES = (
    "What is the maximum output current?",
    "What is the pin configuration?",
    "How do I calculate the power dissipation?",
)


@st.cache_data(ttl=60, show_spinner=False)
def groq_status(_settings, model_key: str) -> llm.LLMStatus:
    """Checked at most once a minute (the key is not part of the cache key)."""
    return llm.check_status(_settings)


@st.cache_resource(show_spinner=False)
def start_background_warm_up() -> bool:
    warm_up(BASE_SETTINGS)  # start downloading/loading the embedding model early
    return True


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    start_background_warm_up()
    status = groq_status(BASE_SETTINGS, BASE_SETTINGS.groq_model + str(bool(BASE_SETTINGS.groq_api_key)))
    ui.render_header()

    # ---- Sidebar -----------------------------------------------------------
    with st.sidebar:
        st.markdown("#### Status")
        ui.render_status(status, BASE_SETTINGS)
        st.divider()
        settings = ui.render_sidebar_config(BASE_SETTINGS, status)
        st.divider()
        stats_slot = st.container()
        st.divider()
        st.markdown("#### 🗑 Cache")
        clear_clicked = st.button("Clear cache", help="Forget the index for the current PDF and rebuild it.")
        feedback_slot = st.container()

    # ---- Upload --------------------------------------------------------------
    st.markdown("#### Upload datasheet")
    upload = st.file_uploader(
        "Upload a PDF datasheet", type=["pdf"], label_visibility="collapsed",
        help=f"PDF files up to {settings.max_upload_mb} MB and {settings.max_pages} pages.",
    )
    if upload is None:
        with stats_slot:
            ui.render_sidebar_stats(None)
        if clear_clicked:
            groq_status.clear()
        st.info("Upload a PDF datasheet to begin. Indexing happens once per file; "
                "after that, questions are answered from the saved index.")
        return

    pdf_bytes = upload.getvalue()
    if clear_clicked:
        try:
            clear_cache(compute_doc_id(pdf_bytes), settings)
        except ValueError:
            pass
        groq_status.clear()
        st.session_state.pop("result", None)
        st.toast("Cache cleared. The document will be indexed again.")

    progress_slot = st.empty()

    def on_progress(fraction: float, message: str) -> None:
        progress_slot.progress(min(max(fraction, 0.0), 1.0), text=message)

    try:
        index, warnings = get_index(pdf_bytes, upload.name, settings, progress=on_progress)
    except PdfProcessingError as exc:
        progress_slot.empty()
        st.error(exc.user_message)
        return
    progress_slot.empty()

    with stats_slot:
        ui.render_sidebar_stats(index)
    ui.render_document_summary(index)
    ui.render_warnings(warnings)
    st.divider()

    # ---- Question ------------------------------------------------------------
    with st.form("ask", clear_on_submit=False, border=False):
        question = st.text_input("Ask your question", max_chars=MAX_QUESTION_CHARS,
                                 placeholder=EXAMPLES[0], help="Examples: " + " · ".join(EXAMPLES))
        asked = st.form_submit_button("Ask", type="primary")

    if asked:
        if not question.strip():
            st.warning("Type a question first.")
        else:
            label = "Agent is working…" if settings.agent_mode == "agent" else "Answering…"
            with st.status(label, expanded=True) as live:
                def on_step(step: AgentStep) -> None:
                    if step.kind in ("action", "note") or step.tool == "hybrid_retrieval":
                        live.write(("🔧 " if step.kind == "action" else "🔎 ") + ui.describe_step(step))
                    elif step.kind == "thought":
                        live.update(label="💭 Reasoning…")

                result = answer_query(question, index, settings, on_step=on_step)
                live.update(label=f"Done in {result.latency} s", state="complete", expanded=False)
            st.session_state["result"] = {"doc_id": index.doc_id, "question": question, "result": result}

    saved = st.session_state.get("result")
    if saved and saved["doc_id"] == index.doc_id:
        result = saved["result"]
        st.divider()
        ui.render_warnings(result.warnings)
        ui.render_answer(result)
        ui.render_agent_trace(result)
        st.divider()
        ui.render_sources(result)
        if result.metrics:
            st.divider()
            ui.render_metrics(result)

    st.divider()
    ui.render_browser(index)

    # ---- Optional human feedback (ENABLE_FEEDBACK=true) ----------------------
    if settings.enable_feedback:
        with feedback_slot:
            st.divider()
            with st.expander("✍ Save a correct answer"):
                fq = st.text_input("Question", key="fb_q")
                fa = st.text_area("Correct answer", key="fb_a")
                if st.button("Save answer"):
                    if fq.strip() and fa.strip():
                        save_feedback(index, settings, fq, fa)
                        st.success("Saved. This exact question will now return this answer.")
                    else:
                        st.warning("Fill in both fields.")


try:
    main()
except Exception:  # last safety net: log the details, show a plain message
    log.exception("Unhandled error in the Streamlit app")
    st.error("Something went wrong while handling your request. Please try again. "
             "If it keeps happening, check the app logs.")
