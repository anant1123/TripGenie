from config.settings import settings
from services.research_service import ResearchService, build_queries, format_research_for_prompt
from services.search_service import SearchService
from tests.helpers import FakeSearchService, make_request


class FakeTavily:
    """Pretends to be the Tavily client."""

    def __init__(self, results=None, fail=False):
        self.results = results or []
        self.fail = fail
        self.calls = 0

    def search(self, query, max_results):
        self.calls += 1
        if self.fail:
            raise RuntimeError("quota exceeded")
        return {"results": self.results}


def make_search_service(monkeypatch, tavily) -> SearchService:
    monkeypatch.setattr(settings.api, "tavily_api_key", "")
    return SearchService(tavily_client=tavily)


def test_tavily_results_are_cleaned(monkeypatch):
    tavily = FakeTavily(
        [
            {"title": "A", "url": "https://a.com", "content": "x" * 1000},
            {"title": "No url", "url": "", "content": "dropped"},
        ]
    )
    results = make_search_service(monkeypatch, tavily).search("hotels")

    assert len(results) == 1  # the result without a URL was dropped
    assert len(results[0]["snippet"]) == settings.search.snippet_length


def test_duckduckgo_is_used_when_tavily_fails(monkeypatch):
    service = make_search_service(monkeypatch, FakeTavily(fail=True))
    monkeypatch.setattr(
        service,
        "_search_duckduckgo",
        lambda query: [{"title": "DDG", "url": "https://ddg.com", "snippet": "from backup"}],
    )
    assert service.search("hotels")[0]["title"] == "DDG"


def test_same_search_is_only_sent_once(monkeypatch):
    tavily = FakeTavily([{"title": "A", "url": "https://a.com", "content": "text"}])
    service = make_search_service(monkeypatch, tavily)
    service.search("hotels")
    service.search("hotels")
    assert tavily.calls == 1


def test_queries_cover_every_topic():
    queries = build_queries(make_request(transport="Train", food_prefs=["Vegetarian"]))
    assert set(queries) == {"transport", "hotels", "attractions", "food", "best_time"}
    assert "train" in queries["transport"]
    assert "vegetarian" in queries["food"]
    assert "economy" in queries["hotels"]  # the price range text in brackets is not used


def test_results_get_numbers_and_duplicate_pages_are_dropped():
    items = ResearchService(FakeSearchService()).research(make_request())

    # 5 topics x 2 results, but the "shared" page appears in every topic and is kept only once
    assert len(items) == 6
    assert [item["id"] for item in items] == [1, 2, 3, 4, 5, 6]
    assert len({item["url"] for item in items}) == 6


def test_prompt_text_without_results_tells_the_ai_to_estimate():
    assert "estimates" in format_research_for_prompt([])
