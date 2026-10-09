"""The planning form. Returns a checked TripRequest when the user clicks 'Plan my trip'."""
from datetime import date, timedelta
from typing import Optional

import streamlit as st

from config.settings import HOTEL_BUDGETS, settings
from models import TripRequest
from services.location_service import Location, LocationService
from utils.formatters import format_duration
from utils.validators import ValidationError, validate_trip_request


def _pick_place(label: str, placeholder: str, key: str, location_service: LocationService) -> Optional[Location]:
    """A text box + a list of matching places. Returns the place the user picked (or None)."""
    text = st.text_input(label, placeholder=placeholder, key=f"{key}_text")
    if len(text.strip()) < 2:
        return None

    # Searches are remembered by LocationService, so re-running the page is free
    with st.spinner("Searching..."):
        places = location_service.search(text)
    if not places:
        st.warning("No place found. Try another spelling.")
        return None

    labels = [place.label for place in places]
    chosen = st.selectbox("Pick the right place", labels, key=f"{key}_choice")
    return places[labels.index(chosen)]


def render_form(location_service: LocationService) -> Optional[TripRequest]:
    """Show the form. Returns a TripRequest only in the run where the button was clicked."""
    st.subheader("Where are you going?")
    col1, col2 = st.columns(2)
    with col1:
        from_place = _pick_place("Starting from", "e.g. Kota", "from", location_service)
    with col2:
        to_place = _pick_place("Going to", "e.g. New Delhi", "to", location_service)

    st.subheader("Trip details")
    col1, col2, col3 = st.columns(3)
    with col1:
        start_date = st.date_input(
            "Start date",
            value=date.today() + timedelta(days=14),
            min_value=date.today(),
        )
    with col2:
        days = st.number_input("Days", min_value=1, max_value=settings.limits.max_days, value=3)
        st.caption(f"Trip length: {format_duration(int(days))}")
    with col3:
        people = st.number_input("Travellers", min_value=1, max_value=settings.limits.max_people, value=2)

    col1, col2 = st.columns(2)
    with col1:
        group_type = st.selectbox("Group type", ["Solo", "Couple", "Family", "Friends", "Business"], index=3)
        transport = st.selectbox("Transport", ["Any", "Train", "Flight", "Bus", "Car"])
    with col2:
        hotel_budget = st.select_slider("Hotel budget per night", options=list(HOTEL_BUDGETS), value="Economy (₹1000-3000)")
        total_budget = st.number_input(
            "Total budget per person in ₹ (0 = no limit)", min_value=0, value=0, step=1000
        )

    st.subheader("Preferences")
    col1, col2 = st.columns(2)
    with col1:
        food_prefs = st.multiselect(
            "Food", ["Vegetarian", "Vegan", "Non-Vegetarian", "Jain", "Halal", "Street food", "Local cuisine"]
        )
        stay_types = st.multiselect("Where to stay", ["Hotel", "Hostel", "Homestay", "Resort", "Airbnb"])
    with col2:
        trip_styles = st.multiselect(
            "Trip style",
            ["Culture & history", "Nature", "Adventure", "Religious", "Food", "Shopping", "Relaxation", "Nightlife"],
        )
        pace = st.radio("Pace", ["Relaxed", "Balanced", "Packed"], index=1, horizontal=True)

    notes = st.text_area(
        "Special requirements (optional)",
        placeholder="e.g. travelling with a senior, wheelchair access, we love photography ...",
        max_chars=settings.limits.max_notes_length,
    )

    if not st.button("✨ Plan my trip", type="primary"):
        return None

    if from_place is None or to_place is None:
        st.error("Please type and pick both places first.")
        return None

    request = TripRequest(
        from_city=from_place.short_name(),
        to_city=to_place.short_name(),
        start_date=start_date.isoformat(),
        days=int(days),
        people=int(people),
        group_type=group_type,
        transport=transport,
        hotel_budget=hotel_budget,
        food_prefs=food_prefs,
        trip_styles=trip_styles,
        pace=pace,
        stay_types=stay_types,
        notes=notes,
        total_budget_per_person=float(total_budget),
        to_lat=to_place.lat,
        to_lon=to_place.lon,
    )
    try:
        return validate_trip_request(request)
    except ValidationError as error:
        st.error(str(error))
        return None
