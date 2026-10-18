
import hashlib
import os
import uuid

from sqlalchemy.exc import IntegrityError

from app.models import Document, DocumentChunk, Run
from app.workflow.constants import NODE_EXTRACT, NODE_INGEST
from app.workflow.dependencies import WorkflowDependencies, default_workflow_dependencies
from app.workflow.state import WorkflowState


def ingest_node(
    state: WorkflowState,
    dependencies: WorkflowDependencies | None = None,
) -> dict:
    """Real ingestion stage that reads a file and records it to the database.

    Returns a partial state update that records the transition from
    ``ingest`` to ``extract``. If the input is invalid, transitions to a controlled
    error state.
    """
    print("[DEBUG] ingest_node started!")
    run_id_str = state.get("run_id")
    if not run_id_str:
        return {
            "current_stage": "failed",
            "status": "failed",
            "errors": ["Missing run_id in state"],
        }
    
    try:
        run_uuid = uuid.UUID(run_id_str)
    except ValueError:
        return {
            "current_stage": "failed",
            "status": "failed",
            "errors": [f"Invalid run_id format: {run_id_str}"],
        }

    dependencies = dependencies or default_workflow_dependencies()
    session_factory = dependencies.session_factory()
    with session_factory() as session:
        run = session.get(Run, run_uuid)
        if not run:
            return {
                "current_stage": "failed",
                "status": "failed",
                "errors": [f"Run not found: {run_id_str}"],
            }
        
        input_metadata = run.input_metadata or {}
        file_paths = input_metadata.get("file_paths", [])
        if not file_paths:
            return {
                "current_stage": "failed",
                "status": "failed",
                "errors": ["Missing file_paths in Run.input_metadata"],
            }
        
        all_doc_ids = []
        all_chunk_ids = []
        
        for file_path in file_paths:
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                continue
                
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
            except OSError as e:
                return {
                    "current_stage": "failed",
                    "status": "failed",
                    "errors": [f"Error reading file {file_path}: {e}"],
                }
            
            file_hash = hashlib.sha256(content).hexdigest()
            byte_size = len(content)
            name = os.path.basename(file_path)
            
            # Check for duplicate hash
            existing = session.query(Document).filter_by(run_id=run.id, hash=file_hash, name=name).first()
            if existing:
                all_doc_ids.append(str(existing.id))
                chunks = session.query(DocumentChunk).filter_by(document_id=existing.id).all()
                all_chunk_ids.extend([str(c.id) for c in chunks])
                continue
            
            # Parse content
            if name.lower().endswith(".pdf"):
                try:
                    import fitz
                    doc = fitz.open(stream=content, filetype="pdf")
                    text_content = ""
                    for page in doc:
                        text_content += page.get_text() + "\n\n"
                    doc.close()
                except Exception as e:
                    return {
                        "current_stage": "failed",
                        "status": "failed",
                        "errors": [f"Error parsing PDF {name}: {e}"],
                    }
            else:
                try:
                    text_content = content.decode("utf-8")
                except UnicodeDecodeError:
                    text_content = content.decode("latin-1")
                
            raw_chunks = [p.strip() for p in text_content.split("\n\n") if p.strip()]
            if not raw_chunks:
                raw_chunks = [text_content.strip()] if text_content.strip() else ["(Empty Document)"]
                
            document = Document(
                run_id=run.id,
                hash=file_hash,
                name=name,
                byte_size=byte_size,
                metadata_json={"source": file_path}
            )
            session.add(document)
            
            try:
                session.commit()
                all_doc_ids.append(str(document.id))
                
                db_chunks = []
                for i, text in enumerate(raw_chunks):
                    chunk = DocumentChunk(
                        document_id=document.id,
                        run_id=run.id,
                        chunk_index=i,
                        text=text
                    )
                    db_chunks.append(chunk)
                    session.add(chunk)
                session.commit()
                all_chunk_ids.extend([str(c.id) for c in db_chunks])
            except IntegrityError as e:
                session.rollback()
                existing = session.query(Document).filter_by(run_id=run.id, hash=file_hash, name=name).first()
                if existing:
                    all_doc_ids.append(str(existing.id))
                    chunks = session.query(DocumentChunk).filter_by(document_id=existing.id).all()
                    all_chunk_ids.extend([str(c.id) for c in chunks])
                else:
                    return {
                        "current_stage": "failed",
                        "status": "failed",
                        "errors": [f"Database error during ingestion: {e}"],
                    }
        
        if not all_doc_ids:
             return {
                "current_stage": "failed",
                "status": "failed",
                "errors": ["No valid documents ingested."],
            }
        
        return {
            "current_stage": NODE_EXTRACT,
            "completed_stages": [NODE_INGEST],
            "document_ids": all_doc_ids,
            "ingested_document_ids": all_doc_ids,
            "chunk_ids": all_chunk_ids,
            "chunk_count": len(all_chunk_ids),
        }
