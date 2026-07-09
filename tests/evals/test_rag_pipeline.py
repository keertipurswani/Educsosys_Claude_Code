"""RAG-specific eval suite for the retriever behind search_codebase.

Unlike test_codebase_agent.py (which evaluates the full tool-using agent),
this suite isolates retrieval only — no generation step, no agent, no
LLM-written answer — and scores it with retrieval-quality metrics: Precision@k,
Recall@k, and Relevancy@k (see metrics.py for the exact deepeval metric
mapping). A failing metric here points unambiguously at retrieval, never at
agent reasoning.

Graded against fixtures/sample_project (indexed once by conftest.py's
session fixture into an isolated ChromaDB collection), not against
educosys_claude's own source — in real usage this tool is always pointed at
someone else's project (or an empty one), never at itself.

The dataset (dataset_rag.json) is hand-authored, not generated with
`deepeval generate` — every input/expected_output/context is grounded in
facts manually verified against fixtures/sample_project's real source
(source_file records where each answer comes from).
"""

import pytest
from deepeval import assert_test
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.test_case import LLMTestCase

from educosys_claude.context.retrievers.factory import get_retriever

from metrics import RAG_METRICS

RETRIEVAL_K = 5

dataset = EvaluationDataset()
dataset.add_goldens_from_json_file(file_path="tests/evals/dataset_rag.json")


@pytest.mark.parametrize("golden", dataset.goldens)
def test_rag_pipeline(golden: Golden):
    retrieve = get_retriever()
    chunks = retrieve(golden.input, k=RETRIEVAL_K)

    retrieval_context = [
        f"File: {c['source']} (lines {c['start_line']}-{c['end_line']})\n"
        f"{c['type']} {c['name']}:\n{c['content']}"
        for c in chunks
    ]

    test_case = LLMTestCase(
        input=golden.input,
        retrieval_context=retrieval_context,
        expected_output=golden.expected_output,
    )
    assert_test(test_case=test_case, metrics=RAG_METRICS)
