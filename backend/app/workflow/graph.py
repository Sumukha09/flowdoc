
from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

from app.workflow.constants import (
    EXPECTED_NODES, NODE_ANALYZE, NODE_APPROVAL, NODE_COMPLETE, NODE_EXTRACT,
    NODE_INGEST, NODE_VERIFY,
)
from app.workflow.ingest import ingest_node
from app.workflow.extract import extract_node
from app.workflow.analyze import analyze_node
from app.workflow.verify import verify_node
from app.workflow.approval import approval_node, requires_human_review
from app.workflow.completion import complete_node
from app.workflow.dependencies import WorkflowDependencies, default_workflow_dependencies
from app.workflow.llm import get_llm
from app.workflow.state import WorkflowState


def _build_graph(dependencies: WorkflowDependencies | None = None) -> StateGraph:
    """Construct the LangGraph ``StateGraph`` and return it uncompiled."""
    dependencies = dependencies or default_workflow_dependencies()
    graph = StateGraph(WorkflowState)

    graph.add_node(NODE_INGEST, partial(ingest_node, dependencies=dependencies))
    graph.add_node(NODE_EXTRACT, partial(extract_node, dependencies=dependencies))
    graph.add_node(NODE_ANALYZE, partial(analyze_node, dependencies=dependencies))
    graph.add_node(NODE_VERIFY, partial(verify_node, dependencies=dependencies))
    graph.add_node(NODE_APPROVAL, approval_node)
    graph.add_node(NODE_COMPLETE, partial(complete_node, dependencies=dependencies))

    graph.add_edge(START, NODE_INGEST)
    graph.add_edge(NODE_INGEST, NODE_EXTRACT)
    graph.add_edge(NODE_EXTRACT, NODE_ANALYZE)
    graph.add_edge(NODE_ANALYZE, NODE_VERIFY)
    
    graph.add_conditional_edges(
        NODE_VERIFY,
        requires_human_review,
        {
            NODE_APPROVAL: NODE_APPROVAL,
            NODE_COMPLETE: NODE_COMPLETE,
        }
    )
    
    graph.add_edge(NODE_APPROVAL, NODE_COMPLETE)
    graph.add_edge(NODE_COMPLETE, END)

    return graph

def compile_workflow(
    checkpointer=None,
    *,
    dependencies: WorkflowDependencies | None = None,
    **kwargs,
):
    """Compile the graph, optionally with a checkpointer and kwargs like interrupt_before."""
    return _build_graph(dependencies).compile(checkpointer=checkpointer, **kwargs)

#: Compiled workflow without a checkpointer.
workflow_graph = compile_workflow()

__all__ = [
    "EXPECTED_NODES", "NODE_INGEST", "NODE_EXTRACT", "NODE_ANALYZE",
    "NODE_VERIFY", "NODE_APPROVAL", "NODE_COMPLETE", "workflow_graph",
    "compile_workflow", "ingest_node", "extract_node", "analyze_node",
    "verify_node", "approval_node", "complete_node", "requires_human_review",
    "get_llm",
]
