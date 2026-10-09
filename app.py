"""
TripGenie - AI travel planner.

Run it with:   streamlit run app.py

This file only connects the pieces together. The real work happens in:
    services/   search, AI agent, budget, weather, storage ...
    ui/         the form, the plan view and the history view
"""
import uuid

import streamlit as st

from config.settings import CURRENCIES, settings
from models import TripPlan, TripRequest
from services.agent_service import PlanError, TripGenieAgent
from services.currency_service import CurrencyService
from services.location_service import LocationService
from services.storage_service import TripStorage
from ui.form import render_form
from ui.history import render_history
from ui.results import render_plan
from ui.styles import apply_styles, render_header, render_tips
from utils.logger import get_logger, setup_logging

# This must be the first Streamlit command in the script
st.set_page_config(page_title=settings.page_title, page_icon=settings.page_icon, layout="centered")
setup_logging()
logger = get_logger(__name__)
apply_styles()

# What we tell the user when each pipeline step is finished
STEP_MESSAGES = {
    "research": "Searched the web for prices and places",
    "draft": "Wrote the itinerary",
    "refine": "Updated the itinerary",
    "verify": "Checked every price against its sources",
    "budget": "Calculated the budget",
}

# ----------------------------------------------------------------------
# Start-up checks
# ----------------------------------------------------------------------
missing_keys = settings.api.missing_keys()
if missing_keys:
    render_header()
    st.error(f"Missing API key: {', '.join(missing_keys)}")
    st.markdown(
        "Create a file named `.env` next to `app.py` (see `.env.example`) and add your key, "
        "or add it to Streamlit secrets when you deploy. Then restart the app."
    )
    st.stop()


# ----------------------------------------------------------------------
# Shared services. cache_resource = created once, shared by all visitors
# ----------------------------------------------------------------------
@st.cache_resource
def get_location_service() -> LocationService:
    return LocationService()


@st.cache_resource
def get_agent() -> TripGenieAgent:
    return TripGenieAgent()


@st.cache_resource
def get_currency_service() -> CurrencyService:
    return CurrencyService()


@st.cache_resource
def get_local_storage() -> TripStorage:
    return TripStorage(settings.storage.history_file)


def get_storage() -> TripStorage:
    """File storage on your own computer, or a private in-memory history per visitor online."""
    if settings.storage.mode == "session":
        if "storage" not in st.session_state:
            st.session_state.storage = TripStorage(None)
        return st.session_state.storage
    return get_local_storage()


location_service = get_location_service()
agent = get_agent()
storage = get_storage()

# What this visitor is working on right now
st.session_state.setdefault("plan", None)  # the current TripPlan (as a dict)
st.session_state.setdefault("request", None)  # the TripRequest it was made from (as a dict)
st.session_state.setdefault("thread_id", None)  # the agent's memory for this plan
st.session_state.setdefault("trip_id", None)  # id of the saved copy in the history
st.session_state.setdefault("chat", [])  # follow-up requests and answers
st.session_state.setdefault("runs", 0)  # how many plans + changes were asked for


# ----------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------
with st.sidebar:
    st.header("Settings")
    currency = st.selectbox("Show prices in", CURRENCIES)
    save_history = st.checkbox("Save my trips", value=True)

    rate = get_currency_service().get_rate_from_inr(currency)
    if rate is None:
        st.warning("Could not load exchange rates. Showing prices in INR.")
        currency, rate = "INR", 1.0

    runs_left = settings.limits.max_runs_per_session - st.session_state.runs
    st.caption(f"Plans and changes left in this session: {max(runs_left, 0)}")

    with st.expander("About"):
        st.write(f"TripGenie v{settings.version}")
        st.write(f"AI model: {settings.model.model_name}")
        st.write("Search: " + ("Tavily + DuckDuckGo" if settings.api.tavily_api_key else "DuckDuckGo only"))
        st.write(f"LangSmith tracing: {'on' if settings.tracing_enabled else 'off'}")


# ----------------------------------------------------------------------
# Actions
# ----------------------------------------------------------------------
def run_pipeline(steps, success_label: str) -> bool:
    """Show the live progress of the agent. `steps` is the generator returned by the agent.
    Returns True when everything worked."""
    with st.status("TripGenie is working...", expanded=True) as status:
        try:
            for step in steps:
                st.write(f"✅ {STEP_MESSAGES.get(step, step)}")
        except PlanError as error:
            status.update(label="Something went wrong", state="error")
            st.error(str(error))
            return False
        status.update(label=success_label, state="complete", expanded=False)
    return True


def create_new_plan(request: TripRequest) -> None:
    """The user clicked 'Plan my trip'."""
    if runs_left <= 0:
        st.error("You have used all the plans for this session. Please try again later.")
        return

    st.session_state.runs += 1
    thread_id = uuid.uuid4().hex  # a new thread = a new conversation with its own memory
    logger.log_user_action("plan_trip", {"to": request.to_city, "days": request.days})

    if not run_pipeline(agent.start_trip(request, thread_id), "Your trip plan is ready!"):
        return

    plan = agent.get_plan(thread_id)
    st.session_state.plan = plan.model_dump()
    st.session_state.request = request.model_dump()
    st.session_state.thread_id = thread_id
    st.session_state.chat = []
    st.session_state.trip_id = storage.save_trip(request, plan.model_dump()) if save_history else None


def change_plan(instruction: str) -> None:
    """The user asked for a change under the plan."""
    if runs_left <= 0:
        st.error("You have used all the plans for this session. Please try again later.")
        return

    st.session_state.runs += 1
    logger.log_user_action("change_plan", {"length": len(instruction)})

    if not run_pipeline(agent.refine_trip(instruction, st.session_state.thread_id), "Plan updated!"):
        return

    plan = agent.get_plan(st.session_state.thread_id)
    st.session_state.plan = plan.model_dump()
    st.session_state.chat.append({"role": "user", "text": instruction})
    st.session_state.chat.append({"role": "assistant", "text": f"Done. I updated the plan: {plan.title}"})
    if st.session_state.trip_id:
        storage.update_plan(st.session_state.trip_id, plan.model_dump())
    st.rerun()  # redraw the page so the new plan is shown


# ----------------------------------------------------------------------
# Page
# ----------------------------------------------------------------------
render_header()
plan_tab, history_tab, tips_tab = st.tabs(["Plan a trip", "History", "Tips"])

with plan_tab:
    new_request = render_form(location_service)
    if new_request:
        create_new_plan(new_request)

    if st.session_state.plan:
        st.divider()
        request = TripRequest.model_validate(st.session_state.request)
        render_plan(
            TripPlan.model_validate(st.session_state.plan),
            start_date=request.start_date,
            currency=currency,
            rate=rate,
            key_prefix=st.session_state.thread_id,
            location_service=location_service,
            destination=request.to_city,
        )

        # Follow-up changes ("make day 2 cheaper")
        st.divider()
        st.subheader("Want to change something?")
        for message in st.session_state.chat:
            with st.chat_message(message["role"]):
                st.write(message["text"])
        with st.form("change_form", clear_on_submit=True):
            change_text = st.text_input(
                "Tell TripGenie what to change",
                placeholder="e.g. Make day 2 cheaper, or add a day trip",
                max_chars=settings.limits.max_followup_length,
            )
            send = st.form_submit_button("Update my plan")
        if send and change_text.strip():
            change_plan(change_text)

with history_tab:
    render_history(storage, currency, rate, memory_mode=settings.storage.mode == "session")

with tips_tab:
    render_tips()
