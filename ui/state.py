"""Session state and shared resources for the multi-page app."""
from __future__ import annotations

import dataclasses
from typing import Dict, List, Optional

import streamlit as st

from chat.conversations import Conversation, ConversationStore
from config.settings import Settings, load_settings
from learning.feedback import FeedbackStore
from learning.preferences import PreferenceStore
from llm.model_router import ModelRouter, ProviderStatus
from rag.models import DocumentIndex


@st.cache_resource(show_spinner=False)
def base_settings() -> Settings:
    return load_settings()


def settings() -> Settings:
    """Base settings + this browser session's overrides from the Settings page."""
    overrides = st.session_state.get("overrides", {})
    return dataclasses.replace(base_settings(), **overrides) if overrides else base_settings()


def set_override(**kw) -> None:
    st.session_state.setdefault("overrides", {}).update(kw)


@st.cache_resource(show_spinner=False)
def _stores(data_dir: str):
    from pathlib import Path

    d = Path(data_dir)
    return ConversationStore(d), FeedbackStore(d), PreferenceStore(d)


def conversations() -> ConversationStore:
    return _stores(str(settings().data_dir))[0]


def feedback() -> FeedbackStore:
    return _stores(str(settings().data_dir))[1]


def preferences() -> PreferenceStore:
    return _stores(str(settings().data_dir))[2]


def router() -> ModelRouter:
    return ModelRouter(settings())


@st.cache_data(ttl=60, show_spinner=False)
def _status(_settings: Settings, key: str) -> List[ProviderStatus]:
    return ModelRouter(_settings).status()


def provider_status() -> List[ProviderStatus]:
    s = settings()
    key = "|".join(s.llm_providers) + f"|{bool(s.groq_api_key)}|{bool(s.ollama_api_key)}|{s.enable_ollama_local}"
    return _status(s, key)


# --------------------------------------------------------------------- documents
def docs() -> Dict[str, Dict]:
    return st.session_state.setdefault("docs", {})


def add_doc(index: DocumentIndex) -> None:
    docs().setdefault(index.doc_id, {"index": index, "active": True})
    docs()[index.doc_id]["index"] = index


def active_indexes() -> List[DocumentIndex]:
    return [d["index"] for d in docs().values() if d["active"]]


# ----------------------------------------------------------------- conversation
def current_conversation() -> Conversation:
    store = conversations()
    cid = st.session_state.get("conv_id")
    conv: Optional[Conversation] = store.load(cid) if cid else None
    if conv is None:
        existing = store.list()
        conv = existing[0] if existing else store.create([i.doc_id for i in active_indexes()])
        st.session_state["conv_id"] = conv.id
    return conv
