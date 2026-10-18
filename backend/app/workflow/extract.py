
import uuid

from app.llm.schemas import LLMRequest
from app.models import Claim, ClaimEvidence, DocumentChunk
from app.workflow.constants import NODE_ANALYZE, NODE_EXTRACT
from app.workflow.dependencies import WorkflowDependencies, default_workflow_dependencies
from app.workflow.prompts import EXTRACT_SYSTEM_PROMPT, ExtractionResult
from app.workflow.state import WorkflowState


def extract_node(
    state: WorkflowState,
    dependencies: WorkflowDependencies | None = None,
) -> dict:
    """Extract claims from ingested document chunks using the LLM."""
    chunk_ids = state.get("chunk_ids", [])
    if not chunk_ids:
        return {
            "current_stage": NODE_ANALYZE,
            "completed_stages": state.get("completed_stages", []) + [NODE_EXTRACT],
        }

    dependencies = dependencies or default_workflow_dependencies()
    session_factory = dependencies.session_factory()
    llm = dependencies.llm_factory()
    
    previously_processed = set(state.get("processed_chunk_ids", []))
    extracted_claim_ids = list(state.get("extracted_claim_ids", []))
    processed_chunk_ids = list(state.get("processed_chunk_ids", []))
    
    with session_factory() as session:
        for chunk_id_str in chunk_ids:
            if chunk_id_str in previously_processed:
                continue
            
            chunk = session.get(DocumentChunk, uuid.UUID(chunk_id_str))
            if not chunk:
                continue
                
            # Check budget
            total_tokens_used = state.get("total_tokens_used", 0)
            token_budget = dependencies.settings_factory().llm_token_budget
            if total_tokens_used >= token_budget:
                return {
                    "current_stage": "failed",
                    "status": "failed",
                    "errors": [f"Token budget exceeded ({total_tokens_used} >= {token_budget}). Requires continuation/retry."],
                }

            req = LLMRequest(
                system_prompt=EXTRACT_SYSTEM_PROMPT,
                user_prompt=f"Text to analyze:\n\n{chunk.text}",
                response_schema=ExtractionResult,
                max_output_tokens=8192,
                request_id=str(uuid.uuid4()),
                run_id=state.get("run_id"),
                node="extract",
                purpose="extract_claims_from_chunk"
            )
            
            try:
                resp = llm.generate(req)
                
                # Update tokens
                state["total_tokens_used"] = state.get("total_tokens_used", 0) + (resp.input_tokens + resp.output_tokens)
                
                parsed = resp.parsed_content
                if not parsed or not hasattr(parsed, "claims"):
                    continue
                    
                for extracted_claim in parsed.claims:
                    exact_quote = (extracted_claim.exact_quote or "").strip()
                    if not exact_quote or exact_quote not in chunk.text:
                        continue
                    claim = Claim(
                        run_id=uuid.UUID(state.get("run_id")),
                        statement=extracted_claim.statement,
                        confidence=1.0,  # Or from LLM if we added it
                    )
                    session.add(claim)
                    session.flush() # get ID
                    
                    evidence = ClaimEvidence(
                        claim_id=claim.id,
                        chunk_id=chunk.id,
                        snippet=exact_quote,
                    )
                    session.add(evidence)
                    extracted_claim_ids.append(str(claim.id))
                    
                processed_chunk_ids.append(str(chunk.id))
            except Exception as e:
                import traceback
                print(f"[ERROR] extract_node failed for chunk {chunk.id}: {e}")
                traceback.print_exc()                
                session.rollback()
                return {
                    "current_stage": "failed",
                    "status": "failed",
                    "errors": state.get("errors", []) + [f"LLM extraction failed on chunk {chunk.id}: {str(e)}"]
                }
        session.commit()

    return {
        "current_stage": NODE_ANALYZE,
        "completed_stages": state.get("completed_stages", []) + [NODE_EXTRACT],
        "extracted_claim_ids": extracted_claim_ids,
        "extracted_entity_count": len(extracted_claim_ids),
        "processed_chunk_ids": processed_chunk_ids,
    }
