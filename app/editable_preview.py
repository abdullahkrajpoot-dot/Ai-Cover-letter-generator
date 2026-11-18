"""Inline Word-style contenteditable preview component for Streamlit."""
from pathlib import Path

import streamlit.components.v1 as components


_COMPONENT = components.declare_component(
    "word_preview_editor",
    path=str(Path(__file__).resolve().parent / "word_preview_component"),
)


def word_preview_editor(document_html: str, key: str):
    """Return edited subject, addressee and Markdown body from the live preview."""
    return _COMPONENT(document_html=document_html, key=key, default=None)
