"""Agentic eval suite for the codebase Q&A agent (the `/ask` tool-using agent).

Traces educosys_claude.agent.orchestrator.handle_query end-to-end: the agent
decides whether/how to call search_codebase, run_command, or run_in_directory
to answer a question about a target codebase. DeepEval scores the resulting
trace for task completion, step efficiency, and answer correctness.

Graded against fixtures/sample_project (see conftest.py), not against
educosys_claude's own source — in real usage this tool is always pointed at
someone else's project (or an empty one), never at itself.
"""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest
from deepeval import assert_test
from deepeval.dataset import EvaluationDataset, Golden
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from conftest import SAMPLE_PROJECT_DIR
from educosys_claude.agent.factory import build_agent
from educosys_claude.agent.orchestrator import handle_query

from metrics import CODEBASE_AGENT_METRICS


dataset = EvaluationDataset()
dataset.add_goldens_from_json_file(
    file_path="tests/evals/dataset_codebase_agent.json"
)


async def run_traced_codebase_agent(question: str) -> str:
    """Real app entry point for one /ask turn, isolated per golden.

    Runs with cwd inside a scratch copy of sample_project so any
    run_command/run_in_directory shell calls the agent makes stay confined to
    the target project (and never touch this repo or the read-only fixture).
    include_mcp_tools=False keeps evals hermetic — MCP servers spawn external
    stdio processes that eval runs should not depend on.
    """
    original_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="educosys_eval_codebase_agent_") as scratch_dir:
        shutil.copytree(SAMPLE_PROJECT_DIR, scratch_dir, dirs_exist_ok=True)
        try:
            os.chdir(scratch_dir)
            async with AsyncSqliteSaver.from_conn_string(":memory:") as checkpointer:
                agent = await build_agent(checkpointer, include_mcp_tools=False)
                return await handle_query(agent, question, thread_id=f"eval-{uuid4()}")
        finally:
            os.chdir(original_cwd)


@pytest.mark.parametrize("golden", dataset.goldens)
def test_codebase_agent(golden: Golden):
    asyncio.run(run_traced_codebase_agent(golden.input))
    assert_test(golden=golden, metrics=CODEBASE_AGENT_METRICS)
