"""Service for managing Workflow Runs."""

import uuid

from sqlalchemy.orm import Session

from app.models.run import Run


def get_run(session: Session, run_id: uuid.UUID) -> Run | None:
    """Retrieve a run by its ID."""
    return session.get(Run, run_id)

def update_run_status(session: Session, run_id: uuid.UUID, status: str) -> Run:
    """Update the status of an existing run."""
    run = session.get(Run, run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found.")
    run.status = status
    session.commit()
    return run


def sync_run_status(
    session: Session,
    run_id: uuid.UUID | str,
    final_state: dict,
    *,
    honor_failed_status: bool = False,
) -> None:
    """Persist a workflow result using the caller's established status policy."""
    run_uuid = run_id if isinstance(run_id, uuid.UUID) else uuid.UUID(run_id)
    run = session.get(Run, run_uuid)
    if not run:
        return

    current_stage = final_state.get("current_stage")
    if honor_failed_status and final_state.get("status") == "failed":
        run.status = "failed"
    elif current_stage == "completed":
        run.status = "completed"
    elif current_stage == "failed":
        run.status = "failed"
    session.commit()
