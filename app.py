"""
RAG∞ Pro — Adaptive Multimodal Agentic RAG (Streamlit entry point).

    streamlit run app.py

Pages: Chat · Documents · Metrics · Agent Activity · Preferences · Settings
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="RAG∞ Pro", page_icon="∞", layout="wide")

from config.settings import get_logger, setup_logging  # noqa: E402
from rag.embeddings import warm_up  # noqa: E402
from ui import pages, state, widgets  # noqa: E402
from ui.styles import CSS  # noqa: E402

setup_logging(state.base_settings().log_level)
log = get_logger("app")


@st.cache_resource(show_spinner=False)
def _warm_up() -> bool:
    warm_up(state.base_settings())  # load the embedding model in the background
    return True


def _sidebar_status() -> None:
    s = state.settings()
    with st.sidebar:
        lines = []
        statuses = state.provider_status()
        configured = [p for p in statuses if p.configured]
        if not configured:
            lines.append(widgets.status_line(False, "AI provider", "none configured"))
        for p in configured:
            lines.append(widgets.status_line(p.connected, p.label, "connected" if p.connected else "unavailable"))
        n = len(state.active_indexes())
        lines.append(widgets.status_line(True if n else None, "Documents", f"{n} active"))
        lines.append(widgets.status_line(None, "Pipeline", "RAG∞ Pro" if s.pipeline_mode == "pro" else "Legacy"))
        st.markdown("".join(lines), unsafe_allow_html=True)
        if not configured:
            st.caption("Add GROQ_API_KEY or OLLAMA_API_KEY to the app's secrets. Until then, answers show the best "
                       "matching evidence only.")


def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    _warm_up()
    nav = {
        "chat": st.Page(pages.chat_page, title="Chat", icon="💬", url_path="chat", default=True),
        "documents": st.Page(pages.documents_page, title="Documents", icon="📄", url_path="documents"),
        "metrics": st.Page(pages.metrics_page, title="Metrics", icon="📈", url_path="metrics"),
        "activity": st.Page(pages.activity_page, title="Agent Activity", icon="🧭", url_path="activity"),
        "preferences": st.Page(pages.preferences_page, title="Preferences", icon="🎛", url_path="preferences"),
        "settings": st.Page(pages.settings_page, title="Settings", icon="⚙", url_path="settings"),
    }
    st.session_state["pages"] = nav
    current = st.navigation(list(nav.values()))
    _sidebar_status()
    current.run()


try:
    main()
except Exception:  # last safety net: log details, show a plain message (never a stack trace)
    log.exception("Unhandled error in the app")
    st.error("Something went wrong while handling your request. Please try again; details are in the server logs.")
