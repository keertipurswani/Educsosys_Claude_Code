"""Agentic eval suite for the autonomous /plan pipeline.

Traces the planner -> executor chain: tasks/planner.create_plan produces a
DAG of tasks for a software goal, then tasks/executor.run_subtask_agent
autonomously implements the first task with a restricted, least-privilege
toolset per task type and is checked by an internal LLM-as-judge. DeepEval
scores the resulting nested trace for task completion, plan quality, and
whether execution adhered to the plan.

Covers both real usage modes of /plan:
  - empty project: most goldens plan+execute into a blank scratch directory
    (nothing to seed — this is the tool's most common starting point).
  - existing project: goldens whose golden.additional_metadata has
    "seed_existing_project": true instead get a copy of fixtures/sample_project
    seeded into the scratch directory first, so the executor has to read and
    extend real pre-existing code rather than write everything from scratch.
"""

import asyncio
import os
import shutil
import tempfile

import pytest
from deepeval import assert_test
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.tracing import observe, update_current_trace

from conftest import SAMPLE_PROJECT_DIR
from educosys_claude.tasks.executor import run_subtask_agent
from educosys_claude.tasks.planner import create_plan

from metrics import TASK_PLANNING_AGENT_METRICS


dataset = EvaluationDataset()
dataset.add_goldens_from_json_file(
    file_path="tests/evals/dataset_task_planning_agent.json"
)


@observe(type="agent", name="task_planning_pipeline")
async def run_traced_task_planning_pipeline(goal: str, seed_existing_project: bool = False) -> str:
    """Real app entry point: plan the goal, then execute its first task —
    the same plan -> execute sequence handle_plan_command runs per task,
    minus human approval and DB persistence (out of scope for evals).

    Execution is confined to a scratch temp directory so the generated (or
    modified) project files never land inside this repository. When
    seed_existing_project is True, that scratch directory starts as a copy
    of fixtures/sample_project instead of empty, so the goal is "add to/fix
    an existing codebase" rather than "build from scratch".
    """
    plan = create_plan(goal)
    first_task = plan.tasks[0].model_dump(mode="json")

    original_cwd = os.getcwd()
    with tempfile.TemporaryDirectory(prefix="educosys_eval_") as scratch_dir:
        if seed_existing_project:
            shutil.copytree(SAMPLE_PROJECT_DIR, scratch_dir, dirs_exist_ok=True)
        os.chdir(scratch_dir)
        try:
            result = await run_subtask_agent(first_task, dep_outputs=[])
        except Exception as e:
            result = f"Task execution failed: {e}"
        finally:
            os.chdir(original_cwd)

    output = (
        f"Plan: {plan.project_name} ({len(plan.tasks)} tasks, "
        f"tech_stack={', '.join(plan.tech_stack)})\n\n"
        f"First task [{first_task['id']}] \"{first_task['title']}\" result:\n{result}"
    )
    update_current_trace(input=goal, output=output)
    return output


@pytest.mark.parametrize("golden", dataset.goldens)
def test_task_planning_agent(golden: Golden):
    seed_existing_project = bool(
        (golden.additional_metadata or {}).get("seed_existing_project")
    )
    asyncio.run(run_traced_task_planning_pipeline(golden.input, seed_existing_project))
    assert_test(golden=golden, metrics=TASK_PLANNING_AGENT_METRICS)
