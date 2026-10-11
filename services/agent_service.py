"""
TripGenie agent: a fixed pipeline built with LangGraph.

    New trip:         research -> draft  -> verify -> budget
    Follow-up change: refine   ->           verify -> budget

    research  our code searches the web (transport, hotels, attractions, food, best time)
    draft     the AI writes the plan using ONLY those search results
    refine    the AI edits the existing plan ("make day 2 cheaper")
    verify    our code checks every price against its sources and attaches the real URLs
    budget    our code adds up the costs (rooms for the group, round trip ...)

LangGraph keeps the plan in memory for each conversation (thread_id), which is what
makes follow-up changes possible. The memory is cleared when the app restarts.
"""
import time
from datetime import date
from typing import Iterator, List, Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from config.prompts import DRAFT_SYSTEM_PROMPT, REFINE_SYSTEM_PROMPT
from config.settings import settings
from models import TripPlan, TripPlanDraft, TripRequest
from services.budget_service import calculate_budget
from services.research_service import ResearchService, format_research_for_prompt
from services.search_service import SearchService
from services.verify_service import verify_plan
from services.weather_service import get_weather, weather_to_text
from utils.logger import get_logger
from utils.validators import clean_for_prompt

logger = get_logger(__name__)


class PlanError(Exception):
    """The plan could not be made. The message is safe to show to the user."""


class TripState(TypedDict, total=False):
    """The data that moves through the pipeline. Everything is plain dicts/lists/text."""

    request: dict  # the TripRequest
    instruction: str  # follow-up change request ("" for a brand new trip)
    research: list  # numbered web search results
    weather: dict  # weather for the trip dates (can be missing)
    plan: dict  # the TripPlan


class TripGenieAgent:
    """Creates trip plans and changes them when the user asks."""

    def __init__(self, search_service=None, primary_llm=None, fallback_llm=None):
        """Normally you call TripGenieAgent() with no arguments.
        The arguments exist so the tests can use fake search and a fake AI."""
        self.research_service = ResearchService(search_service or SearchService())

        if primary_llm is None:
            primary_llm = self._make_llm(settings.model.model_name)
            fallback_llm = self._make_llm(settings.model.fallback_model_name)
        # We try the main model first and the backup model if the main one keeps failing
        self.llms = [primary_llm] + ([fallback_llm] if fallback_llm else [])

        self.graph = self._build_graph()
        logger.info("TripGenieAgent is ready")

    # ------------------------------------------------------------------
    # Public methods (used by the app)
    # ------------------------------------------------------------------
    def start_trip(self, request: TripRequest, thread_id: str) -> Iterator[str]:
        """Make a new plan. Yields the name of each step when it finishes."""
        yield from self._run({"request": request.model_dump(), "instruction": ""}, thread_id)

    def refine_trip(self, instruction: str, thread_id: str) -> Iterator[str]:
        """Change the existing plan. Yields the name of each step when it finishes."""
        if not instruction.strip():
            raise PlanError("Please tell TripGenie what you would like to change.")
        yield from self._run({"instruction": instruction}, thread_id)

    def get_plan(self, thread_id: str) -> TripPlan:
        """Get the latest plan of a conversation."""
        snapshot = self.graph.get_state(self._config(thread_id))
        plan = snapshot.values.get("plan")
        if not plan:
            raise PlanError("There is no plan yet.")
        return TripPlan.model_validate(plan)

    # ------------------------------------------------------------------
    # Building the graph
    # ------------------------------------------------------------------
    @staticmethod
    def _make_llm(model_name: str) -> ChatGroq:
        return ChatGroq(
            model=model_name,
            temperature=settings.model.temperature,
            max_retries=settings.model.max_retries,
            timeout=settings.model.timeout,
            api_key=settings.api.groq_api_key,
        )

    def _build_graph(self):
        graph = StateGraph(TripState)
        graph.add_node("research", self._research_node)
        graph.add_node("draft", self._draft_node)
        graph.add_node("refine", self._refine_node)
        graph.add_node("verify", self._verify_node)
        graph.add_node("budget", self._budget_node)

        # A new trip starts with research. A change request goes straight to refine.
        graph.add_conditional_edges(START, self._choose_start, {"research": "research", "refine": "refine"})
        graph.add_edge("research", "draft")
        graph.add_edge("draft", "verify")
        graph.add_edge("refine", "verify")
        graph.add_edge("verify", "budget")
        graph.add_edge("budget", END)
        return graph.compile(checkpointer=MemorySaver())

    @staticmethod
    def _choose_start(state: TripState) -> str:
        return "refine" if state.get("instruction") else "research"

    @staticmethod
    def _config(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    def _run(self, input_data: dict, thread_id: str) -> Iterator[str]:
        """Run the graph and report each finished step."""
        start = time.time()
        try:
            for update in self.graph.stream(input_data, self._config(thread_id), stream_mode="updates"):
                for node_name in update:
                    yield node_name
        except PlanError:
            raise
        except Exception as error:
            logger.error("The pipeline failed", exc=error)
            raise PlanError(f"Something went wrong while planning your trip: {error}") from error
        logger.info(f"Pipeline finished in {time.time() - start:.1f}s")

    # ------------------------------------------------------------------
    # The steps (nodes)
    # ------------------------------------------------------------------
    def _research_node(self, state: TripState) -> dict:
        request = TripRequest.model_validate(state["request"])
        update = {"research": self.research_service.research(request)}

        if request.to_lat is not None and request.to_lon is not None:
            weather = get_weather(
                request.to_lat, request.to_lon, date.fromisoformat(request.start_date), request.days
            )
            if weather:
                update["weather"] = weather
        return update

    def _draft_node(self, state: TripState) -> dict:
        request = TripRequest.model_validate(state["request"])
        messages = [
            SystemMessage(content=DRAFT_SYSTEM_PROMPT),
            HumanMessage(content=self._describe_trip(request, state)),
        ]
        draft = self._ask_llm(messages)
        return {"plan": draft.model_dump()}

    def _refine_node(self, state: TripState) -> dict:
        request = TripRequest.model_validate(state["request"])
        current_plan = TripPlanDraft.model_validate(state["plan"])
        instruction = clean_for_prompt(state["instruction"], settings.limits.max_followup_length)

        text = (
            self._describe_trip(request, state)
            + "\n\nCURRENT PLAN (JSON):\n"
            + current_plan.model_dump_json()
            + f"\n\n<change_request>{instruction}</change_request>"
        )
        messages = [SystemMessage(content=REFINE_SYSTEM_PROMPT), HumanMessage(content=text)]
        draft = self._ask_llm(messages)
        return {"plan": draft.model_dump()}

    def _verify_node(self, state: TripState) -> dict:
        request = TripRequest.model_validate(state["request"])
        plan = TripPlan.model_validate(state["plan"])
        plan = verify_plan(plan, state.get("research", []), request.days)
        plan.weather = state.get("weather")
        return {"plan": plan.model_dump()}

    def _budget_node(self, state: TripState) -> dict:
        request = TripRequest.model_validate(state["request"])
        plan = TripPlan.model_validate(state["plan"])
        plan.budget, budget_warnings = calculate_budget(plan, request)
        plan.warnings += budget_warnings
        return {"plan": plan.model_dump()}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _describe_trip(request: TripRequest, state: TripState) -> str:
        """Write the traveller's request, the weather and the search results as text for the AI."""
        limit = request.total_budget_per_person
        budget_text = f"INR {limit:,.0f} per person" if limit > 0 else "no fixed limit"

        return (
            "TRAVELLER REQUEST\n"
            f"- Trip: {request.from_city} to {request.to_city}\n"
            f"- Start date: {request.start_date}, {request.days} days ({max(request.days - 1, 0)} nights)\n"
            f"- Travellers: {request.people} ({request.group_type})\n"
            f"- Transport: {request.transport}\n"
            f"- Hotel budget per night: {request.hotel_budget or 'any'}\n"
            f"- Stay type: {', '.join(request.stay_types) or 'any'}\n"
            f"- Food preferences: {', '.join(request.food_prefs) or 'local food'}\n"
            f"- Trip style: {', '.join(request.trip_styles) or 'any'}\n"
            f"- Pace: {request.pace}\n"
            f"- Total budget: {budget_text}\n"
            f"<user_notes>{request.notes or 'none'}</user_notes>\n\n"
            f"{weather_to_text(state.get('weather'))}\n\n"
            "SEARCH RESULTS\n"
            f"{format_research_for_prompt(state.get('research', []))}"
        )

    def _ask_llm(self, messages: List) -> TripPlanDraft:
        """Ask the AI for a plan. Tries each model twice before giving up."""
        last_error: Optional[Exception] = None
        for llm in self.llms:
            for attempt in range(2):
                try:
                    result = llm.with_structured_output(TripPlanDraft).invoke(messages)
                    if isinstance(result, dict):
                        result = TripPlanDraft.model_validate(result)
                    return result
                except Exception as error:
                    last_error = error
                    logger.warning(f"The AI model failed (attempt {attempt + 1}): {error}")
                    time.sleep(1)
        if "tool_use_failed" in str(last_error):
            # Groq sends this when the AI's answer is cut off or is not valid JSON.
            # It happens mostly with long trips, because the answer becomes very long.
            raise PlanError(
                "The AI could not write the plan because its answer was too long or got cut off. "
                "Try a shorter trip (5 days or fewer) and try again."
            )
        raise PlanError(f"The AI could not write the plan. Please try again. ({str(last_error)[:200]})")
