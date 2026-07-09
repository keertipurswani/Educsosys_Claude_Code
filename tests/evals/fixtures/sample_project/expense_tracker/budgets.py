from .models import Category
from .store import ExpenseStore


class BudgetExceededError(Exception):
    """Raised by enforce_budget when spending in a category exceeds its limit."""


class BudgetChecker:
    """Tracks a per-category spending limit and checks it against an ExpenseStore."""

    def __init__(self, store: ExpenseStore, limits: dict[Category, float]):
        self.store = store
        self.limits = limits

    def remaining_budget(self, category: Category) -> float:
        """Return how much budget is left for a category (negative if over)."""
        limit = self.limits.get(category, float("inf"))
        spent = self.store.total_by_category(category)
        return limit - spent

    def is_over_budget(self, category: Category) -> bool:
        """True if spending in this category has exceeded its configured limit."""
        return self.remaining_budget(category) < 0

    def enforce_budget(self, category: Category) -> None:
        """Raise BudgetExceededError if the category is currently over budget."""
        if self.is_over_budget(category):
            raise BudgetExceededError(
                f"Category '{category.value}' is over budget by {-self.remaining_budget(category):.2f}"
            )
