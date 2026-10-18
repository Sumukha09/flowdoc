"""Canonical workflow state contract.

This module defines the single ``WorkflowState`` TypedDict that every step of
the FlowDocs pipeline reads from and writes to. The state is intentionally a
plain JSON-serialisable bag of primitives and containers — no SQLAlchemy
sessions, no LLM clients, no file bytes, no Python objects. Checkpoint
storage, in-memory state, and inter-node communication all serialise through
this shape.

Design notes:

* The TypedDict is declared with ``total=False`` so every field is optional
  from a typing perspective. This matches the way a workflow is built up
  incrementally: nodes add keys as they run, and a partial state at the
  start of a step is valid. The contract itself is the *set* of allowed
  keys plus their value types.
* All list fields hold string identifiers (UUIDs rendered as strings). No
  SQLAlchemy ORM objects are stored.
* ``verification_result_counts`` is a ``dict[str, int]`` keyed by result
  category (e.g. ``{"verified": 12, "rejected": 1, "insufficient": 2}``).
* Stage, status, and decision identifiers use ``Literal`` aliases directly in
  the state contract for type checking.
"""


from typing import Literal, TypedDict

# ---------------------------------------------------------------------------
# Vocabulary literals. These aliases are also used by the state fields below.
# They are kept here as the canonical source for workflow stage and status
# values. Legacy stage values remain included for existing checkpoints.
# ---------------------------------------------------------------------------

#: Values emitted by the graph, terminal markers, and legacy checkpoint values.
Stage = Literal[
    "ingest",
    "extract",
    "analyze",
    "verify",
    "approval",
    "complete",
    "failed",
    "completed",
    "approve",
    "finalize",
]

#: Coarse workflow and persisted run status values returned to callers.
Status = Literal[
    "pending",
    "running",
    "awaiting_approval",
    "approved",
    "rejected",
    "failed",
    "completed",
]

#: Approval decisions stored in workflow state.
ApprovalDecision = Literal["approved", "rejected"]


# ---------------------------------------------------------------------------
# The state contract. Every key listed here is part of the public surface.
# ---------------------------------------------------------------------------


class WorkflowState(TypedDict, total=False):
    """The single, canonical workflow state for a FlowDocs run.

    Every field is JSON-serialisable. The contract is intentionally a flat
    mapping of primitives and primitive containers; nesting is kept shallow
    so the state can round-trip through JSON without bespoke codecs.
    """

    # --- Run identity and lifecycle ------------------------------------------
    run_id: str
    current_stage: Stage
    status: Status
    document_ids: list[str]
    completed_stages: list[Stage]
    errors: list[str]

    # --- Approval gate --------------------------------------------------------
    approval_required: bool
    approval_decision: ApprovalDecision | None
    rejection_reason: str | None
    reviewer: str | None

    # --- Ingest outputs -------------------------------------------------------
    chunk_ids: list[str]
    chunk_count: int
    ingested_document_ids: list[str]

    # --- Extract outputs ------------------------------------------------------
    extracted_claim_ids: list[str]
    extracted_entity_count: int
    processed_chunk_ids: list[str]

    # --- Analyze outputs ------------------------------------------------------
    analyzed_finding_ids: list[str]
    analyzed_claim_ids: list[str]
    compliance_checks_total: int
    compliance_checks_passed: int

    # --- Verify outputs -------------------------------------------------------
    verified_claim_ids: list[str]
    verification_result_counts: dict[str, int]
    failed_insufficient_evidence_count: int

    # --- Token Tracking -------------------------------------------------------
    total_tokens_used: int


#: The set of allowed keys. Exposed so tests and external tooling can assert
#: that a serialised state contains no unknown fields. This is the single
#: source of truth for "what is in the contract".
WORKFLOW_STATE_FIELDS: frozenset[str] = frozenset(WorkflowState.__annotations__.keys())
