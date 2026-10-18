"""Execute a run's persisted workflow and synchronize its final status."""
from __future__ import annotations

import traceback
import uuid

from langgraph.checkpoint.postgres import PostgresSaver

from app.services.run import sync_run_status
from app.workflow.graph import compile_workflow


def run_graph_background(run_id_str: str, initial_state: dict):
    """Run or resume the workflow and persist its terminal status.

    The function intentionally retains the current background execution
    behavior so HTTP, MCP, and startup recovery share the same implementation.
    """
    from app.config import get_settings

    settings = get_settings()
    conn_string = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
    try:
        with PostgresSaver.from_conn_string(conn_string) as saver:
            saver.setup()
            graph = compile_workflow(checkpointer=saver, interrupt_before=["approval"])
            thread_config = {"configurable": {"thread_id": run_id_str}}
            final_state = graph.invoke(initial_state, thread_config)

            from app.db.session import get_session_factory

            session_factory = get_session_factory()
            with session_factory() as session:
                sync_run_status(session, run_id_str, final_state, honor_failed_status=True)
    except Exception as e:
        print(f"[ERROR] Graph execution failed for run {run_id_str}: {e}")
        traceback.print_exc()
        try:
            from app.db.session import get_session_factory
            from app.models.run import Run

            session_factory = get_session_factory()
            with session_factory() as session:
                run = session.get(Run, uuid.UUID(run_id_str))
                if run:
                    run.status = "failed"
                    if run.input_metadata is None:
                        run.input_metadata = {}
                    meta = dict(run.input_metadata)
                    meta["error"] = str(e)
                    run.input_metadata = meta
                    session.commit()
        except:
            pass
