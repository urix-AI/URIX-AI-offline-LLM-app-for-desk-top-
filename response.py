# File: urix/utils/response.py

from __future__ import annotations
from typing import Any, Dict, List, Optional
import re

try:
    import markdown  # type:ignore
except Exception:  
    markdown = None


def normalize_llm_response(resp: Dict[str, Any]) -> str:
    """Extract assistant text from llama.cpp/openai-style dict safely."""
    if not isinstance(resp, dict):
        return "Error: Invalid response type."
    try:
        choice = (resp.get("choices") or [{}])[0]
        text = (
            (choice.get("message") or {}).get("content")
            or choice.get("text")
            or ""
        )
        return text.strip() if isinstance(text, str) else ""
    except Exception:
        return ""


def strip_unsafe_html(html: str) -> str:
    """Very small sanitizer for QTextEdit: strip <script>, <iframe>, <object>, <embed> blocks.
    Note: QTextEdit doesn't execute JS, but we still remove dangerous tags.
    """
    if not html:
        return html
    # Remove whole tag blocks
    patterns = [
        r"<\s*script[^>]*>.*?<\s*/\s*script\s*>",
        r"<\s*iframe[^>]*>.*?<\s*/\s*iframe\s*>",
        r"<\s*object[^>]*>.*?<\s*/\s*object\s*>",
        r"<\s*embed[^>]*>.*?<\s*/\s*embed\s*>",
    ]
    cleaned = html
    for pat in patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    return cleaned


def markdown_to_safe_html(md_text: str) -> str:
    """Convert Markdown to HTML and strip unsafe tags. Falls back to plaintext."""
    if not md_text:
        return ""
    if markdown is None:
        # Escape basic HTML
        escaped = (
            md_text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        return f"<pre>{escaped}</pre>"
    html = markdown.markdown(md_text, extensions=["fenced_code", "tables"])  # type: ignore
    return strip_unsafe_html(html)