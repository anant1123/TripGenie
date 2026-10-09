"""
Step 1 of the pipeline: collect facts from the web BEFORE the AI writes anything.

Our own code decides what to search (transport, hotels, attractions, food, best time),
so the AI can never "forget" to search or pretend that it did.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

from models import TripRequest
from services.search_service import SearchService


def build_queries(request: TripRequest) -> Dict[str, str]:
    """One search query for each topic: {"transport": "...", "hotels": "...", ...}"""
    origin = request.from_city
    destination = request.to_city

    transport = "train flight bus" if request.transport == "Any" else request.transport.lower()
    hotel_level = request.hotel_budget.split(" (")[0].lower() if request.hotel_budget else ""
    food = " ".join(request.food_prefs).lower() if request.food_prefs else "local"

    return {
        "transport": f"{transport} from {origin} to {destination} ticket price",
        "hotels": f"{hotel_level} hotels in {destination} price per night".strip(),
        "attractions": f"top attractions in {destination} entry fee ticket price",
        "food": f"best {food} restaurants in {destination} price",
        "best_time": f"best time to visit {destination} weather",
    }


class ResearchService:
    """Runs all the searches and gives every result a number."""

    def __init__(self, search_service: SearchService):
        self.search_service = search_service

    def research(self, request: TripRequest) -> List[Dict]:
        """Returns a list like [{"id": 1, "category": "hotels", "title": ..., "url": ..., "snippet": ...}]."""
        queries = build_queries(request)

        # The searches are independent, so run them at the same time
        with ThreadPoolExecutor(max_workers=len(queries)) as pool:
            all_results = list(pool.map(self.search_service.search, queries.values()))

        items = []
        seen_urls = set()
        for category, results in zip(queries.keys(), all_results):
            for result in results:
                if result["url"] in seen_urls:  # the same page can appear in two searches
                    continue
                seen_urls.add(result["url"])
                items.append({"id": len(items) + 1, "category": category, **result})
        return items


def format_research_for_prompt(items: List[Dict]) -> str:
    """Turn the numbered results into text for the AI prompt."""
    if not items:
        return "No search results were found. Give honest estimates and leave source_ids empty."
    lines = []
    for item in items:
        lines.append(f"[{item['id']}] ({item['category']}) {item['title']}")
        lines.append(f"    {item['snippet']}")
    return "\n".join(lines)
