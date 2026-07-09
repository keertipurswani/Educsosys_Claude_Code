from dataclasses import dataclass
from datetime import date
from enum import Enum


class Category(str, Enum):
    FOOD = "food"
    TRANSPORT = "transport"
    HOUSING = "housing"
    ENTERTAINMENT = "entertainment"
    OTHER = "other"


@dataclass
class Expense:
    """A single recorded expense."""
    id: int
    amount: float
    category: Category
    description: str
    incurred_on: date

    def __post_init__(self):
        if self.amount <= 0:
            raise ValueError(f"Expense amount must be positive, got {self.amount}")
