"""The 'History' tab: saved trips, export / import and delete."""
from functools import partial

import streamlit as st

from models import TripPlan
from services.export_service import plan_to_markdown
from services.storage_service import TripStorage
from ui.results import render_plan
from utils.formatters import format_money, slugify

MAX_TRIPS_SHOWN = 20  # every saved plan is drawn on the page, so keep the list short


def render_history(storage: TripStorage, currency: str, rate: float, memory_mode: bool) -> None:
    """Show the saved trips."""
    st.subheader("Your saved trips")
    if memory_mode:
        st.info(
            "On this website your trips are kept only for this visit. "
            "Use **Download all** to keep them, and **Import** to bring them back later."
        )

    _render_export_import(storage)

    trips = storage.get_all_trips(limit=MAX_TRIPS_SHOWN)
    if not trips:
        st.write("No saved trips yet. Plan a trip and it will appear here.")
        return

    money = partial(format_money, currency=currency, rate=rate)
    for trip in trips:
        title = f"{trip.from_city} → {trip.to_city} | {trip.days} days | {trip.timestamp[:10]}"
        with st.expander(title):
            if trip.plan:
                plan = TripPlan.model_validate(trip.plan)
                render_plan(plan, trip.start_date, currency, rate, f"history_{trip.id}", show_extras=False)
                st.download_button(
                    "Download as text",
                    plan_to_markdown(plan, money),
                    file_name=f"{slugify(plan.title) or 'trip'}.md",
                    key=f"history_{trip.id}_download",
                )
            else:
                # Trips saved by version 1 of TripGenie are plain text
                st.markdown(trip.legacy_text or "This trip has no saved plan.")

            if st.button("Delete this trip", key=f"history_{trip.id}_delete"):
                storage.delete_trip(trip.id)
                st.rerun()

    _render_clear_all(storage)


def _render_export_import(storage: TripStorage) -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download all trips (JSON)",
            storage.export_json(),
            file_name="tripgenie-history.json",
            mime="application/json",
        )
    with col2:
        uploaded = st.file_uploader("Import trips", type="json", label_visibility="collapsed")
        if uploaded is not None and st.button("Import this file"):
            added = storage.import_json(uploaded.getvalue().decode("utf-8", errors="ignore"))
            st.success(f"Imported {added} trip(s).")
            st.rerun()


def _render_clear_all(storage: TripStorage) -> None:
    st.divider()
    confirmed = st.checkbox("Yes, I want to delete ALL my saved trips")
    if st.button("Delete all trips", disabled=not confirmed):
        storage.clear_all()
        st.rerun()
