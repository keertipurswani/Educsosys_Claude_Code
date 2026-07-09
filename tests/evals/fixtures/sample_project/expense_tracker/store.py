from datetime import date

from .models import Category, Expense


class ExpenseNotFoundError(Exception):
    """Raised when an expense id doesn't exist in the store."""


class ExpenseStore:
    """In-memory store for expenses, keyed by auto-incrementing id."""

    def __init__(self):
        self._expenses: dict[int, Expense] = {}
        self._next_id = 1

    def add_expense(self, amount: float, category: Category, description: str, incurred_on: date) -> Expense:
        """Create and store a new Expense, assigning it the next available id."""
        expense = Expense(
            id=self._next_id, amount=amount, category=category,
            description=description, incurred_on=incurred_on,
        )
        self._expenses[expense.id] = expense
        self._next_id += 1
        return expense

    def remove_expense(self, expense_id: int) -> None:
        """Delete an expense by id, raising ExpenseNotFoundError if it doesn't exist."""
        if expense_id not in self._expenses:
            raise ExpenseNotFoundError(f"No expense with id {expense_id}")
        del self._expenses[expense_id]

    def get_expense(self, expense_id: int) -> Expense:
        """Look up a single expense by id, raising ExpenseNotFoundError if missing."""
        if expense_id not in self._expenses:
            raise ExpenseNotFoundError(f"No expense with id {expense_id}")
        return self._expenses[expense_id]

    def list_expenses(self) -> list[Expense]:
        """Return all stored expenses, ordered by id."""
        return sorted(self._expenses.values(), key=lambda e: e.id)

    def total_by_category(self, category: Category) -> float:
        """Sum the amount of every expense in the given category."""
        return sum(e.amount for e in self._expenses.values() if e.category == category)

    def total_all(self) -> float:
        """Sum the amount of every expense in the store."""
        return sum(e.amount for e in self._expenses.values())
