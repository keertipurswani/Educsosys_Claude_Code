# expense_tracker (eval fixture)

A small, self-contained Python project used only as a target codebase for the
educosys_claude eval suite. It is deliberately unrelated to educosys_claude's
own implementation — the RAG and codebase-agent evals index and query *this*
project, not educosys_claude's own source, since that's how the tool is
actually used: pointed at someone else's (or an empty) project.

Modules: `models.py` (Expense, Category), `store.py` (ExpenseStore,
ExpenseNotFoundError), `budgets.py` (BudgetChecker, BudgetExceededError),
`reports.py` (category_breakdown, monthly_summary), `cli.py` (argparse CLI).
