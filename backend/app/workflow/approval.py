
from app.workflow.constants import (
    NODE_ANALYZE, NODE_APPROVAL, NODE_COMPLETE, NODE_EXTRACT, NODE_INGEST, NODE_VERIFY,
)
from app.workflow.state import WorkflowState


def approval_node(state: WorkflowState) -> dict:
    """Structural placeholder for the approval gate.

    Real approval logic (reviewer assignment, decision routing) is added in a
    later step. This placeholder simply advances the stage and records the
    transition. No human-in-the-loop behaviour is implemented here.
    """
    return {
        "current_stage": NODE_COMPLETE,
        "completed_stages": [
            NODE_INGEST,
            NODE_EXTRACT,
            NODE_ANALYZE,
            NODE_VERIFY,
            NODE_APPROVAL,
        ],
    }


def requires_human_review(state: WorkflowState) -> str:
    """Determine whether to route to human review or skip straight to completion."""
    if state.get("approval_required", False):
        return NODE_APPROVAL
    return NODE_COMPLETE
