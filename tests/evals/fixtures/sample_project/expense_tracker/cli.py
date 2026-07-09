import argparse
from datetime import date

from .models import Category
from .reports import category_breakdown
from .store import ExpenseStore


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse CLI parser with 'add' and 'report' subcommands."""
    parser = argparse.ArgumentParser(prog="expense-tracker")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add a new expense")
    add_parser.add_argument("amount", type=float)
    add_parser.add_argument("category", choices=[c.value for c in Category])
    add_parser.add_argument("description")

    subparsers.add_parser("report", help="Show a category breakdown report")
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: parses argv and dispatches to the add/report commands."""
    parser = build_parser()
    args = parser.parse_args(argv)
    store = ExpenseStore()

    if args.command == "add":
        store.add_expense(args.amount, Category(args.category), args.description, date.today())
        print(f"Added {args.amount} to {args.category}")
    elif args.command == "report":
        for category, total in category_breakdown(store).items():
            print(f"{category.value}: {total:.2f}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
