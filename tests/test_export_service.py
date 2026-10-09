from functools import partial

from models import TripPlan
from services.budget_service import calculate_budget
from services.export_service import plan_to_ics, plan_to_markdown, plan_to_pdf
from tests.helpers import make_draft, make_request
from utils.formatters import format_money

money = partial(format_money, currency="INR", rate=1.0)


def make_plan() -> TripPlan:
    plan = TripPlan.model_validate(make_draft().model_dump())
    plan.budget, _ = calculate_budget(plan, make_request())
    return plan


def test_markdown_contains_the_important_parts():
    text = plan_to_markdown(make_plan(), money)

    assert "# Delhi in 2 days" in text
    assert "## Day 1: Old Delhi" in text
    assert "Red Fort" in text
    assert "₹1,000 per person one way (estimate)" in text  # no source -> marked as estimate
    assert "Total:" in text


def test_pdf_is_a_real_pdf_even_with_rupee_signs_and_long_urls():
    plan = make_plan()
    plan.sources = []
    plan.tips = ["Visit https://example.com/" + "very-long-address-" * 12]

    pdf = plan_to_pdf(plan, money)

    assert pdf.startswith(b"%PDF")


def test_calendar_has_one_event_per_day():
    plan = make_plan()
    calendar = plan_to_ics(plan, "2026-12-20")

    assert calendar.count("BEGIN:VEVENT") == 2
    assert "DTSTART;VALUE=DATE:20261220" in calendar
    assert "DTSTART;VALUE=DATE:20261221" in calendar
    assert "SUMMARY:Day 1: Old Delhi" in calendar
    assert calendar.endswith("END:VCALENDAR\r\n")
