"""Small helpers that turn data into nice text."""
import re

CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}


def _plural(count: int, word: str) -> str:
    """1 -> '1 day', 3 -> '3 days'"""
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def format_duration(days: int) -> str:
    """Turn a number of days into text: 3 -> '3 days', 10 -> '1 week and 3 days', 30 -> '1 month'."""
    if days < 7:
        return _plural(days, "day")
    if days < 30:
        weeks, extra = divmod(days, 7)
        text = _plural(weeks, "week")
        return text if extra == 0 else f"{text} and {_plural(extra, 'day')}"
    months, extra = divmod(days, 30)
    text = _plural(months, "month")
    return text if extra == 0 else f"{text} and {_plural(extra, 'day')}"


def format_money(amount_inr: float, currency: str = "INR", rate: float = 1.0) -> str:
    """Show an amount (stored in INR) in the chosen currency.

    rate = how much 1 INR is worth in that currency (1.0 for INR itself).
    """
    symbol = CURRENCY_SYMBOLS.get(currency, currency + " ")
    value = amount_inr * rate
    if currency == "INR":
        return f"{symbol}{value:,.0f}"
    return f"{symbol}{value:,.2f}"


def slugify(text: str) -> str:
    """Make text safe to use in a file name: 'Trip to New Delhi!' -> 'trip-to-new-delhi'."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
