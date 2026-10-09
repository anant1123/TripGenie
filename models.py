"""
Data models for TripGenie.

These classes describe the shape of the data that moves through the app:

    TripRequest   what the user asked for (from the form)
    TripPlanDraft what the AI writes (itinerary, hotel, transport ...)
    TripPlan      the draft + things our own code adds (sources, budget, weather, warnings)
"""
from typing import Optional

from pydantic import BaseModel, Field


class TripRequest(BaseModel):
    """What the user typed into the form."""

    from_city: str
    to_city: str
    start_date: str  # "YYYY-MM-DD"
    days: int
    people: int
    group_type: str = "Friends"
    transport: str = "Any"
    hotel_budget: str = ""
    food_prefs: list[str] = Field(default_factory=list)
    trip_styles: list[str] = Field(default_factory=list)
    pace: str = "Balanced"
    stay_types: list[str] = Field(default_factory=list)
    notes: str = ""
    total_budget_per_person: float = 0  # 0 means "no limit"
    # Coordinates of the destination (used to look up the weather)
    to_lat: Optional[float] = None
    to_lon: Optional[float] = None


class Activity(BaseModel):
    """One thing to do (a place to visit, a meal, a local ride ...)."""

    time_of_day: str = Field(description="Morning, Afternoon or Evening")
    title: str
    description: str
    place_name: str = Field(default="", description="Name of the place (used to find it on the map)")
    category: str = Field(
        default="sightseeing",
        description="sightseeing, food, local_transport, shopping or other",
    )
    cost_per_person: float = Field(default=0, description="Cost per person in INR. Use 0 if free")
    source_ids: list[int] = Field(
        default_factory=list,
        description="Numbers of the search results that support the price",
    )
    sourced: bool = False  # filled in by our code, not by the AI


class DayPlan(BaseModel):
    """One day of the trip."""

    day: int
    theme: str
    activities: list[Activity]


class TransportOption(BaseModel):
    """How to get from the start city to the destination."""

    mode: str
    description: str
    price_per_person_one_way: float = Field(description="INR per person, one way")
    source_ids: list[int] = Field(default_factory=list)
    sourced: bool = False


class HotelOption(BaseModel):
    """Where to stay."""

    name: str
    area: str = ""
    description: str = ""
    price_per_night_per_room: float = Field(description="INR per room per night")
    source_ids: list[int] = Field(default_factory=list)
    sourced: bool = False


class TripPlanDraft(BaseModel):
    """The plan as written by the AI."""

    title: str
    overview: str
    best_time_to_visit: str = ""
    transport: TransportOption
    hotel: HotelOption
    days: list[DayPlan]
    tips: list[str] = Field(default_factory=list)


class Source(BaseModel):
    """A web page that one of the prices or facts came from."""

    id: int
    title: str
    url: str
    category: str = ""


class BudgetSummary(BaseModel):
    """Result of the budget calculator."""

    lines: dict[str, float]  # label -> total cost in INR
    total: float
    per_person: float
    people: int
    rooms: int
    nights: int


class TripPlan(TripPlanDraft):
    """The final plan shown to the user."""

    sources: list[Source] = Field(default_factory=list)
    budget: Optional[BudgetSummary] = None
    weather: Optional[dict] = None
    warnings: list[str] = Field(default_factory=list)
    unsourced_count: int = 0  # how many priced items are only estimates
