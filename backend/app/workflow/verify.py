
import uuid

from app.llm.schemas import LLMRequest
from app.models import Claim, ClaimEvidence, DocumentChunk, Finding
from app.workflow.constants import NODE_APPROVAL, NODE_COMPLETE, NODE_VERIFY
from app.workflow.dependencies import WorkflowDependencies, default_workflow_dependencies
from app.workflow.prompts import VERIFY_SYSTEM_PROMPT, VerificationResult
from app.workflow.state import WorkflowState


def verify_node(
    state: WorkflowState,
    dependencies: WorkflowDependencies | None = None,
) -> dict:
    """Verify claims against their source evidence."""
    # ALWAYS check if human review is required first, so early returns don't skip it
    dependencies = dependencies or default_workflow_dependencies()
    run_id_str = state.get("run_id")
    approval_required = False
    
    if run_id_str:
        try:
            run_id = uuid.UUID(run_id_str) if isinstance(run_id_str, str) else run_id_str
            session_factory = dependencies.session_factory()
            with session_factory() as session:
                pending_count = session.query(Finding).filter(
                    Finding.run_id == run_id, 
                    Finding.status == "pending"
                ).count()
                approval_required = pending_count > 0
        except ValueError:
            pass # Handle invalid UUIDs in tests

    extracted_claim_ids = state.get("extracted_claim_ids", [])
    if not extracted_claim_ids:
        return {
            "current_stage": NODE_APPROVAL if approval_required else NODE_COMPLETE,
            "completed_stages": state.get("completed_stages", []) + [NODE_VERIFY],
            "verified_claim_ids": [],
            "verification_result_counts": {},
            "failed_insufficient_evidence_count": 0,
            "approval_required": approval_required,
        }

    session_factory = dependencies.session_factory()
    llm = dependencies.llm_factory()
    
    previously_verified = set(state.get("verified_claim_ids", []))
    verified_claim_ids = list(state.get("verified_claim_ids", []))
    
    # Initialize counts from previous state to accumulate instead of replace
    prev_counts = state.get("verification_result_counts", {})
    result_counts = {
        "verified": prev_counts.get("verified", 0),
        "contradicted": prev_counts.get("contradicted", 0),
        "insufficient_evidence": prev_counts.get("insufficient_evidence", 0)
    }
    
    with session_factory() as session:
        for cid in extracted_claim_ids:
            if cid in previously_verified:
                continue
            
            claim = session.get(Claim, uuid.UUID(cid))
            if not claim:
                continue
                
            evidence_records = session.query(ClaimEvidence).filter(ClaimEvidence.claim_id == claim.id).all()
            if not evidence_records:
                continue
                
            # For simplicity, verify against the first piece of evidence
            # In a real setup, we might verify against all chunk texts
            evidence = evidence_records[0]
            chunk = session.get(DocumentChunk, evidence.chunk_id)
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
                system_prompt=VERIFY_SYSTEM_PROMPT,
                user_prompt=f"Claim:\n{claim.statement}\n\nEvidence source:\n{evidence.snippet or chunk.text}",
                response_schema=VerificationResult,
                max_output_tokens=200,
                request_id=str(uuid.uuid4()),
                run_id=state.get("run_id"),
                node="verify",
                purpose="claim_verification"
            )
            
            try:
                resp = llm.generate(req)
                
                # Update tokens
                state["total_tokens_used"] = state.get("total_tokens_used", 0) + (resp.input_tokens + resp.output_tokens)
                
                parsed = resp.parsed_content
                if parsed:
                    # Update evidence relevance
                    evidence.relevance = parsed.relevance_score
                    
                    # Track result
                    res_type = parsed.supports_claim
                    if res_type in result_counts:
                        result_counts[res_type] += 1
                        
                    if res_type == "verified":
                        verified_claim_ids.append(str(claim.id))
                        
            except Exception as e:
                import traceback
                print(f"[ERROR] verify_node failed for claim {claim.id}: {e}")
                traceback.print_exc()
                
        session.commit()

    return {
        "current_stage": NODE_APPROVAL if approval_required else NODE_COMPLETE,
        "completed_stages": state.get("completed_stages", []) + [NODE_VERIFY],
        "verified_claim_ids": verified_claim_ids,
        "verification_result_counts": result_counts,
        "failed_insufficient_evidence_count": result_counts.get("insufficient_evidence", 0),
        "approval_required": approval_required,
    }
