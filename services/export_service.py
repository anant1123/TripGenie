"""Export a plan as text (Markdown), PDF or a calendar file (.ics)."""
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from fpdf import FPDF

from models import TripPlan

# money(amount_in_inr) -> text such as "₹1,500" or "$18.00"
Money = Callable[[float], str]


def _price_note(price: float, sourced: bool) -> str:
    """' (estimate)' for a price that no search result supports."""
    return " (estimate)" if price > 0 and not sourced else ""


# ----------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------
def plan_to_markdown(plan: TripPlan, money: Money) -> str:
    """The whole plan as readable text."""
    transport, hotel = plan.transport, plan.hotel
    lines = [f"# {plan.title}", "", plan.overview, ""]
    if plan.best_time_to_visit:
        lines += [f"**Best time to visit:** {plan.best_time_to_visit}", ""]

    lines += [
        "## Getting there",
        f"{transport.mode}: {transport.description} - "
        f"{money(transport.price_per_person_one_way)} per person one way"
        f"{_price_note(transport.price_per_person_one_way, transport.sourced)}",
        "",
        "## Where to stay",
        f"{hotel.name} ({hotel.area}): {hotel.description} - "
        f"{money(hotel.price_per_night_per_room)} per room per night"
        f"{_price_note(hotel.price_per_night_per_room, hotel.sourced)}",
        "",
    ]

    for day in plan.days:
        lines += [f"## Day {day.day}: {day.theme}"]
        for activity in day.activities:
            cost = money(activity.cost_per_person) if activity.cost_per_person > 0 else "free"
            note = _price_note(activity.cost_per_person, activity.sourced)
            lines.append(f"- **{activity.time_of_day}** - {activity.title}: {activity.description} ({cost}{note})")
        lines.append("")

    if plan.budget:
        lines += ["## Budget"]
        for label, amount in plan.budget.lines.items():
            lines.append(f"- {label}: {money(amount)}")
        lines += [
            f"- **Total: {money(plan.budget.total)}** ({money(plan.budget.per_person)} per person)",
            f"- Based on {plan.budget.people} travellers, {plan.budget.rooms} rooms, {plan.budget.nights} nights",
            "",
        ]

    if plan.tips:
        lines += ["## Tips"] + [f"- {tip}" for tip in plan.tips] + [""]

    if plan.sources:
        lines += ["## Sources"] + [f"- [{source.id}] {source.title} - {source.url}" for source in plan.sources]
        lines.append("")

    lines.append("Prices are estimates. Always confirm them before booking.")
    return "\n".join(lines)


# ----------------------------------------------------------------------
# PDF
# ----------------------------------------------------------------------
def _pdf_safe(text: str) -> str:
    """The standard PDF font only knows basic Latin letters, so replace or drop other symbols."""
    replacements = {"₹": "Rs ", "–": "-", "—": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "→": "->", "•": "-"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "ignore").decode("latin-1")


def plan_to_pdf(plan: TripPlan, money: Money) -> bytes:
    """The plan as a PDF file (returned as bytes)."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    def write(text: str, size: int = 11, bold: bool = False) -> None:
        """Write one paragraph and move to the next line."""
        pdf.set_font("Helvetica", "B" if bold else "", size)
        pdf.multi_cell(0, size * 0.55, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")

    write(plan.title, size=18, bold=True)
    write(plan.overview)
    pdf.ln(2)

    write("Getting there", size=14, bold=True)
    transport = plan.transport
    write(
        f"{transport.mode}: {transport.description}\n"
        f"{money(transport.price_per_person_one_way)} per person one way"
        f"{_price_note(transport.price_per_person_one_way, transport.sourced)}"
    )
    write("Where to stay", size=14, bold=True)
    hotel = plan.hotel
    write(
        f"{hotel.name} ({hotel.area}): {hotel.description}\n"
        f"{money(hotel.price_per_night_per_room)} per room per night"
        f"{_price_note(hotel.price_per_night_per_room, hotel.sourced)}"
    )

    for day in plan.days:
        pdf.ln(2)
        write(f"Day {day.day}: {day.theme}", size=14, bold=True)
        for activity in day.activities:
            cost = money(activity.cost_per_person) if activity.cost_per_person > 0 else "free"
            note = _price_note(activity.cost_per_person, activity.sourced)
            write(f"- {activity.time_of_day}: {activity.title} ({cost}{note})\n  {activity.description}")

    if plan.budget:
        pdf.ln(2)
        write("Budget", size=14, bold=True)
        for label, amount in plan.budget.lines.items():
            write(f"- {label}: {money(amount)}")
        write(f"Total: {money(plan.budget.total)} ({money(plan.budget.per_person)} per person)", bold=True)

    if plan.tips:
        pdf.ln(2)
        write("Tips", size=14, bold=True)
        for tip in plan.tips:
            write(f"- {tip}")

    if plan.sources:
        pdf.ln(2)
        write("Sources", size=14, bold=True)
        for source in plan.sources:
            write(f"[{source.id}] {source.title}\n{source.url}", size=9)

    write("Prices are estimates. Always confirm them before booking.", size=9)
    return bytes(pdf.output())


# ----------------------------------------------------------------------
# Calendar (.ics)
# ----------------------------------------------------------------------
def _ics_escape(text: str) -> str:
    """Characters with a special meaning in .ics files must be escaped."""
    text = text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return text.replace("\n", "\\n")


def plan_to_ics(plan: TripPlan, start_date: str) -> str:
    """One all-day calendar event per trip day. start_date looks like '2026-10-20'."""
    first_day = date.fromisoformat(start_date)
    created = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//TripGenie//EN"]
    for index, day in enumerate(plan.days):
        day_date = first_day + timedelta(days=index)
        details = "\n".join(f"{a.time_of_day}: {a.title}" for a in day.activities)
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uuid.uuid4()}@tripgenie",
            f"DTSTAMP:{created}",
            f"DTSTART;VALUE=DATE:{day_date:%Y%m%d}",
            f"DTEND;VALUE=DATE:{day_date + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{_ics_escape(f'Day {day.day}: {day.theme}')}",
            f"DESCRIPTION:{_ics_escape(details)}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
