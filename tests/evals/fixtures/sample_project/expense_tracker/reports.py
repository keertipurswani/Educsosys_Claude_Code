from collections import defaultdict

from .store import ExpenseStore


def category_breakdown(store: ExpenseStore) -> dict:
    """Return {category: total_amount} for every category with at least one expense."""
    totals = defaultdict(float)
    for expense in store.list_expenses():
        totals[expense.category] += expense.amount
    return dict(totals)


def monthly_summary(store: ExpenseStore, year: int, month: int) -> float:
    """Sum the amount of every expense incurred in the given year/month."""
    return sum(
        e.amount for e in store.list_expenses()
        if e.incurred_on.year == year and e.incurred_on.month == month
    )
