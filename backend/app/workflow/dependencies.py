
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.config import get_settings
from app.db.session import get_session_factory


def _default_llm_factory():
    # Resolve the graph export when called so existing integrations that patch
    # app.workflow.graph.get_llm continue to affect direct node invocations.
    from app.workflow.graph import get_llm

    return get_llm()


@dataclass(frozen=True)
class WorkflowDependencies:
    """Replaceable dependencies shared by workflow node implementations."""

    session_factory: Callable[[], Any] = get_session_factory
    llm_factory: Callable[[], Any] = _default_llm_factory
    settings_factory: Callable[[], Any] = get_settings


def default_workflow_dependencies() -> WorkflowDependencies:
    """Return production dependencies for direct node calls and compilation."""
    return WorkflowDependencies()
