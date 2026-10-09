from utils.formatters import format_duration, format_money, slugify


def test_format_duration():
    assert format_duration(1) == "1 day"
    assert format_duration(3) == "3 days"
    assert format_duration(7) == "1 week"
    assert format_duration(10) == "1 week and 3 days"
    assert format_duration(30) == "1 month"  # this used to say "1 months"
    assert format_duration(45) == "1 month and 15 days"


def test_format_money():
    assert format_money(1500) == "₹1,500"
    assert format_money(1000, currency="USD", rate=0.012) == "$12.00"


def test_slugify():
    assert slugify("Trip to New Delhi!") == "trip-to-new-delhi"
