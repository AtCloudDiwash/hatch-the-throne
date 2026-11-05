"""Date helpers shared across billing, jobs and reports."""
import calendar
import datetime as dt


def parse_date(value):
    if isinstance(value, dt.date):
        return value
    return dt.date.fromisoformat(value)


def add_days(day, days):
    return parse_date(day) + dt.timedelta(days=days)


def add_months(day, months):
    day = parse_date(day)
    index = day.month - 1 + months
    year = day.year + index // 12
    month = index % 12 + 1
    last = calendar.monthrange(year, month)[1]
    return dt.date(year, month, min(day.day, last))


def month_end(day):
    day = parse_date(day)
    return dt.date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])


def month_start(day):
    return parse_date(day).replace(day=1)


def days_overdue(due_date, as_of, grace=0):
    """Whole days past due after the grace period; zero if not overdue."""
    late = (parse_date(as_of) - parse_date(due_date)).days - grace
    return late if late > 0 else 0


def is_business_day(day):
    return parse_date(day).weekday() < 5


def next_business_day(day):
    day = parse_date(day)
    while not is_business_day(day):
        day += dt.timedelta(days=1)
    return day


def business_days_between(start, end):
    start, end = parse_date(start), parse_date(end)
    count = 0
    while start < end:
        if is_business_day(start):
            count += 1
        start += dt.timedelta(days=1)
    return count


def quarter_of(day):
    return (parse_date(day).month - 1) // 3 + 1
