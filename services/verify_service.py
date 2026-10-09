"""
Step 3 of the pipeline: check the AI's plan against the real search results.

The AI is allowed to give a source NUMBER for a price, but it can never give a URL.
This code attaches the real URLs itself, and throws away any number the AI made up.
"""
from typing import Dict, List

from models import Source, TripPlan


def verify_plan(plan: TripPlan, research: List[Dict], expected_days: int) -> TripPlan:
    """Mark every priced item as 'sourced' or 'estimate' and attach the real sources."""
    valid_ids = {item["id"] for item in research}
    used_ids = set()
    estimate_count = 0

    def check(item, price: float) -> bool:
        """Keep only real source numbers. Returns True if the price is just an estimate."""
        item.source_ids = [number for number in item.source_ids if number in valid_ids]
        item.sourced = bool(item.source_ids)
        used_ids.update(item.source_ids)
        return price > 0 and not item.sourced

    if check(plan.transport, plan.transport.price_per_person_one_way):
        estimate_count += 1
    if check(plan.hotel, plan.hotel.price_per_night_per_room):
        estimate_count += 1
    for day_number, day in enumerate(plan.days, start=1):
        day.day = day_number  # make sure the days are numbered 1, 2, 3 ...
        for activity in day.activities:
            if check(activity, activity.cost_per_person):
                estimate_count += 1

    # Warnings are rebuilt every time the plan is checked
    plan.warnings = []
    if not research:
        plan.warnings.append("No live web results were found, so every price in this plan is an estimate.")
    if len(plan.days) != expected_days:
        plan.warnings.append(
            f"You asked for {expected_days} days but the plan has {len(plan.days)}. "
            "Ask for the missing days below."
        )

    plan.unsourced_count = estimate_count
    plan.sources = [
        Source(id=item["id"], title=item["title"], url=item["url"], category=item["category"])
        for item in research
        if item["id"] in used_ids
    ]
    return plan
