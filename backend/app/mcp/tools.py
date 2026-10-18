import uuid
import os
import threading
from typing import List

from app.db.session import get_session_factory
from app.api.deps import get_checkpointer
from app.models.run import Run
from app.models.finding import Finding
from app.models.document import Document
from app.services.run_workflow import (
    create_run as create_run_record,
    get_checkpoint_state,
    mark_run_running,
    queue_document_paths,
    review_finding as apply_finding_review,
    update_approval_checkpoint,
)
from app.services.workflow_runner import run_graph_background

def _get_run_or_raise(session, run_id: str) -> Run:
    try:
        rid = uuid.UUID(run_id)
    except ValueError:
        raise ValueError(f"Invalid UUID: {run_id}")
    run = session.get(Run, rid)
    if not run:
        raise ValueError(f"Run {run_id} not found.")
    return run

def register_tools(mcp):
    @mcp.tool()
    def create_run(file_paths: List[str], compliance_rules: str) -> dict:
        """Create a new document processing run.
        
        Args:
            file_paths: List of absolute file paths to process.
            compliance_rules: Required rules or playbook to evaluate the documents against.
            
        Returns:
            dict: Initial run state.
        """
        if not file_paths:
            raise ValueError("Must provide at least one valid file_path.")
        if not compliance_rules or not compliance_rules.strip():
            raise ValueError("Compliance rules are required and cannot be blank.")
            
        session_factory = get_session_factory()
        with session_factory() as session:
            initial_state = create_run_record(session, file_paths, compliance_rules)
            run_id_str = initial_state["run_id"]
        
        # Start graph background execution
        threading.Thread(target=run_graph_background, args=(run_id_str, initial_state), daemon=True).start()
        
        return initial_state

    @mcp.tool()
    def get_run(run_id: str) -> dict:
        """Get the basic database status of a run.
        
        Args:
            run_id: The ID of the run.
        """
        session_factory = get_session_factory()
        with session_factory() as session:
            run = _get_run_or_raise(session, run_id)
            return {
                "run_id": str(run.id),
                "status": run.status,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            }

    @mcp.tool()
    def get_run_state(run_id: str) -> dict:
        """Retrieve the durable LangGraph state for a run, showing the execution trace.
        
        Args:
            run_id: The ID of the run.
        """
        checkpointer_gen = get_checkpointer()
        checkpointer = next(checkpointer_gen)
        try:
            state = get_checkpoint_state(checkpointer, run_id)
                
            session_factory = get_session_factory()
            with session_factory() as session:
                run = session.get(Run, uuid.UUID(run_id))
                if run:
                    if run.status == "failed":
                        state["status"] = "failed"
                        if run.input_metadata and "error" in run.input_metadata:
                            errors = state.get("errors") or []
                            if run.input_metadata["error"] not in errors:
                                errors.append(run.input_metadata["error"])
                            state["errors"] = errors
                    elif not state.get("status"):
                        state["status"] = run.status
                        
            return state
        finally:
            checkpointer_gen.close()

    @mcp.tool()
    def resume_run(run_id: str) -> dict:
        """Resume a stalled or failed workflow run from its existing checkpoint.
        
        Args:
            run_id: The ID of the run to resume.
        """
        session_factory = get_session_factory()
        with session_factory() as session:
            run = _get_run_or_raise(session, run_id)
            if run.status == "completed":
                raise ValueError(f"Cannot resume a completed run.")
                
            mark_run_running(session, run)
            
        # Start graph background execution from checkpoint (None initial state triggers resume)
        threading.Thread(target=run_graph_background, args=(run_id, None), daemon=True).start()
        
        return {"run_id": run_id, "status": "resumed"}

    @mcp.tool()
    def add_documents(run_id: str, file_paths: List[str]) -> dict:
        """Add new documents to an existing run and selectively process them.
        
        Args:
            run_id: The ID of the run.
            file_paths: List of absolute file paths to add.
        """
        import hashlib
        session_factory = get_session_factory()
        added_docs = []
        
        with session_factory() as session:
            run = _get_run_or_raise(session, run_id)
            
            for path in file_paths:
                if not os.path.exists(path):
                    raise ValueError(f"File not found: {path}")
                
                with open(path, "rb") as f:
                    content = f.read()
                    
                content_hash = hashlib.sha256(content).hexdigest()
                # Check if this exact file is already in the run
                existing_doc = session.query(Document).filter(
                    Document.run_id == run.id,
                    Document.hash == content_hash,
                    Document.name == os.path.basename(path),
                ).first()
                
                if not existing_doc:
                    # Let ingest_node create the document and its chunks together.
                    # Pre-creating a document here makes ingest treat it as a
                    # duplicate and skip parsing/chunk creation.
                    added_docs.append({"name": os.path.basename(path), "path": path, "byte_size": len(content)})
            
            if not added_docs:
                return {"run_id": run_id, "message": "All documents already exist in the run.", "added_documents": []}
                
            queue_document_paths(
                session,
                run,
                [doc["path"] for doc in added_docs],
                deduplicate_paths=True,
            )
            
        # Resume the workflow so ingest node picks up the new files
        threading.Thread(target=run_graph_background, args=(run_id, None), daemon=True).start()
        
        return {"run_id": run_id, "added_documents": added_docs, "status": "running"}

    @mcp.tool()
    def get_findings(run_id: str) -> List[dict]:
        """Get all persisted compliance findings for a run.
        
        Args:
            run_id: The ID of the run.
        """
        session_factory = get_session_factory()
        with session_factory() as session:
            findings = session.query(Finding).filter(Finding.run_id == uuid.UUID(run_id)).all()
            return [
                {
                    "finding_id": str(f.id),
                    "title": f.title,
                    "summary": f.summary,
                    "severity": f.severity,
                    "status": f.status,
                }
                for f in findings
            ]

    @mcp.tool()
    def review_finding(run_id: str, finding_id: str, decision: str, comment: str = None) -> dict:
        """Perform a human approval action programmatically.
        
        Args:
            run_id: The ID of the run.
            finding_id: The ID of the finding.
            decision: 'approve', 'reject', or 'edit'
            comment: Optional reviewer comment.
        """
        session_factory = get_session_factory()
        with session_factory() as session:
            finding_uuid = uuid.UUID(finding_id)
            run_uuid = uuid.UUID(run_id)
            review = apply_finding_review(
                session,
                run_uuid,
                finding_uuid,
                decision,
            )
            pending_count = review.pending_count
            finding_status = review.status
            
        if pending_count == 0:
            # All findings are reviewed! Update the graph state and resume.
            checkpointer_gen = get_checkpointer()
            checkpointer = next(checkpointer_gen)
            try:
                update_approval_checkpoint(checkpointer, run_id, "mcp_machine")
                
                threading.Thread(target=run_graph_background, args=(run_id, None), daemon=True).start()
                return {"finding_id": finding_id, "status": finding_status, "message": "All findings reviewed, workflow resumed."}
            finally:
                checkpointer_gen.close()
            
        return {"finding_id": finding_id, "status": finding_status, "message": f"{pending_count} findings remaining."}

    @mcp.tool()
    def get_report(run_id: str) -> dict:
        """Retrieve the generated report metadata.
        
        Args:
            run_id: The ID of the run.
        """
        session_factory = get_session_factory()
        with session_factory() as session:
            run = _get_run_or_raise(session, run_id)
            meta = dict(run.input_metadata or {})
            report_meta = meta.get("report_metadata", {})
            
            if not report_meta:
                return {"status": "unavailable", "message": "Report not yet generated for this run."}
                
            return {
                "status": "available",
                "report_metadata": report_meta
            }
