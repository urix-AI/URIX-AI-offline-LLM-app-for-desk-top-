# File: urix/retrieval/search_orchestrator.py

from __future__ import annotations
from typing import List, Dict, Any, Optional
import time
import math
import re

from urix.utils.google_search import perform_search


def _jaccard(a: str, b: str) -> float:
    sa, sb = set(a.lower().split()), set(b.lower().split())
    if not sa or not sb:
        return 0.0
    # safe: both are sets, so union/intersection work fine
    return len(sa.intersection(sb)) / len(sa.union(sb))


def _dedup(items: List[Dict[str, str]], title_sim_thresh: float = 0.6) -> List[Dict[str, str]]:
    
    out: List[Dict[str, str]] = []
    for it in items:
        t = it.get("title", "")
        if any(_jaccard(t, x.get("title", "")) >= title_sim_thresh for x in out):
            continue
        out.append(it)
    return out



def _score_item(item: Dict[str, str], query: str) -> float:
    # why: prioritize closer title matches; snippet adds tie-breaker
    t, s = item.get("title", ""), item.get("snippet", "")
    qt = _jaccard(query, t)
    qs = _jaccard(query, s)
    return 0.7 * qt + 0.3 * qs


def _format_results(items: List[Dict[str, str]]) -> str:
    lines = []
    for i, it in enumerate(items, 1):
        title = it.get("title", "No Title").strip()
        snippet = it.get("snippet", "").strip()
        link = it.get("link", "").strip()
        lines.append(f"({i}) {title} — {snippet} (URL: {link})")
    return "\n".join(lines)


class SearchOrchestrator:
    def __init__(self, api_key: str, cx: str, *, default_results: int = 6,
                 safe: str = "off", lang: str = "en", time_range: Optional[str] = None):
        self.api_key = api_key
        self.cx = cx
        self.default_results = default_results
        self.safe = safe
        self.lang = lang
        self.time_range = time_range

    def search(self, query: str, *, num_results: Optional[int] = None) -> Dict[str, Any]:
        n = num_results or self.default_results
        raw = perform_search(
            self.api_key,
            self.cx,
            query,
            num_results=n,
        )
        if isinstance(raw, str):
            return {"items": [], "formatted": raw, "query": query}
        items = _dedup(raw)
        items.sort(key=lambda x: _score_item(x, query), reverse=True)
        top = items[:n]
        formatted = _format_results(top)
        return {"items": top, "formatted": formatted, "query": query}

    def build_grounded_prompt(self, user_query: str, user_profile: Dict[str, str]) -> Dict[str, Any]:
        results = self.search(user_query)
        profile_ctx = "\n".join([f"- {k}: {v}" for k, v in user_profile.items()]) if user_profile else ""
        guidance = (
            "You are URIX. Answer the user's question directly using ONLY the search results below.\n"
            "Do NOT invent placeholder values (like [Insert …]).\n"
            "If exact numeric values (like temperature) are present in the results, quote them.\n"
            "Always cite sources using [1], [2], etc. and include a 'Sources' section at the end "
            "with clickable markdown links.\n"
            "If the information is not found in the search results, reply honestly that it is unavailable."
        )

        prompt_parts = [guidance]
        if profile_ctx:
            prompt_parts.append(f"User profile\n---\n{profile_ctx}\n---\n")
        prompt_parts.append("Search Results\n---")
        prompt_parts.append(results.get("formatted", ""))
        prompt_parts.append("---\n")
        prompt_parts.append(f"User question: {user_query}")
        prompt_parts.append(
            "Formatting:\n- Use Markdown\n- Numbered citations [n]\n- End with:\n\nSources:\n- [n] Title (URL)"
        )
        return {"prompt": "\n\n".join(prompt_parts), "results": results}


# File: urix/utils/google_search.py

from __future__ import annotations
import logging
from typing import List, Dict, Union
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


def _clean_url(url: str) -> str:
    try:
        p = urlparse(url)
        allowed = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_")]
        return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(allowed), p.fragment))
    except Exception:
        return url


def perform_search(api_key: str, search_engine_id: str, query: str, num_results: int = 5) -> Union[str, List[Dict[str, str]]]:
    if not api_key or "YOUR_API_KEY" in api_key:
        logger.error("Google Search API key is missing or placeholder.")
        return "Error: Google Search API key is not configured."
    try:
        service = build("customsearch", "v1", developerKey=api_key)
        result = service.cse().list(q=query, cx=search_engine_id, num=num_results).execute()
        items = result.get("items", [])
        if not items:
            return []
        out: List[Dict[str, str]] = []
        seen = set()
        for it in items:
            title = (it.get("title") or "No Title").strip()
            snippet = (it.get("snippet") or "No Snippet").replace("\n", " ").strip()
            link = _clean_url((it.get("link") or "").strip())
            if not link or link in seen:
                continue
            seen.add(link)
            out.append({"title": title, "snippet": snippet, "link": link})
        return out
    except HttpError as e:
        logger.error(f"HTTP error during Google Search: {e}")
        try:
            return f"Error: API error occurred: {e.content.decode()}"
        except Exception:
            return "Error: API error occurred."
    except Exception as e:
        logger.error(f"Unexpected error during Google Search: {e}", exc_info=True)
        return f"Error: Unexpected error occurred: {e}"



from __future__ import annotations
import os, gc, json, logging, re
from typing import Dict, Any, List, Optional
from threading import Thread

from urix.retrieval.search_orchestrator import SearchOrchestrator
from urix.utils.database import KnowledgeBase
from urix.utils.response import normalize_llm_response

try:
    from llama_cpp import Llama
except ImportError:
    logging.critical("llama-cpp-python is not installed. Please install it with 'pip install llama-cpp-python'")
    Llama = None

logger = logging.getLogger(__name__)

class ProfileUpdateWorker(Thread):
    def __init__(self, engine, history_chunk):
        super().__init__(); self.engine = engine; self.history_chunk = history_chunk; self.daemon = True
    def run(self):
        self.engine._update_user_profile_from_history(self.history_chunk)

class UrixEngine:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.llm = None
        self.current_mode = None
        data_dir = os.path.join(self.config.get("base_dir", "."), "data"); os.makedirs(data_dir, exist_ok=True)
        self.kb = KnowledgeBase(os.path.join(data_dir, "urix_kb.db"))
        self.message_counter = 0; self.profile_update_threshold = 10

        if not Llama:
            raise ImportError("Llama-cpp-python is required but not installed.")
        model_config = self.config.get("models", {})
        self.model_modes = model_config.get("modes", {})
        default_mode = model_config.get("default_mode", "eco")
        if not self.model_modes:
            raise ValueError("No model modes defined in config.yaml under models.modes")
        if not self.switch_model(default_mode):
            raise FileNotFoundError("Model path not found or failed to load for default mode.")

        gs = self.config.get("google_search", {})
        self.search = SearchOrchestrator(
            api_key=gs.get("api_key", ""),
            cx=gs.get("search_engine_id", ""),
            default_results=gs.get("num_results", 6),
            safe=gs.get("safe", "off"),
            lang=gs.get("lang", "en"),
            time_range=gs.get("time_range"),
        )

  
    def generate_chat_response(self, history: List[Dict[str, str]], max_tokens: int = 0) -> Dict:
        if not self.llm:
            return {"choices": [{"text": "Error: LLM model not loaded."}]}
        user_query = history[-1]['content']

        greetings = {'hello','hi','hey','how are you','good morning','good afternoon','good evening'}
        if user_query.strip().lower() in greetings:
            return {"choices": [{"text": "Hello there! I'm here to help. What can I do for you today?"}]}

        self.message_counter += 1
        if self.message_counter >= self.profile_update_threshold:
            ProfileUpdateWorker(self, history[-self.profile_update_threshold:]).start(); self.message_counter = 0

        cached = self.kb.get_answer(user_query)
        if cached:
            return {"choices": [{"text": cached + "\n\n*– Answer from local Knowledge Base.*"}]}

        user_profile = self.kb.get_full_profile()

        # Decide whether to search: eco = off, else on
        do_search = self.current_mode != 'eco' and self.search.api_key and self.search.cx
        if do_search:
            s = self.search.build_grounded_prompt(user_query, user_profile)
            prompt = s["prompt"]
            search_items = s["results"].get("items", [])
        else:
            # No search: plain persona
            prompt = (
                "You are URIX. Answer **concisely and directly**. Use Markdown.\n" 
                f"Question: {user_query}"
            )
            search_items = []

        messages_to_send = list(history[:-1])
        messages_to_send.append({'role': 'user', 'content': prompt})

        try:
            resp = self.llm.create_chat_completion(messages=messages_to_send, max_tokens=(max_tokens or None))
            content = normalize_llm_response(resp)
            if content and not content.startswith("Error:"):
                self.kb.add_entry(user_query, content)
            return {"choices": [{"text": content}]}
        except Exception as e:
            logger.error(f"Llama chat error: {e}", exc_info=True)
            return {"choices": [{"text": f"Error: {e}"}]}
