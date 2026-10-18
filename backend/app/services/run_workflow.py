"""Shared application operations for run and approval lifecycle changes.

HTTP routes and MCP tools keep transport-specific validation and scheduling.
This module owns the persisted run creation, checkpoint state lookup, approval
updates, and finding review transitions common to both adapters.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.finding import Finding
from app.models.document import Document
from app.models.run import Run
from app.services.audit import create_audit_log
from app.workflow.graph import compile_workflow


def create_run(session: Session, file_paths: list[str], compliance_rules: str) -> dict:
    """Persist a new run and return the initial graph state."""
    if not compliance_rules or not compliance_rules.strip():
        raise ValueError("Compliance rules are required and cannot be blank.")
    run = Run(
        status="running",
        input_metadata={
            "file_paths": file_paths,
            "compliance_rules": compliance_rules.strip(),
        },
    )
    session.add(run)
    session.commit()
    return {"run_id": str(run.id), "current_stage": "ingest"}


def mark_run_running(session: Session, run: Run) -> None:
    """Persist the established running status for a resumed or updated run."""
    run.status = "running"
    session.commit()


def queue_document_paths(
    session: Session,
    run: Run,
    paths: list[str],
    *,
    deduplicate_paths: bool,
) -> None:
    """Append newly accepted source paths and persist the running status.

    The adapters retain their current duplicate policies and pass the matching
    policy here so input metadata and status updates happen in one place.
    """
    metadata = dict(run.input_metadata or {})
    current_paths = metadata.get("file_paths", [])
    if deduplicate_paths:
        for path in paths:
            if path not in current_paths:
                current_paths.append(path)
    else:
        current_paths = current_paths + paths
    metadata["file_paths"] = current_paths
    run.input_metadata = metadata
    run.status = "running"
    session.commit()


def get_checkpoint_state(checkpointer, run_id: str) -> dict:
    """Return a run's checkpoint state, or its established initial state."""
    graph = compile_workflow(checkpointer=checkpointer, interrupt_before=["approval"])
    thread_config = {"configurable": {"thread_id": run_id}}
    snapshot = graph.get_state(thread_config)
    if snapshot and snapshot.values:
        return dict(snapshot.values)
    return {"run_id": run_id, "current_stage": "ingest"}


def get_run_details(session: Session, checkpointer, run_id: uuid.UUID) -> dict:
    """Build the persisted run detail read model from checkpoint and records."""
    state = get_checkpoint_state(checkpointer, str(run_id))
    doc_ids = state.get("document_ids", [])

    if doc_ids:
        docs = session.query(Document).filter(
            Document.id.in_([uuid.UUID(doc_id) for doc_id in doc_ids])
        ).all()
    else:
        docs = []

    findings = session.query(Finding).filter(Finding.run_id == run_id).all()
    document_details = [
        {"id": doc.id, "name": doc.name, "byte_size": doc.byte_size}
        for doc in docs
    ]

    finding_details = []
    for finding in findings:
        claim_details = []
        for claim in finding.claims:
            evidence_details = []
            for evidence in claim.evidence:
                evidence_details.append({
                    "id": evidence.id,
                    "snippet": evidence.snippet,
                    "relevance": evidence.relevance,
                    "document_name": (
                        evidence.chunk.document.name
                        if evidence.chunk and evidence.chunk.document
                        else None
                    ),
                })
            claim_details.append({
                "id": claim.id,
                "statement": claim.statement,
                "confidence": claim.confidence,
                "evidence": evidence_details,
            })
        finding_details.append({
            "id": finding.id,
            "title": finding.title,
            "summary": finding.summary,
            "severity": finding.severity,
            "status": finding.status,
            "claims": claim_details,
        })

    return {
        "run_id": run_id,
        "documents": document_details,
        "findings": finding_details,
    }


def update_approval_checkpoint(checkpointer, run_id: str, reviewer: str):
    """Record approval at the verify seam so the graph can continue."""
    graph = compile_workflow(checkpointer=checkpointer, interrupt_before=["approval"])
    thread_config = {"configurable": {"thread_id": run_id}}
    graph.update_state(
        thread_config,
        {"approval_decision": "approved", "reviewer": reviewer},
        as_node="verify",
    )
    return graph


class FindingNotFound(ValueError):
    """A finding does not belong to the requested run."""


class FindingAlreadyReviewed(ValueError):
    """A finding is no longer pending review."""


@dataclass(frozen=True)
class FindingReviewResult:
    finding_id: str
    status: str
    pending_count: int


def review_finding(
    session: Session,
    run_id: uuid.UUID,
    finding_id: uuid.UUID,
    decision: str,
    *,
    comment: str | None = None,
    edited_text: str | None = None,
    audit: bool = False,
) -> FindingReviewResult:
    """Apply a finding decision and return the remaining pending count.

    The HTTP adapter requests an audit record and may submit edits. The MCP
    adapter keeps its existing approve/reject-only behavior and omits audit.
    """
    finding = (
        session.query(Finding)
        .filter(Finding.id == finding_id, Finding.run_id == run_id)
        .with_for_update()
        .first()
    )
    if not finding:
        raise FindingNotFound("Finding not found for this run.")

    if finding.status != "pending":
        raise FindingAlreadyReviewed(
            f"Finding has already been reviewed (current status: {finding.status})."
        )

    if decision == "approve":
        finding.status = "approved"
    elif decision == "reject":
        finding.status = "rejected"
    elif decision == "edit" and audit:
        finding.status = "approved"
    else:
        raise ValueError(f"Invalid decision: {decision}. Must be 'approve' or 'reject'.")

    if decision == "edit" and edited_text:
        if finding.payload is None:
            finding.payload = {}
        payload_copy = dict(finding.payload)
        payload_copy["original_summary"] = finding.summary
        finding.payload = payload_copy
        finding.summary = edited_text

    if audit:
        create_audit_log(
            session=session,
            run_id=run_id,
            action=f"finding_{decision}",
            details={
                "finding_id": str(finding_id),
                "comment": comment,
                "edited_text": edited_text if decision == "edit" else None,
                "reviewer": "human",
            },
        )

    session.commit()
    pending_count = (
        session.query(Finding)
        .filter(Finding.run_id == run_id, Finding.status == "pending")
        .count()
    )
    return FindingReviewResult(
        finding_id=str(finding.id),
        status=finding.status,
        pending_count=pending_count,
    )
