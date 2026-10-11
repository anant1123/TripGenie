"""Shows a trip plan on the page: overview, days, budget, weather, map, sources and downloads."""
from functools import partial
from typing import Optional

import pandas as pd
import streamlit as st

from models import DayPlan, TripPlan
from services.export_service import plan_to_ics, plan_to_markdown, plan_to_pdf
from services.location_service import LocationService
from utils.formatters import format_money, slugify


def _badge(price: float, sourced: bool) -> str:
    """✅ if a web page supports the price, ⚠️ if it is only an estimate."""
    if price <= 0:
        return ""
    return "✅ sourced" if sourced else "⚠️ estimate"


def render_plan(
    plan: TripPlan,
    start_date: str,
    currency: str,
    rate: float,
    key_prefix: str,
    location_service: Optional[LocationService] = None,
    destination: str = "",
    show_extras: bool = True,
) -> None:
    """Draw the whole plan.

    key_prefix   makes the widget keys unique (needed when several plans are on one page)
    show_extras  False hides the map and the download buttons (used in the history list)
    """
    # money(500) -> "₹500" (or "$6.00" if the user picked USD)
    money = partial(format_money, currency=currency, rate=rate)

    st.header(plan.title)
    st.write(plan.overview)
    if plan.best_time_to_visit:
        st.caption(f"Best time to visit: {plan.best_time_to_visit}")
    for warning in plan.warnings:
        st.warning(warning)

    _render_summary(plan, money)
    _render_weather(plan)
    _render_transport_and_hotel(plan, money)

    st.subheader("Day by day")
    for day in plan.days:
        _render_day(day, money)

    _render_budget(plan, money, rate)

    if show_extras and location_service is not None and destination:
        _render_map(plan, destination, location_service, key_prefix)

    if plan.tips:
        st.subheader("Tips")
        for tip in plan.tips:
            st.markdown(f"- {tip}")

    _render_sources(plan)

    if show_extras:
        _render_downloads(plan, start_date, money, key_prefix)


# ----------------------------------------------------------------------
# Small pieces
# ----------------------------------------------------------------------
def _render_summary(plan: TripPlan, money) -> None:
    if not plan.budget:
        return
    budget = plan.budget
    col1, col2, col3 = st.columns(3)
    col1.metric("Estimated total", money(budget.total))
    col2.metric("Per person", money(budget.per_person))
    col3.metric("Stay", f"{budget.nights} nights, {budget.rooms} rooms")
    if plan.unsourced_count:
        st.caption(f"{plan.unsourced_count} price(s) are estimates without a web source (marked ⚠️).")


def _render_weather(plan: TripPlan) -> None:
    if not plan.weather:
        return
    if plan.weather["kind"] == "forecast":
        title = "Weather forecast"
    else:
        title = "Weather on the same dates last year (a rough guide, not a forecast)"
    with st.expander(title):
        table = pd.DataFrame(plan.weather["days"]).rename(
            columns={"date": "Date", "temp_min": "Min °C", "temp_max": "Max °C", "rain_mm": "Rain (mm)"}
        )
        st.dataframe(table, hide_index=True)


def _render_transport_and_hotel(plan: TripPlan, money) -> None:
    transport, hotel = plan.transport, plan.hotel
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Getting there")
        st.markdown(
            f"**{transport.mode}**  \n{transport.description}  \n"
            f"{money(transport.price_per_person_one_way)} per person, one way "
            f"{_badge(transport.price_per_person_one_way, transport.sourced)}"
        )
    with col2:
        st.subheader("Where to stay")
        st.markdown(
            f"**{hotel.name}** ({hotel.area})  \n{hotel.description}  \n"
            f"{money(hotel.price_per_night_per_room)} per room per night "
            f"{_badge(hotel.price_per_night_per_room, hotel.sourced)}"
        )


def _render_day(day: DayPlan, money) -> None:
    with st.expander(f"Day {day.day}: {day.theme}", expanded=(day.day == 1)):
        for activity in day.activities:
            cost = money(activity.cost_per_person) + " per person" if activity.cost_per_person > 0 else "Free"
            st.markdown(
                f"**{activity.time_of_day}: {activity.title}**  \n"
                f"{activity.description}  \n"
                f"{cost} {_badge(activity.cost_per_person, activity.sourced)}"
            )


def _render_budget(plan: TripPlan, money, rate: float) -> None:
    if not plan.budget:
        return
    st.subheader("Budget")
    budget = plan.budget
    table = pd.DataFrame({"Item": list(budget.lines), "Cost": [money(amount) for amount in budget.lines.values()]})
    st.dataframe(table, hide_index=True)
    st.caption(
        f"Based on {budget.people} travellers, {budget.rooms} rooms, {budget.nights} nights, "
        "and a round trip. Total: " + money(budget.total)
    )
    # The chart uses the same currency as the table
    chart = pd.DataFrame({"Cost": [amount * rate for amount in budget.lines.values()]}, index=list(budget.lines))
    st.bar_chart(chart)


def _render_map(plan: TripPlan, destination: str, location_service: LocationService, key_prefix: str) -> None:
    """Show one day's places on a map. Places are looked up only when the user asks."""
    st.subheader("Map")
    day_names = [f"Day {day.day}: {day.theme}" for day in plan.days]
    chosen = st.selectbox("Choose a day", day_names, key=f"{key_prefix}_map_day")
    day = plan.days[day_names.index(chosen)]

    # The result is saved in session_state, otherwise it would vanish on the next click
    state_key = f"{key_prefix}_map_{day.day}"
    if st.button("Show this day on the map", key=f"{key_prefix}_map_button"):
        with st.spinner("Finding the places..."):
            points = []
            for activity in day.activities:
                place = activity.place_name or activity.title
                coordinates = location_service.geocode_place(place, destination)
                if coordinates:
                    points.append({"lat": coordinates[0], "lon": coordinates[1], "name": place})
        st.session_state[state_key] = points

    points = st.session_state.get(state_key)
    if points:
        st.map(pd.DataFrame(points)[["lat", "lon"]])
        st.caption("Shown: " + ", ".join(point["name"] for point in points))
    elif points == []:
        st.info("Could not find these places on the map.")


def _render_sources(plan: TripPlan) -> None:
    st.subheader("Sources")
    if not plan.sources:
        st.caption("No web pages were used for the prices in this plan.")
        return
    for source in plan.sources:
        st.markdown(f"[{source.id}] [{source.title}]({source.url})")


def _render_downloads(plan: TripPlan, start_date: str, money, key_prefix: str) -> None:
    name = slugify(plan.title) or "trip-plan"
    st.subheader("Download")
    col1, col2, col3 = st.columns(3)

    col1.download_button(
        "Text (.md)",
        plan_to_markdown(plan, money),
        file_name=f"{name}.md",
        mime="text/markdown",
        key=f"{key_prefix}_md",
    )
    try:
        col2.download_button(
            "PDF", plan_to_pdf(plan, money), file_name=f"{name}.pdf", mime="application/pdf", key=f"{key_prefix}_pdf"
        )
    except Exception:  # a PDF problem must never break the page
        col2.caption("PDF is not available right now.")
    if start_date:
        col3.download_button(
            "Calendar (.ics)",
            plan_to_ics(plan, start_date),
            file_name=f"{name}.ics",
            mime="text/calendar",
            key=f"{key_prefix}_ics",
        )
