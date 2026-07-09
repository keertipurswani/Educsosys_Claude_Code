"""Shared DeepEval metric lists for the educosys_claude eval suites.

Agentic-flow metrics (task completion, step efficiency, plan quality/
adherence) plus one GEval custom-criteria metric per agent surface, and a
dedicated set of RAG retrieval metrics for the retriever used by
search_codebase. Keep eval files focused on running the app; construct
metrics here.
"""

from deepeval.metrics import (
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
    GEval,
    PlanAdherenceMetric,
    PlanQualityMetric,
    StepEfficiencyMetric,
    TaskCompletionMetric,
)
from deepeval.test_case import SingleTurnParams

# Evaluation (judge) model for every metric below. Override by setting
# DEEPEVAL_EVAL_MODEL, e.g. to use gpt-4.1 or a reasoning model instead.
import os

EVAL_MODEL = os.getenv("DEEPEVAL_EVAL_MODEL", "gpt-4o")

# ---------------------------------------------------------------------------
# codebase_agent — the tool-using /ask agent (agent/orchestrator.handle_query)
# ---------------------------------------------------------------------------
CODEBASE_AGENT_METRICS = [
    TaskCompletionMetric(threshold=0.5, model=EVAL_MODEL),
    StepEfficiencyMetric(threshold=0.5, model=EVAL_MODEL),
    GEval(
        name="Codebase Answer Correctness",
        criteria=(
            "Determine whether 'actual output' correctly and specifically answers "
            "the codebase question in 'input'. A correct answer references real "
            "file names, function/class names, or code behavior instead of "
            "generic or hedged statements, unless the agent explicitly and "
            "correctly states the answer could not be found in the codebase."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        threshold=0.5,
        model=EVAL_MODEL,
    ),
]

# ---------------------------------------------------------------------------
# task_planning_agent — the autonomous /plan pipeline: planner -> executor
# (tasks/planner.create_plan -> tasks/executor.run_subtask_agent, judged by
# an internal LLM-as-judge before the trace even reaches these metrics)
# ---------------------------------------------------------------------------
TASK_PLANNING_AGENT_METRICS = [
    TaskCompletionMetric(threshold=0.5, model=EVAL_MODEL),
    PlanQualityMetric(threshold=0.5, model=EVAL_MODEL),
    PlanAdherenceMetric(threshold=0.5, model=EVAL_MODEL),
    GEval(
        name="Task Output Quality",
        criteria=(
            "Determine whether 'actual output' describes concrete, non-trivial "
            "work completed toward the goal in 'input' (files written, code or "
            "config produced, or a clear implementation summary), rather than a "
            "vague plan restatement or a refusal."
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        threshold=0.5,
        model=EVAL_MODEL,
    ),
]

# ---------------------------------------------------------------------------
# rag_pipeline — the retriever behind search_codebase
# (context/retrievers/factory.get_retriever), evaluated purely on retrieval
# quality: no generation step, no actual_output. All three metrics only need
# input + retrieval_context (+ expected_output where noted).
#
#   ContextualPrecisionMetric  ~ Precision@k  — are the relevant retrieved
#                                chunks ranked near the top of the k results?
#                                (needs expected_output)
#   ContextualRecallMetric     ~ Recall@k     — does retrieval_context contain
#                                enough to produce expected_output?
#                                (needs expected_output)
#   ContextualRelevancyMetric  ~ Relevancy@k  — what fraction of the k
#                                retrieved chunks are actually relevant to input?
# ---------------------------------------------------------------------------
RAG_METRICS = [
    ContextualPrecisionMetric(threshold=0.5, model=EVAL_MODEL),
    ContextualRecallMetric(threshold=0.5, model=EVAL_MODEL),
    ContextualRelevancyMetric(threshold=0.5, model=EVAL_MODEL),
]
