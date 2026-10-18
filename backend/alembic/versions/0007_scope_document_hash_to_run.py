"""Scope document content deduplication to a run.

Revision ID: 0007_scope_document_hash_to_run
Revises: 0006_doc_unique_fix
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0007_scope_document_hash_to_run"
down_revision: Union[str, None] = "0006_doc_unique_fix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_documents_hash", "documents", type_="unique")
    op.create_unique_constraint(
        "uq_documents_run_hash_name", "documents", ["run_id", "hash", "name"]
    )


def downgrade() -> None:
    # Existing data may contain the same content in multiple runs, so collapse
    # must be done by an operator before restoring the former global constraint.
    op.drop_constraint("uq_documents_run_hash_name", "documents", type_="unique")
    op.create_unique_constraint("uq_documents_hash", "documents", ["hash"])
