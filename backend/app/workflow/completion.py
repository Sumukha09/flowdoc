
import uuid

from app.models import AuditLog, Finding, Run
from app.workflow.constants import (
    NODE_ANALYZE, NODE_APPROVAL, NODE_COMPLETE, NODE_EXTRACT, NODE_INGEST, NODE_VERIFY,
)
from app.workflow.state import WorkflowState
from app.workflow.dependencies import WorkflowDependencies, default_workflow_dependencies


def complete_node(
    state: WorkflowState,
    dependencies: WorkflowDependencies | None = None,
) -> dict:
    """Mark the workflow as completed."""
    run_id_str = state.get("run_id")
    if not run_id_str:
        return {
            "status": "completed",
            "current_stage": NODE_COMPLETE
        }
        
    dependencies = dependencies or default_workflow_dependencies()
    session_factory = dependencies.session_factory()
    with session_factory() as session:
        try:
            run_id = uuid.UUID(run_id_str) if isinstance(run_id_str, str) else run_id_str
            run = session.get(Run, run_id)
            if run:
                run.status = "completed"
                session.add(AuditLog(
                    run_id=run.id,
                    actor="system",
                    action="workflow_completed",
                    payload={"stage": NODE_COMPLETE}
                ))
                session.commit()
                
                meta = dict(run.input_metadata or {})
        except ValueError:
            pass
            report_meta = meta.get("report_metadata", {})
            
            prev_version = report_meta.get("new_version", 0)
            new_version = prev_version + 1
            
            all_findings = session.query(Finding).filter(Finding.run_id == run.id).all()
            current_finding_titles = [f.title for f in all_findings]
            
            prev_titles = report_meta.get("all_titles", [])
            
            changed = [t for t in current_finding_titles if t not in prev_titles]
            unchanged = [t for t in prev_titles if t in current_finding_titles]
            
            new_report_meta = {
                "previous_version": prev_version,
                "new_version": new_version,
                "changed_sections": changed,
                "unchanged_sections": unchanged,
                "all_titles": current_finding_titles,
                "source_document_ids": state.get("ingested_document_ids", []),
                "triggered_by": "incremental_update" if prev_version > 0 else "initial_run"
            }
            
            meta["report_metadata"] = new_report_meta
            run.input_metadata = meta
            session.commit()
            
    return {
        "current_stage": "completed",
        "status": "completed",
        "completed_stages": state.get("completed_stages", []) + [NODE_COMPLETE],
    }
