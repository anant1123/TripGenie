"""
Budget maths, done in plain Python.

The AI only suggests prices. THIS code adds them up, so the totals are always correct
(for example: 8 friends need 4 rooms, and a train trip is a round trip).
"""
import math
from typing import List, Tuple

from config.settings import HOTEL_BUDGETS, settings
from models import BudgetSummary, TripPlan, TripRequest

# Which budget line an activity category belongs to
CATEGORY_LABELS = {
    "sightseeing": "Sightseeing & activities",
    "food": "Food",
    "local_transport": "Local transport",
    "shopping": "Shopping",
    "other": "Sightseeing & activities",
}


def calculate_budget(plan: TripPlan, request: TripRequest) -> Tuple[BudgetSummary, List[str]]:
    """Work out the total cost. Returns (budget, warnings)."""
    people = request.people
    nights = max(request.days - 1, 0)  # a 1-day trip needs no hotel
    rooms = math.ceil(people / settings.budget.people_per_room)

    lines = {
        "Transport (round trip)": max(plan.transport.price_per_person_one_way, 0) * 2 * people,
        "Hotel": max(plan.hotel.price_per_night_per_room, 0) * rooms * nights,
        "Food": 0.0,
        "Sightseeing & activities": 0.0,
        "Local transport": 0.0,
        "Shopping": 0.0,
    }

    # Add up every activity: cost per person x number of people
    for day in plan.days:
        for activity in day.activities:
            label = CATEGORY_LABELS.get(activity.category, "Sightseeing & activities")
            lines[label] += max(activity.cost_per_person, 0) * people

    total = sum(lines.values())
    budget = BudgetSummary(
        lines=lines,
        total=total,
        per_person=total / people,
        people=people,
        rooms=rooms,
        nights=nights,
    )
    return budget, _budget_warnings(plan, request, budget)


def _budget_warnings(plan: TripPlan, request: TripRequest, budget: BudgetSummary) -> List[str]:
    """Tell the user when the plan does not match what they asked for."""
    warnings = []

    limit = request.total_budget_per_person
    if limit > 0 and budget.per_person > limit:
        warnings.append(
            f"The estimated cost is INR {budget.per_person:,.0f} per person, "
            f"which is above your budget of INR {limit:,.0f}. Ask for a cheaper plan below."
        )

    price_range = HOTEL_BUDGETS.get(request.hotel_budget)
    if price_range:
        highest = price_range[1]
        if highest is not None and plan.hotel.price_per_night_per_room > highest:
            warnings.append(
                f"The suggested hotel costs INR {plan.hotel.price_per_night_per_room:,.0f} per night, "
                f"above your hotel budget (up to INR {highest:,.0f})."
            )
    return warnings
