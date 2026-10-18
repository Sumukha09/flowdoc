"""API routes for managing workflow runs."""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from langgraph.checkpoint.postgres import PostgresSaver

from app.api.deps import get_checkpointer, get_db_session
from app.api.schemas.run import RunCreateRequest, RunResponse, RunStateResponse, RunDetailsResponse, RunStatsResponse, AuditLogResponse, CostReportResponse
from app.api.schemas.approval import ApprovalRequest
from app.models.run import Run
from app.models.document import Document
from app.models.finding import Finding
from app.models.claim import Claim
from app.models.cost_report import CostReport
from app.models.audit_log import AuditLog
from app.models.claim_evidence import ClaimEvidence as Evidence
from app.services.run import get_run, sync_run_status
from app.services.run_workflow import (
    FindingAlreadyReviewed,
    FindingNotFound,
    create_run as create_run_record,
    get_checkpoint_state,
    get_run_details as build_run_details,
    mark_run_running,
    queue_document_paths,
    review_finding as apply_finding_review,
    update_approval_checkpoint,
)
from app.services.workflow_runner import run_graph_background
from app.workflow.graph import compile_workflow

router = APIRouter(prefix="/runs", tags=["runs"])

SUPPORTED_DOCUMENT_EXTENSIONS = {".pdf", ".txt"}


def _validate_document_name(name: str) -> None:
    if os.path.splitext(name)[1].lower() not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and plain-text (.txt) files are supported.",
        )


@router.post(
    "",
    response_model=RunStateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new document processing run",
)
def create_run(
    request: RunCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
) -> RunStateResponse:
    """Create a new run and invoke the workflow graph."""
    print(f"[DEBUG] create_run endpoint hit! request files count: {len(request.files)}")

    file_paths = []
    
    for f in request.files:
        candidate_name = f.file_name if f.file_content_base64 else f.file_path
        if candidate_name:
            _validate_document_name(os.path.basename(candidate_name))

        path = f.file_path
        if f.file_content_base64:
            import base64
            
            content = base64.b64decode(f.file_content_base64)
            name = os.path.basename(f.file_name or "uploaded_doc.pdf")
            _validate_document_name(name)
            upload_dir = os.path.join(os.getcwd(), "uploads", str(uuid.uuid4()))
            os.makedirs(upload_dir, exist_ok=True)
            path = os.path.join(upload_dir, name)
            with open(path, "wb") as file_out:
                file_out.write(content)
        
        if path:
            file_paths.append(path)

    if not file_paths:
        raise HTTPException(status_code=400, detail="Must provide at least one valid file_path or file_content_base64")

    initial_state = create_run_record(db, file_paths, request.compliance_rules)
    run_id_str = initial_state["run_id"]
    print(f"[DEBUG] DB commit successful. run_id: {run_id_str}")
    
    # 3. Schedule graph in background
    print(f"[DEBUG] Scheduling run_graph_background task for run {run_id_str}...")
    background_tasks.add_task(run_graph_background, run_id_str, initial_state)
        
    print(f"[DEBUG] Returning initial state for run {run_id_str}")
    return RunStateResponse(**initial_state)


@router.post(
    "/{run_id}/documents",
    status_code=status.HTTP_201_CREATED,
    summary="Add documents to an existing run",
)
def add_documents_to_run(
    run_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db_session),
    checkpointer: PostgresSaver = Depends(get_checkpointer),
):
    """Upload new documents to an existing run and selectively process them."""
    import hashlib
    
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found."
        )
        
    # Read files and hash them
    new_paths = []
    response_docs = []
    upload_dir = os.path.join(os.getcwd(), "uploads", str(run_id), str(uuid.uuid4()))
    os.makedirs(upload_dir, exist_ok=True)
    
    for f in files:
        if not f.filename:
            continue

        _validate_document_name(os.path.basename(f.filename))
            
        content = f.file.read()
        if not content:
            raise HTTPException(status_code=400, detail=f"File {f.filename} is empty")
            
        # Check size limit (e.g. 50MB)
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"File {f.filename} exceeds 50MB limit")
            
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Check if already added to this run
        source_name = os.path.basename(f.filename)
        existing_doc = db.query(Document).filter_by(hash=file_hash, run_id=run.id, name=source_name).first()
        if existing_doc:
            response_docs.append({
                "document_id": str(existing_doc.id),
                "filename": f.filename,
                "status": "already_exists"
            })
            continue
            
        # Save file to disk
        file_dir = os.path.join(upload_dir, str(uuid.uuid4()))
        os.makedirs(file_dir, exist_ok=True)
        path = os.path.join(file_dir, source_name)
        with open(path, "wb") as out_file:
            out_file.write(content)
            
        new_paths.append(path)
        response_docs.append({
            "filename": f.filename,
            "status": "queued"
        })
        
    if not new_paths:
        # All were duplicates, return idempotent success
        return {
            "run_id": str(run_id),
            "added_documents": response_docs,
            "existing_documents": [str(d.id) for d in run.documents],
            "run_status": run.status
        }
        
    # Append to run.input_metadata
    queue_document_paths(db, run, new_paths, deduplicate_paths=False)
    
    # Resume graph processing from ingest
    thread_config = {"configurable": {"thread_id": str(run_id)}}
    graph = compile_workflow(checkpointer=checkpointer, interrupt_before=["approval"])
    
    # Update LangGraph state to trick it into restarting from start node
    # This prevents the graph from instantly terminating if it was previously at END.
    try:
        from langgraph.graph import START
        graph.update_state(thread_config, {"current_stage": "ingest", "status": "running"}, as_node=START)
    except Exception as e:
        print(f"[ERROR] Failed to update state pointer to START: {e}")
        # fallback, may not work if graph is completed
        graph.update_state(thread_config, {"current_stage": "ingest", "status": "running"})
        
    # Start background task with empty initial_state, it will pick up from the updated checkpoint
    background_tasks.add_task(run_graph_background, str(run_id), {})
    
    return {
        "run_id": str(run_id),
        "added_documents": response_docs,
        "existing_documents": [str(d.id) for d in run.documents],
        "run_status": "running"
    }


@router.get(
    "",
    response_model=list[RunResponse],
    summary="List all runs",
)
def list_runs(
    db: Session = Depends(get_db_session),
) -> list[RunResponse]:
    """Retrieve all runs ordered by created_at descending."""
    runs = db.query(Run).order_by(Run.created_at.desc()).all()
    return [RunResponse.model_validate(r) for r in runs]


@router.post(
    "/{run_id}/commit_clean",
    summary="Commit a run with zero pending findings",
)
def commit_clean_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    checkpointer: PostgresSaver = Depends(get_checkpointer),
):
    """Manually advance the workflow when there are no findings to review."""
    pending_count = db.query(Finding).filter(Finding.run_id == run_id, Finding.status == "pending").count()
    if pending_count > 0:
        raise HTTPException(status_code=400, detail="Cannot commit cleanly while findings are pending.")

    thread_config = {"configurable": {"thread_id": str(run_id)}}
    graph = update_approval_checkpoint(checkpointer, str(run_id), "human_manual")
    
    try:
        final_state = graph.invoke(None, thread_config)
        sync_run_status(db, run_id, final_state)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Workflow failed to resume."
        ) from e
        
    return {"status": "success"}

@router.post(
    "/{run_id}/resume",
    response_model=RunStateResponse,
    summary="Resume a stalled run",
)
def resume_run(
    run_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    checkpointer: PostgresSaver = Depends(get_checkpointer),
) -> RunStateResponse:
    """Resume a stalled workflow run."""
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found."
        )
        
    if run.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resume a completed run."
        )
        
    run_id_str = str(run.id)
    
    initial_state = get_checkpoint_state(checkpointer, run_id_str)
        
    mark_run_running(db, run)
    
    print(f"[DEBUG] Resuming run_graph_background task for run {run_id_str}...")
    background_tasks.add_task(run_graph_background, run_id_str, initial_state)
    
    return RunStateResponse(**initial_state)


@router.get(
    "/{run_id}",
    response_model=RunResponse,
    summary="Get run status",
)
def get_run_status(
    run_id: uuid.UUID,
    db: Session = Depends(get_db_session),
) -> RunResponse:
    """Retrieve the basic database status of a run."""
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found."
        )
        
    return RunResponse.model_validate(run)


@router.get(
    "/{run_id}/state",
    response_model=RunStateResponse,
    summary="Get run workflow state",
)
def get_run_state(
    run_id: uuid.UUID,
    checkpointer: PostgresSaver = Depends(get_checkpointer),
) -> RunStateResponse:
    """Retrieve the durable LangGraph state for a run."""
    
    state = get_checkpoint_state(checkpointer, str(run_id))
        
    # Inject DB status and errors if the run failed outside the graph
    from app.db.session import get_session_factory
    from app.models.run import Run
    session_factory = get_session_factory()
    with session_factory() as session:
        run = session.get(Run, run_id)
        if run:
            if run.status == "failed":
                state["status"] = "failed"
                if run.input_metadata and "error" in run.input_metadata:
                    errors = state.get("errors") or []
                    errors.append(run.input_metadata["error"])
                    state["errors"] = errors
            elif not state.get("status"):
                state["status"] = run.status
                
    return RunStateResponse(**state)


@router.get(
    "/{run_id}/details",
    response_model=RunDetailsResponse,
    summary="Get detailed run information including documents and findings",
)
def get_run_details(
    run_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    checkpointer: PostgresSaver = Depends(get_checkpointer),
) -> RunDetailsResponse:
    """Retrieve detailed UI-ready data for a run."""
    return RunDetailsResponse(**build_run_details(db, checkpointer, run_id))

@router.post(
    "/{run_id}/findings/{finding_id}/approve",
    status_code=status.HTTP_200_OK,
    summary="Submit a human review decision for a finding",
)
def approve_finding(
    run_id: uuid.UUID,
    finding_id: uuid.UUID,
    request: ApprovalRequest,
    db: Session = Depends(get_db_session),
    checkpointer: PostgresSaver = Depends(get_checkpointer),
) -> dict:
    """Record a human reviewer's decision for a specific finding.
    
    If all findings for the run are reviewed, the workflow automatically resumes.
    """
    try:
        result = apply_finding_review(
            db,
            run_id,
            finding_id,
            request.decision,
            comment=request.comment,
            edited_text=request.edited_text,
            audit=True,
        )
    except FindingNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except FindingAlreadyReviewed as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    pending_count = result.pending_count
    
    if pending_count == 0:
        # All findings are reviewed! Update the graph state and resume.
        thread_config = {"configurable": {"thread_id": str(run_id)}}
        graph = update_approval_checkpoint(checkpointer, str(run_id), "human")
        
        # Resume the workflow by invoking it with no new input
        try:
            final_state = graph.invoke(None, thread_config)
            sync_run_status(db, run_id, final_state)
                
        except Exception as e:
            # Again, log the error safely without exposing raw traces
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Workflow failed to resume."
            ) from e
            
    return {"status": "success", "remaining_pending": pending_count}

@router.get(
    "/stats/global",
    response_model=RunStatsResponse,
    summary="Get global workflow statistics",
)
def get_global_stats(db: Session = Depends(get_db_session)) -> RunStatsResponse:
    """Retrieve aggregate statistics across all runs."""
    total_runs = db.query(Run).count()
    active_runs = db.query(Run).filter(Run.status.in_(["pending", "running"])).count()
    successful_runs = db.query(Run).filter(Run.status == "completed").count()
    failed_runs = db.query(Run).filter(Run.status == "failed").count()
    
    total_docs = db.query(Document).count()
    total_claims = db.query(Claim).count()
    total_findings = db.query(Finding).count()
    
    pending_approvals = db.query(Finding).filter(Finding.status == "pending").count()
    
    from sqlalchemy.sql import func
    total_cost_micro = db.query(func.sum(CostReport.total_cost_micro)).scalar() or 0
    
    return RunStatsResponse(
        total_runs=total_runs,
        active_runs=active_runs,
        successful_runs=successful_runs,
        failed_runs=failed_runs,
        total_documents=total_docs,
        total_claims=total_claims,
        total_findings=total_findings,
        pending_approvals=pending_approvals,
        total_cost_micro=int(total_cost_micro)
    )

@router.get(
    "/{run_id}/audit",
    response_model=list[AuditLogResponse],
    summary="Get audit logs for a run",
)
def get_run_audit(
    run_id: uuid.UUID,
    db: Session = Depends(get_db_session),
) -> list[AuditLogResponse]:
    """Retrieve chronological audit trail for a run."""
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    logs = db.query(AuditLog).filter(AuditLog.run_id == run_id).order_by(AuditLog.created_at.asc()).all()
    return [AuditLogResponse.model_validate(log) for log in logs]

@router.get(
    "/{run_id}/cost",
    response_model=CostReportResponse,
    summary="Get cost report for a run",
)
def get_run_cost(
    run_id: uuid.UUID,
    db: Session = Depends(get_db_session),
) -> CostReportResponse:
    """Retrieve LLM cost observability data for a run."""
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    cost = db.query(CostReport).filter(CostReport.run_id == run_id).first()
    if not cost:
        raise HTTPException(status_code=404, detail="Cost report not found for run")
        
    return CostReportResponse.model_validate(cost)


from fastapi.responses import StreamingResponse
import io

@router.get(
    "/{run_id}/report",
    summary="Download the final verified PDF report",
)
def download_report(
    run_id: uuid.UUID,
    db: Session = Depends(get_db_session),
    checkpointer: PostgresSaver = Depends(get_checkpointer),
):
    run = get_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    findings = db.query(Finding).filter(Finding.run_id == run_id, Finding.status == "approved").all()
    
    # Get stats from state
    from app.workflow.graph import compile_workflow
    graph = compile_workflow(checkpointer=checkpointer, interrupt_before=["approval"])
    thread_config = {"configurable": {"thread_id": str(run_id)}}
    state_snapshot = graph.get_state(thread_config)
    
    total_checks = 0
    passed_checks = 0
    if state_snapshot and state_snapshot.values:
        total_checks = state_snapshot.values.get("compliance_checks_total", 0)
        passed_checks = state_snapshot.values.get("compliance_checks_passed", 0)
    
    # Generate PDF in memory
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    story.append(Paragraph(f"Verified Deliverable: Run {str(run_id)[:8]}", styles['Title']))
    story.append(Spacer(1, 12))
    

    story.append(Paragraph(f"<b>Findings:</b> {len(findings)}", styles['Normal']))
    if not findings:
        story.append(Paragraph("<b>Status:</b> NO FINDINGS", styles['Normal']))
    else:
        story.append(Paragraph("<b>Status:</b> FINDINGS PRESENT", styles['Normal']))
        
    story.append(Spacer(1, 12))
    
    if not findings:
        story.append(Paragraph("No verified findings to report. The corpus is clean.", styles['Normal']))
    else:
        for finding in findings:
            story.append(Paragraph(f"Finding: {finding.title}", styles['Heading2']))
            if finding.summary:
                story.append(Paragraph(f"Summary: {finding.summary}", styles['Normal']))
            story.append(Spacer(1, 6))
            
            claims = db.query(Claim).filter(Claim.finding_id == finding.id).all()
            for claim in claims:
                story.append(Paragraph(f"Claim: {claim.statement}", styles['Bullet']))
                evidences = db.query(Evidence).filter(Evidence.claim_id == claim.id).all()
                for ev in evidences:
                    doc_name = ev.chunk.document.name if ev.chunk and ev.chunk.document else "Unknown Document"
                    story.append(Paragraph(f"Source Document: {doc_name}", styles['Normal']))
                    if ev.snippet:
                        story.append(Paragraph(f"Evidence: \"{ev.snippet}\"", styles['Italic']))
            story.append(Spacer(1, 12))
            
    doc.build(story)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=flowdocs_report_{str(run_id)[:8]}.pdf"}
    )

import os
from fastapi.responses import FileResponse

@router.get(
    "/{run_id}/documents/{doc_id}/content",
    summary="Stream raw document content to the browser",
)
def get_document_content(
    run_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: Session = Depends(get_db_session),
):
    doc = db.query(Document).filter(Document.id == doc_id, Document.run_id == run_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    source_path = doc.metadata_json.get("source")
    if not source_path or not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="Source file missing on disk")
        
    return FileResponse(source_path)
