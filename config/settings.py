"""
Settings for TripGenie.

Every number you may want to change lives in this file.
Secret keys are NOT written here. They come from the .env file
(or from Streamlit secrets when the app is deployed online).
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# The project root is the folder that contains app.py and main.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Read the .env file (if there is one)
load_dotenv(PROJECT_ROOT / ".env")

# Hotel budgets shown in the app: label -> (lowest, highest) price per night in rupees.
# A highest value of None means "no upper limit".
HOTEL_BUDGETS = {
    "Budget (₹0-1000)": (0, 1000),
    "Economy (₹1000-3000)": (1000, 3000),
    "Mid-Range (₹3000-6000)": (3000, 6000),
    "Premium (₹6000-12000)": (6000, 12000),
    "Luxury (₹12000+)": (12000, None),
}

# Currencies the user can choose to DISPLAY prices in. Plans are always made in INR.
CURRENCIES = ["INR", "USD", "EUR", "GBP"]


def get_secret(name: str) -> str:
    """Read a secret from the environment (.env) first, then from Streamlit secrets."""
    value = os.getenv(name, "")
    if value:
        return value
    try:
        import streamlit as st

        return str(st.secrets.get(name, ""))
    except Exception:
        # No secrets file (or Streamlit is not installed): the secret simply is not set
        return ""


def _number_from_env(name: str, default: int) -> int:
    """Read a whole number from the environment, or use the default."""
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass
class ApiConfig:
    """Keys for the online services."""

    groq_api_key: str = field(default_factory=lambda: get_secret("GROQ_API_KEY"))
    tavily_api_key: str = field(default_factory=lambda: get_secret("TAVILY_API_KEY"))

    def missing_keys(self) -> List[str]:
        """Keys the app cannot run without. (Tavily is optional: DuckDuckGo is the backup.)"""
        return [] if self.groq_api_key else ["GROQ_API_KEY"]


@dataclass
class ModelConfig:
    """The AI model. If the main model fails, the smaller backup model is tried."""

    model_name: str = "openai/gpt-oss-120b"
    fallback_model_name: str = "openai/gpt-oss-20b"
    temperature: float = 0.3
    max_retries: int = 2
    timeout: int = 120


@dataclass
class SearchConfig:
    """Web search."""

    results_per_search: int = 3
    use_ddg_fallback: bool = True
    cache_seconds: int = 3600  # same search within 1 hour = no new request
    snippet_length: int = 400  # keep each search result short to save AI tokens


@dataclass
class LocationConfig:
    """OpenStreetMap Nominatim (free). Their rules: max 1 request/second + a User-Agent."""

    nominatim_url: str = "https://nominatim.openstreetmap.org/search"
    user_agent: str = "TripGenie-Education-Project/2.0 (github.com/anant1123/Trip_Planner-Agent)"
    rate_limit_delay: float = 1.0
    max_results: int = 5
    timeout: int = 10
    cache_seconds: int = 86400  # place names do not change, keep them for a day


@dataclass
class LimitsConfig:
    """Limits that protect your free API quota when the app is public."""

    max_people: int = 20
    max_days: int = 14  # longer trips make the AI answer too long
    max_notes_length: int = 1000
    max_followup_length: int = 300
    # How many plans + changes one visitor may ask for in one session
    max_runs_per_session: int = field(default_factory=lambda: _number_from_env("MAX_RUNS_PER_SESSION", 10))


@dataclass
class StorageConfig:
    """Where trip history is kept.

    "local"   -> data/trip_history.json (good for running on your own computer)
    "session" -> only in the visitor's browser session (use this on a public website,
                 so people never see each other's trips)
    """

    mode: str = field(default_factory=lambda: (get_secret("STORAGE_MODE") or "local").lower())
    history_file: Path = PROJECT_ROOT / "data" / "trip_history.json"


@dataclass
class BudgetConfig:
    """Rules used by the budget calculator."""

    people_per_room: int = 2


class Settings:
    """All settings in one place:  from config.settings import settings"""

    version = "2.0.0"
    page_title = "TripGenie - AI Travel Planner"
    page_icon = "🌍"

    def __init__(self):
        self.api = ApiConfig()
        self.model = ModelConfig()
        self.search = SearchConfig()
        self.location = LocationConfig()
        self.limits = LimitsConfig()
        self.storage = StorageConfig()
        self.budget = BudgetConfig()

    @property
    def tracing_enabled(self) -> bool:
        """LangSmith tracing is OFF unless you turn it on yourself in .env."""
        flags = (os.getenv("LANGCHAIN_TRACING_V2", ""), os.getenv("LANGSMITH_TRACING", ""))
        return any(flag.lower() == "true" for flag in flags)


# One shared settings object. Creating it never fails, even if keys are missing.
settings = Settings()
