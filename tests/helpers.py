"""Small helpers that build sample data for the tests."""
from datetime import date, timedelta

from models import Activity, DayPlan, HotelOption, TransportOption, TripPlanDraft, TripRequest


def make_request(**changes) -> TripRequest:
    """A valid trip request. Pass keyword arguments to change a field."""
    values = {
        "from_city": "Kota, Rajasthan, India",
        "to_city": "New Delhi, Delhi, India",
        "start_date": (date.today() + timedelta(days=30)).isoformat(),
        "days": 2,
        "people": 4,
        "hotel_budget": "Economy (₹1000-3000)",
    }
    values.update(changes)
    return TripRequest(**values)


def make_draft(title: str = "Delhi in 2 days", source_ids=None) -> TripPlanDraft:
    """A small plan like the AI would write.

    Costs: transport 1000 one way, hotel 2000 per night, 2 days of activities.
    """
    source_ids = source_ids if source_ids is not None else [1]
    day1 = DayPlan(
        day=1,
        theme="Old Delhi",
        activities=[
            Activity(
                time_of_day="Morning",
                title="Red Fort",
                description="Visit the fort",
                place_name="Red Fort",
                category="sightseeing",
                cost_per_person=50,
                source_ids=source_ids,
            ),
            Activity(
                time_of_day="Afternoon",
                title="Lunch at Karim's",
                description="Famous Mughlai food",
                category="food",
                cost_per_person=400,
            ),
        ],
    )
    day2 = DayPlan(
        day=2,
        theme="New Delhi",
        activities=[
            Activity(
                time_of_day="Morning",
                title="India Gate",
                description="A walk at India Gate",
                category="sightseeing",
                cost_per_person=0,
            ),
            Activity(
                time_of_day="Evening",
                title="Metro rides",
                description="Travel by metro",
                category="local_transport",
                cost_per_person=100,
            ),
        ],
    )
    return TripPlanDraft(
        title=title,
        overview="A short trip to Delhi.",
        best_time_to_visit="October to March",
        transport=TransportOption(
            mode="Train",
            description="Overnight train",
            price_per_person_one_way=1000,
            source_ids=source_ids,
        ),
        hotel=HotelOption(
            name="Hotel Test",
            area="Paharganj",
            description="Simple hotel",
            price_per_night_per_room=2000,
            source_ids=source_ids,
        ),
        days=[day1, day2],
        tips=["Carry water"],
    )


class FakeSearchService:
    """Pretends to search the web. Always returns the same two results."""

    def __init__(self):
        self.queries = []

    def search(self, query):
        self.queries.append(query)
        return [
            {
                "title": f"Result A for {query}",
                "url": f"https://example.com/a?q={query}",
                "snippet": "Ticket costs 1000.",
            },
            {"title": "Shared page", "url": "https://example.com/shared", "snippet": "Hotel costs 2000."},
        ]


class FakeLLM:
    """Pretends to be the AI model. Returns the drafts you give it, one per call."""

    def __init__(self, drafts):
        self.drafts = list(drafts)
        self.calls = 0
        self.last_messages = []

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        self.calls += 1
        self.last_messages = messages
        # When only one draft is left, keep returning it
        return self.drafts.pop(0) if len(self.drafts) > 1 else self.drafts[0]


class BrokenLLM:
    """An AI model that always fails."""

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        raise RuntimeError("model is down")
