"""Input checks. Everything the user types is checked here before it is used."""
import re
from datetime import date

from config.settings import settings
from models import TripRequest


class ValidationError(Exception):
    """Raised when the user's input is not acceptable. The message is safe to show to the user."""


# Characters we never want inside an AI prompt: new lines, tabs and other control characters
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def clean_for_prompt(text: str, max_length: int = 500) -> str:
    """Make free text safe to put inside an AI prompt.

    - removes <script> blocks first, then any other html tags
    - removes < and > so nobody can close our <user_notes> tag
    - turns new lines / tabs into spaces (so text cannot fake a new instruction block)
    - cuts the text at max_length
    """
    if not text:
        return ""
    text = re.sub(r"<script.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]*>", "", text)
    text = text.replace("<", "").replace(">", "")
    text = _CONTROL_CHARS.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_length:
        text = text[:max_length].rstrip() + "..."
    return text


def check_location(name: str, label: str) -> str:
    """Check a place name. Returns the cleaned name or raises ValidationError."""
    name = (name or "").strip()
    if len(name) < 2:
        raise ValidationError(f"{label} is too short.")
    if len(name) > 100:
        raise ValidationError(f"{label} is too long.")
    if re.search(r"[<>{}\[\]\\]", name):
        raise ValidationError(f"{label} contains characters that are not allowed.")
    return name


def validate_trip_request(request: TripRequest) -> TripRequest:
    """Check the whole request.

    Returns a cleaned copy (the free-text notes are made prompt-safe).
    Raises ValidationError with ALL the problems found, one per line.
    """
    problems = []

    # Places
    try:
        from_city = check_location(request.from_city, "Starting location")
    except ValidationError as error:
        problems.append(str(error))
        from_city = request.from_city
    try:
        to_city = check_location(request.to_city, "Destination")
    except ValidationError as error:
        problems.append(str(error))
        to_city = request.to_city
    if from_city.strip().lower() == to_city.strip().lower():
        problems.append("Starting location and destination must be different.")

    # Numbers
    if not 1 <= request.people <= settings.limits.max_people:
        problems.append(f"Number of travellers must be between 1 and {settings.limits.max_people}.")
    if not 1 <= request.days <= settings.limits.max_days:
        problems.append(f"Trip length must be between 1 and {settings.limits.max_days} days.")
    if request.total_budget_per_person < 0:
        problems.append("Budget cannot be negative.")

    # Date
    try:
        if date.fromisoformat(request.start_date) < date.today():
            problems.append("The start date cannot be in the past.")
    except ValueError:
        problems.append("The start date is not valid.")

    if problems:
        raise ValidationError("\n".join(problems))

    return request.model_copy(
        update={
            "from_city": from_city,
            "to_city": to_city,
            "notes": clean_for_prompt(request.notes, settings.limits.max_notes_length),
        }
    )
