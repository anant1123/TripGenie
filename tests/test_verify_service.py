from models import TripPlan
from services.verify_service import verify_plan
from tests.helpers import make_draft

RESEARCH = [
    {"id": 1, "category": "hotels", "title": "Hotel page", "url": "https://example.com/1", "snippet": "..."},
    {"id": 2, "category": "food", "title": "Food page", "url": "https://example.com/2", "snippet": "..."},
]


def make_plan(source_ids) -> TripPlan:
    return TripPlan.model_validate(make_draft(source_ids=source_ids).model_dump())


def test_real_source_numbers_are_kept_and_urls_attached():
    plan = verify_plan(make_plan([1]), RESEARCH, expected_days=2)

    assert plan.transport.sourced is True
    assert plan.hotel.sourced is True
    assert [source.url for source in plan.sources] == ["https://example.com/1"]


def test_made_up_source_numbers_are_removed():
    # The AI claims sources 99 and 100, which do not exist
    plan = verify_plan(make_plan([99, 100]), RESEARCH, expected_days=2)

    assert plan.transport.source_ids == []
    assert plan.transport.sourced is False
    assert plan.sources == []


def test_estimates_are_counted_but_free_items_are_not():
    plan = verify_plan(make_plan([]), RESEARCH, expected_days=2)

    # Priced items without a source: transport, hotel, Red Fort, lunch, metro (India Gate is free)
    assert plan.unsourced_count == 5


def test_warning_when_the_number_of_days_is_wrong():
    plan = verify_plan(make_plan([1]), RESEARCH, expected_days=5)
    assert any("5 days" in warning for warning in plan.warnings)


def test_warning_when_there_is_no_research_at_all():
    plan = verify_plan(make_plan([1]), [], expected_days=2)
    assert any("estimate" in warning for warning in plan.warnings)


def test_days_are_renumbered():
    plan = make_plan([1])
    plan.days[0].day = 7
    plan.days[1].day = 7
    plan = verify_plan(plan, RESEARCH, expected_days=2)
    assert [day.day for day in plan.days] == [1, 2]
