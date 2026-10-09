"""
Command-line version of TripGenie. Handy for a quick test without opening the web app.

Example:
    python main.py "Kota, Rajasthan, India" "New Delhi, India" --days 3 --people 2
"""
import argparse
import sys
import uuid
from datetime import date, timedelta
from functools import partial

from config.settings import settings
from models import TripRequest
from services.agent_service import PlanError, TripGenieAgent
from services.export_service import plan_to_markdown
from utils.formatters import format_money
from utils.logger import setup_logging
from utils.validators import ValidationError, validate_trip_request


def main() -> int:
    parser = argparse.ArgumentParser(description="Make a trip plan from the command line.")
    parser.add_argument("from_city", help="where you start")
    parser.add_argument("to_city", help="where you want to go")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--people", type=int, default=2)
    parser.add_argument("--start-date", default=(date.today() + timedelta(days=14)).isoformat())
    args = parser.parse_args()

    # Friendly message instead of a crash when the key is missing
    if settings.api.missing_keys():
        print(f"Missing API key: {', '.join(settings.api.missing_keys())}. Add it to your .env file.")
        return 1

    setup_logging()
    request = TripRequest(
        from_city=args.from_city,
        to_city=args.to_city,
        start_date=args.start_date,
        days=args.days,
        people=args.people,
    )
    try:
        request = validate_trip_request(request)
        agent = TripGenieAgent()
        thread_id = uuid.uuid4().hex
        for step in agent.start_trip(request, thread_id):
            print(f"  done: {step}")
        plan = agent.get_plan(thread_id)
    except (ValidationError, PlanError) as error:
        print(f"Error: {error}")
        return 1

    print()
    print(plan_to_markdown(plan, partial(format_money, currency="INR", rate=1.0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
