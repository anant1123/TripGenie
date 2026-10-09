"""Web search. Tavily is used first, DuckDuckGo (free, no key) is the backup."""
import time
from typing import Dict, List, Optional, Tuple

from tavily import TavilyClient

from config.settings import settings
from utils.logger import get_logger

from ddgs import DDGS

logger = get_logger(__name__)


class SearchService:
    """Runs web searches and returns simple results: {"title", "url", "snippet"}."""

    def __init__(self, tavily_client: Optional[TavilyClient] = None):
        key = settings.api.tavily_api_key
        # No Tavily key? Then self.tavily stays None and DuckDuckGo is used.
        self.tavily = tavily_client or (TavilyClient(api_key=key) if key else None)
        self._cache: Dict[str, Tuple[float, List[Dict]]] = {}

    def search(self, query: str) -> List[Dict]:
        """Search the web. Returns an empty list if every search engine fails."""
        cached = self._cache.get(query)
        if cached and time.time() - cached[0] < settings.search.cache_seconds:
            return cached[1]

        start = time.time()
        engine = "tavily"
        results = self._search_tavily(query)
        if not results and settings.search.use_ddg_fallback:
            engine = "duckduckgo"
            results = self._search_duckduckgo(query)

        # Always log what was really searched, so you can check the plan's sources
        logger.log_tool_call(engine, query, len(results), time.time() - start)
        if results:
            self._cache[query] = (time.time(), results)
        return results

    def _search_tavily(self, query: str) -> List[Dict]:
        if self.tavily is None:
            return []
        try:
            response = self.tavily.search(query=query, max_results=settings.search.results_per_search)
            items = response.get("results", [])
        except Exception as error:  # network errors, quota exceeded, bad key ...
            logger.warning(f"Tavily search failed for '{query}': {error}")
            return []
        return self._clean(
            [{"title": i.get("title"), "url": i.get("url"), "snippet": i.get("content")} for i in items]
        )

    def _search_duckduckgo(self, query: str) -> List[Dict]:
        try:
            items = DDGS().text(query, max_results=settings.search.results_per_search)
        except Exception as error:
            logger.warning(f"DuckDuckGo search failed for '{query}': {error}")
            return []
        return self._clean(
            [{"title": i.get("title"), "url": i.get("href"), "snippet": i.get("body")} for i in items]
        )

    @staticmethod
    def _clean(items: List[Dict]) -> List[Dict]:
        """Drop results without a URL and cut long snippets short."""
        cleaned = []
        for item in items:
            if not item.get("url"):
                continue
            cleaned.append(
                {
                    "title": (item.get("title") or "Untitled").strip(),
                    "url": item["url"],
                    "snippet": (item.get("snippet") or "").strip()[: settings.search.snippet_length],
                }
            )
        return cleaned
