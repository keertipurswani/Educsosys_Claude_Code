# Educosys Claude

Educosys Claude is an autonomous coding agent CLI (`educosys_claude`) built on
LangChain / LangGraph. Like Claude Code, it is a tool you run *inside another
project* (or an empty directory) to get help with that project's code — it is
never meant to be pointed at its own source. It has two agentic surfaces:

- **Codebase agent** (`/ask`) — a tool-using ReAct-style agent
  ([agent/orchestrator.py](educosys_claude/agent/orchestrator.py),
  [agent/factory.py](educosys_claude/agent/factory.py)) that answers questions
  about whatever repository it's launched in by calling `search_codebase`
  (RAG over a ChromaDB index of that repo), `run_command` /
  `run_in_directory`, MCP tools, and loaded skills.
- **Autonomous task planner** (`/plan`) — given a goal, an LLM planner
  ([tasks/planner.py](educosys_claude/tasks/planner.py)) produces a
  dependency-ordered DAG of tasks, and a task orchestrator
  ([tasks/orchestrator.py](educosys_claude/tasks/orchestrator.py)) dispatches
  each task to a fresh subtask agent
  ([tasks/executor.py](educosys_claude/tasks/executor.py)) with a
  least-privilege toolset (filesystem/terminal tools scoped to the task type)
  to add code, add features, or fix bugs in that repo. Every subtask's output
  is checked by an internal LLM-as-judge before the task is marked complete.

This repo also contains a **DeepEval eval suite** (`tests/evals/`) that tests
the tool's functionality — not its own source code.

## Why the evals target a separate fixture project

An earlier version of this suite asked the agent questions about
`educosys_claude`'s own implementation (e.g. "how does `index_codebase` skip
unchanged files?"). That's backwards: nobody runs this tool on itself in
practice — they run it against *their* project, which the tool has never
seen before, or against an empty directory it needs to build into. Grading
answers about the tool's own source doesn't measure whether the tool does its
actual job.

So every eval here targets
[tests/evals/fixtures/sample_project](tests/evals/fixtures/sample_project) —
a small, hand-written, self-contained Python project (`expense_tracker`: an
`ExpenseStore`, `BudgetChecker`, and a CLI) that is otherwise unrelated to
educosys_claude. The RAG and codebase-agent suites index and query *that*
project; the task-planning suite either builds into an empty scratch
directory or extends a seeded copy of that project — covering both of this
tool's real usage modes: **different project** and **empty project**.

## Eval Suite Overview

```text
tests/evals/
  conftest.py                       # indexes fixtures/sample_project into an isolated eval-only ChromaDB collection
  fixtures/sample_project/          # hand-written target project the evals operate on
  test_codebase_agent.py            # agentic: evals the /ask tool-using agent, against sample_project
  test_task_planning_agent.py       # agentic: evals the /plan planner -> executor pipeline
  test_rag_pipeline.py              # RAG: evals retrieval quality only, against sample_project
  metrics.py                        # shared metric lists (agentic + RAG)
  dataset_codebase_agent.json       # 14 hand-authored goldens about sample_project
  dataset_task_planning_agent.json  # 16 goldens: 10 empty-project builds + 6 existing-project add-feature/fix-bug
  dataset_rag.json                  # 15 hand-authored goldens about sample_project
```

The two agentic suites use DeepEval's **traced single-turn** eval shape: each
golden's `input` is sent through the real app, DeepEval captures the
resulting execution trace (via `@observe`, added to the app's tool functions
and agent entry points), and `assert_test(golden=golden, metrics=[...])`
scores that trace. The RAG suite uses the **no-tracing** shape instead: it
builds an `LLMTestCase` directly from the real retriever's raw output (no
generation step, no `actual_output`) plus the golden's hand-written
`expected_output`, since `ContextualPrecisionMetric` and
`ContextualRecallMetric` specifically need that reference field.

| Suite | Real entry point | Runs against | Metrics | What it catches |
| --- | --- | --- | --- | --- |
| `test_codebase_agent.py` | `handle_query()` → LangChain agent with `search_codebase`/`run_command`/`run_in_directory` tools | a scratch copy of `sample_project` | `TaskCompletionMetric`, `StepEfficiencyMetric`, `GEval("Codebase Answer Correctness")` | Agent gives a wrong/generic/hallucinated answer about the target repo, or takes redundant tool calls |
| `test_task_planning_agent.py` | `create_plan()` then `run_subtask_agent()` on the plan's first task, inside one nested trace | an empty scratch dir (10 goldens) or a seeded copy of `sample_project` (6 goldens) | `TaskCompletionMetric`, `PlanQualityMetric`, `PlanAdherenceMetric`, `GEval("Task Output Quality")` | Plan is incoherent/incomplete, or execution doesn't actually implement/extend/fix what was asked |
| `test_rag_pipeline.py` | `retrieve()` (via `get_retriever()`) — the same call `search_codebase` uses, called directly, no agent/tool orchestration and no generation | `sample_project` (indexed once by `conftest.py`) | `ContextualPrecisionMetric` (Precision@k), `ContextualRecallMetric` (Recall@k), `ContextualRelevancyMetric` (Relevancy@k) | Retriever ranks irrelevant chunks highly, or retrieves too little of what's needed to answer the question |

`test_rag_pipeline.py` deliberately tests retrieval only, not generation —
see "Why RAG evals only cover retrieval" below for why `FaithfulnessMetric`
and `AnswerRelevancyMetric` (which need a generated `actual_output`) were
dropped rather than adding a separate answer-generation function.

`@observe` tracing was added (non-invasively — it's a transparent decorator)
to:
[agent/tools.py](educosys_claude/agent/tools.py),
[tools/terminal_tools.py](educosys_claude/tools/terminal_tools.py),
[tools/filesystem_tools.py](educosys_claude/tools/filesystem_tools.py),
[agent/orchestrator.py](educosys_claude/agent/orchestrator.py) (`handle_query`),
[tasks/planner.py](educosys_claude/tasks/planner.py) (`create_plan`), and
[tasks/executor.py](educosys_claude/tasks/executor.py) (`run_subtask_agent`).

### Isolation from the real app

- **ChromaDB**: [conftest.py](tests/evals/conftest.py) monkeypatches
  `config["chromadb"]["persist_dir"]`/`collection_name` to a throwaway temp
  directory + a dedicated `educosys_claude_eval_sample_project` collection
  for the whole pytest session, then indexes `fixtures/sample_project` into
  it. Evals never read from or write into the real app's production index of
  this repo (or any other real project you've indexed with this tool).
- **Filesystem**: `test_codebase_agent.py` and `test_task_planning_agent.py`
  both `chdir` into a `tempfile.TemporaryDirectory()` (optionally seeded with
  a copy of `sample_project`) before invoking the agent, so any file writes
  or shell commands the agent runs land in a scratch directory, never in
  this repo or in the read-only fixture.
- **MCP**: both agentic suites build the agent with
  `include_mcp_tools=False` (a small flag added to `build_agent`) so evals
  don't depend on external MCP server processes.

## Prerequisites

- Python 3.12 and [Poetry](https://python-poetry.org/) (already used by this
  project).
- An `OPENAI_API_KEY` in `.env` — used both by the app (LLM + embeddings) and
  by DeepEval's evaluation/judge model (defaults to `gpt-4o`, see
  [tests/evals/metrics.py](tests/evals/metrics.py)).
- `deepeval` and `pytest` are declared as Poetry dev dependencies.

## Step-by-Step: Running the Eval Suite

### 1. Install dependencies

```bash
poetry install
```

This installs `deepeval` and `pytest` (added under `[dependency-groups] dev`
in [pyproject.toml](pyproject.toml)) alongside the app's existing
dependencies.

### 2. Set your OpenAI API key

Make sure `.env` at the repo root has a valid key:

```bash
OPENAI_API_KEY=sk-...
```

`.env` is already git-ignored and loaded automatically by both the app and
the eval suite's `python-dotenv` usage / your shell environment.

### 3. (Optional) Change the eval/judge model

Metrics default to `gpt-4o`. Override without editing code:

```bash
export DEEPEVAL_EVAL_MODEL=gpt-4.1
```

### 4. Run the codebase agent eval

```bash
poetry run deepeval test run tests/evals/test_codebase_agent.py \
  --identifier "codebase-agent-round-1"
```

The first test in any session also builds the eval-only ChromaDB index over
`fixtures/sample_project` (via `conftest.py`'s session fixture) — this is
fast since the fixture is tiny (7 files).

### 5. Run the task-planning agent eval

```bash
poetry run deepeval test run tests/evals/test_task_planning_agent.py \
  --identifier "task-planning-agent-round-1"
```

This suite is slower and more expensive per golden — each test plans a full
project (5-20 tasks) and then actually executes the first task with a real
subtask agent, so expect ~1-3 minutes and a few cents per golden. 10 goldens
build from an empty directory; 6 goldens (flagged with
`"additional_metadata": {"seed_existing_project": true}` in the dataset)
extend a seeded copy of `sample_project` instead — covering both "empty
project" and "different, existing project" usage.

### 6. Run the RAG eval

```bash
poetry run deepeval test run tests/evals/test_rag_pipeline.py \
  --identifier "rag-pipeline-round-1"
```

This is the fastest and cheapest suite — one `retrieve()` call per golden,
no LLM generation at all — and the one to run first when iterating on
chunking, `k`, or the embedding model, since its metrics isolate retrieval
quality from every other concern (generation, tool choice, agent reasoning).

### 7. Useful flags for larger runs

```bash
poetry run deepeval test run tests/evals/test_codebase_agent.py \
  --identifier "codebase-agent-round-2" \
  --num-processes 5 \
  --ignore-errors \
  --skip-on-missing-params
```

- `--num-processes` (`-n`) — parallelize across goldens with pytest-xdist.
  Start smaller (e.g. `2`) for `test_task_planning_agent.py` since each test
  itself spawns 2+ nested LLM agents.
- `--ignore-errors` (`-i`) — keep going past individual eval errors so one bad
  golden doesn't kill the whole run.
- `--skip-on-missing-params` (`-s`) — skip goldens missing fields a metric
  needs instead of failing the run.
- `--identifier` — label the run (useful when comparing rounds while
  iterating on prompts/tools).

Do **not** use plain `pytest` — always use `deepeval test run` so DeepEval can
collect and score the traces.

### 8. Read the results

Each metric prints a score, pass/fail, and a one-paragraph reason (see the
table above for what each metric checks). Real findings surfaced while
building this suite against `sample_project`:

- `test_codebase_agent.py`: `TaskCompletionMetric` and the correctness
  `GEval` passed, but `StepEfficiencyMetric` flagged the agent for making
  redundant `search_codebase` calls and a failed shell command it didn't
  need.
- `test_rag_pipeline.py`: `ContextualRecall` scored 1.0 (the relevant chunk
  was always somewhere in the top `k`), but `ContextualPrecision` and
  `ContextualRelevancy` scored low on some goldens because the retriever
  pulled in off-topic chunks (e.g. `BudgetExceededError` details) alongside
  the one genuinely relevant chunk at `k=5` — a real ranking/precision issue,
  not a recall issue.
- `test_task_planning_agent.py` (existing-project golden): the planner's
  first task was "document the deletion contract" rather than implement it,
  so `TaskCompletionMetric` and `PlanAdherenceMetric` correctly scored low —
  a reminder that this suite only executes the plan's *first* task per
  golden, so plans that front-load a design/documentation step will show
  weaker first-task completion even when the overall plan is reasonable.

### 9. Iterate

1. Run the suite, read failing metrics and reasons.
2. Make the smallest targeted app change (e.g. tighten the system prompt in
   [agent/factory.py](educosys_claude/agent/factory.py) to avoid redundant
   tool calls, or adjust
   [tasks/executor.py](educosys_claude/tasks/executor.py)'s per-task-type
   toolset).
3. Re-run with a new `--identifier` and compare.
4. Repeat for as many rounds as useful — 5 rounds is a reasonable default.

## Why RAG evals only cover retrieval

`test_rag_pipeline.py` calls `get_retriever()` directly and never generates
an answer. That's a deliberate scope decision, not an oversight:

- `retrieve()` only returns chunks — there is no "generate an answer from
  retrieved context" function anywhere in the app. That logic only exists
  embedded inside the full tool-using agent's reasoning loop
  (`agent/orchestrator.handle_query`), mixed with tool-choice decisions.
- `ContextualPrecisionMetric`, `ContextualRecallMetric`, and
  `ContextualRelevancyMetric` (Precision@k, Recall@k, Relevancy@k) only need
  `input` + `retrieval_context` (+ `expected_output` for the first two) —
  none of them need a generated answer at all.
- `FaithfulnessMetric` and `AnswerRelevancyMetric` *do* need a generated
  `actual_output`, so getting them back would require either (a) a new,
  separate answer-generation function, isolated from the agent so a low
  score points at grounding and not at agent tool-choice noise, or
  (b) reusing the full agent from `test_codebase_agent.py`, which reintroduces
  exactly the tool-choice noise the RAG suite exists to avoid, and can't even
  guarantee `search_codebase` gets called for every golden.
- We chose neither: this suite stays retrieval-only, on purpose, so a
  failing metric always points unambiguously at the retriever (chunking,
  `k`, embedding model, ranking) — never at generation or agent reasoning.

If faithfulness/answer-relevancy coverage is wanted later, add a small,
separate generation function and a 4th suite for it — don't fold it back
into this one.

## Growing the Datasets

Every golden in this suite is hand-authored against `fixtures/sample_project`
— none were produced with `deepeval generate`. `sample_project` is small
enough that its behavior can be fully verified by reading it, which is a
stronger ground truth than an LLM-generated `expected_output` grading another
LLM, and (per deepeval 4.0.7's `Synthesizer.generate_goldens_from_scratch()`)
`--method scratch` never populates `expected_output`/`context`/`source_file`
at all, which `ContextualPrecisionMetric`/`ContextualRecallMetric` require.

To add more goldens:

- **RAG / codebase-agent**: pick a real function/behavior in
  `fixtures/sample_project`, write the question, write the correct answer
  yourself, and (for `dataset_rag.json`) copy the relevant snippet into
  `context`. Keep `source_file` accurate.
- **Task planning**: write a new goal. For an "existing project" golden, add
  `"additional_metadata": {"seed_existing_project": true}` so
  `test_task_planning_agent.py` seeds a copy of `sample_project` into the
  scratch directory before planning/executing.
- To extend `fixtures/sample_project` itself (e.g. to test bug-fixing against
  a real known bug), add the file/function there first, then write goldens
  against it — keep the fixture project realistic but small.

## What This Suite Covers (and Doesn't)

This eval suite covers exactly two kinds of behavior on purpose:

- **Agentic** behavior (`test_codebase_agent.py`, `test_task_planning_agent.py`)
  — tool use, task completion, planning, step efficiency — tested against a
  target project the tool has never seen, the way it's actually used.
- **RAG retrieval** (`test_rag_pipeline.py`) — precision@k, recall@k,
  relevancy@k — also against that target project.

It intentionally does not include generic unit tests, chatbot/conversational
metrics (`ConversationCompletenessMetric`, `RoleAdherenceMetric`, etc., since
neither agent surface here is a multi-turn chatbot end-to-end), or any eval
that grades the agent on questions about educosys_claude's own source.

## Confident AI (Not Enabled)

Results run locally only; nothing is sent to Confident AI. To opt in later:

```bash
poetry run deepeval login
poetry run deepeval test run tests/evals/test_codebase_agent.py
poetry run deepeval view   # opens the latest hosted report
```

## CI/CD

[.github/workflows/deepeval-tests.yml](.github/workflows/deepeval-tests.yml)
runs all three eval suites as a GitHub Actions check, following DeepEval's
[CI/CD guide](https://deepeval.com/docs/evaluation-unit-testing-in-ci-cd):
install Poetry, install dependencies, then `poetry run deepeval test run`
per suite with `OPENAI_API_KEY` from GitHub secrets. It uses `deepeval test
run`, never plain `pytest`, so traces are collected and metrics scored the
same way as a local run.

**Triggers**: push to `main`, pull requests targeting `main`, and manual runs
(`workflow_dispatch`).

**Setup**: add `OPENAI_API_KEY` under repo *Settings → Secrets and
variables → Actions → New repository secret*. No other secrets are needed —
this suite never touches Confident AI, Redis, Qdrant, or MCP servers in CI.

**Job behavior**: the three suites run as separate steps (RAG → codebase
agent → task planning, cheapest/fastest first) each marked `if: always()`,
so all three run and report even if an earlier one fails — but the job still
fails overall if any suite has a failing eval, so it works as a real merge
gate, not just an informational run.

**Cost/time**: this runs the *entire* dataset (14 + 15 + 16 goldens = 45
LLM-graded test cases) on every push and PR. The task-planning suite alone
plans and executes real subtasks per golden, so a full CI run can take
20-40+ minutes and a few dollars in OpenAI usage. If that's too much for
your workflow, trim it by:

- Removing `test_task_planning_agent.py` from CI (keep it as a local/manual
  check only) and running the other two suites on every push, or
- Changing the `push`/`pull_request` triggers to `workflow_dispatch`-only
  (or a `schedule` cron) so it runs on demand or nightly instead of on every
  commit, or
- Splitting the dataset JSON files and pointing CI at a small smoke-test
  subset while keeping the full datasets for local/manual runs.

Caching (`actions/cache` on `~/.cache/pypoetry/virtualenvs`, keyed on
`poetry.lock`) is included to keep dependency installs fast across runs.
