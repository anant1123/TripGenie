from models import TripPlan
from services.budget_service import calculate_budget
from tests.helpers import make_draft, make_request


def make_plan() -> TripPlan:
    return TripPlan.model_validate(make_draft().model_dump())


def test_budget_adds_up_for_a_group():
    # 4 people -> 2 rooms. 2 days -> 1 night.
    budget, warnings = calculate_budget(make_plan(), make_request(people=4, days=2))

    assert budget.rooms == 2
    assert budget.nights == 1
    assert budget.lines["Transport (round trip)"] == 1000 * 2 * 4
    assert budget.lines["Hotel"] == 2000 * 2 * 1
    assert budget.lines["Food"] == 400 * 4
    assert budget.lines["Sightseeing & activities"] == 50 * 4
    assert budget.lines["Local transport"] == 100 * 4
    assert budget.total == 14200
    assert budget.per_person == 3550
    assert warnings == []


def test_odd_group_size_rounds_rooms_up():
    budget, _ = calculate_budget(make_plan(), make_request(people=3))
    assert budget.rooms == 2


def test_one_day_trip_has_no_hotel_cost():
    budget, _ = calculate_budget(make_plan(), make_request(days=1))
    assert budget.nights == 0
    assert budget.lines["Hotel"] == 0


def test_warning_when_over_total_budget():
    _, warnings = calculate_budget(make_plan(), make_request(total_budget_per_person=1000))
    assert any("above your budget" in warning for warning in warnings)


def test_warning_when_hotel_is_above_hotel_budget():
    # The sample hotel costs 2000. "Budget" hotels may cost at most 1000.
    _, warnings = calculate_budget(make_plan(), make_request(hotel_budget="Budget (₹0-1000)"))
    assert any("hotel" in warning.lower() for warning in warnings)
