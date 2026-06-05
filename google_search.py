# urix/utils/google_search.py

import logging
from typing import List, Dict, Union
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

def perform_search(api_key: str, search_engine_id: str, query: str, num_results: int = 5) -> Union[str, List[Dict[str, str]]]:
    
    if not api_key or "YOUR_API_KEY" in api_key:
        logger.error("Google Search API key is missing or is a placeholder.")
        return "Error: Google Search API key is not configured."

    try:
        service = build("customsearch", "v1", developerKey=api_key)
        result = (
            service.cse()
            .list(q=query, cx=search_engine_id, num=num_results)
            .execute()
        )

        search_items = result.get("items", [])
        if not search_items:
            return []

        formatted_results: List[Dict[str, str]] = []
        for item in search_items:
            formatted_results.append(
                {
                    "title": item.get("title", "No Title"),
                    "snippet": item.get("snippet", "No Snippet").replace("\n", " "),
                    "link": item.get("link", ""),
                }
            )

        return formatted_results

    except HttpError as e:
        logger.error(f"An HTTP error occurred during Google Search: {e}")
        try:
            return f"Error: API error occurred: {e.content.decode()}"
        except Exception:
            return "Error: API error occurred."
    except Exception as e:
        logger.error(f"Unexpected error during Google Search: {e}", exc_info=True)
        return f"Error: Unexpected error occurred: {e}"


