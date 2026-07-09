"""Shared eval fixtures.

Every RAG/codebase-agent eval in this directory is graded against
fixtures/sample_project — a small standalone project unrelated to
educosys_claude's own source. That mirrors real usage: nobody points this
coding agent at itself, they point it at another project (or an empty one).

This fixture indexes sample_project into a throwaway, session-scoped ChromaDB
collection so evals never read from or write into the real app's production
index of this repo.
"""

import tempfile
from pathlib import Path

import pytest

from educosys_claude.config import config
from educosys_claude.context.indexers.factory import get_indexer

SAMPLE_PROJECT_DIR = Path(__file__).parent / "fixtures" / "sample_project"


@pytest.fixture(scope="session", autouse=True)
def _index_sample_project():
    original_persist_dir = config["chromadb"]["persist_dir"]
    original_collection = config["chromadb"]["collection_name"]

    eval_persist_dir = tempfile.mkdtemp(prefix="educosys_eval_chromadb_")
    config["chromadb"]["persist_dir"] = eval_persist_dir
    config["chromadb"]["collection_name"] = "educosys_claude_eval_sample_project"

    get_indexer()(str(SAMPLE_PROJECT_DIR))

    yield

    config["chromadb"]["persist_dir"] = original_persist_dir
    config["chromadb"]["collection_name"] = original_collection
