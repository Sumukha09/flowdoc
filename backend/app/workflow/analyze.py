
import uuid

from app.llm.schemas import LLMRequest
from app.models import Claim, ClaimEvidence, DocumentChunk, Finding, Run
from app.workflow.constants import NODE_ANALYZE, NODE_VERIFY
from app.workflow.dependencies import WorkflowDependencies, default_workflow_dependencies
from app.workflow.prompts import ANALYZE_SYSTEM_PROMPT, AnalysisResult
from app.workflow.state import WorkflowState


def analyze_node(
    state: WorkflowState,
    dependencies: WorkflowDependencies | None = None,
) -> dict:
    """Analyze extracted claims to identify findings and conflicts."""
    extracted_claim_ids = state.get("extracted_claim_ids", [])

    dependencies = dependencies or default_workflow_dependencies()
    session_factory = dependencies.session_factory()
    llm = dependencies.llm_factory()
    
    previously_analyzed = set(state.get("analyzed_claim_ids", []))
    analyzed_finding_ids = list(state.get("analyzed_finding_ids", []))
    analyzed_claim_ids = list(state.get("analyzed_claim_ids", []))
    
    with session_factory() as session:
        claims = []
        old_claims = []
        for cid in extracted_claim_ids:
            claim = session.get(Claim, uuid.UUID(cid))
            if claim:
                if cid in previously_analyzed:
                    old_claims.append(claim)
                else:
                    claims.append(claim)
                    analyzed_claim_ids.append(str(claim.id))
                
        # Get compliance rules from the run
        run_id = uuid.UUID(state.get("run_id"))
        run = session.get(Run, run_id)
        compliance_rules = run.input_metadata.get("compliance_rules") if run and run.input_metadata else None
        
        # Fetch raw chunks for corpus
        chunk_objs = []
        corpus_parts = []
        for chunk_id_str in state.get("processed_chunk_ids", []):
            chunk = session.get(DocumentChunk, uuid.UUID(chunk_id_str))
            if chunk:
                chunk_objs.append(chunk)
                document_name = chunk.document.name if chunk.document else "Unknown source document"
                corpus_parts.append(
                    f"--- source_chunk_id: {chunk.id}; source_document: {document_name} ---\n{chunk.text}"
                )
                
        # Collect old claims for context
        old_claims_text = ""
        if old_claims:
            old_claims_data = [f"Claim ID: {c.id}\nStatement: {c.statement}" for c in old_claims]
            old_claims_text = "Existing Baseline Claims (For Context Only):\n" + "\n".join(old_claims_data) + "\n\n"
            
        # Collect claims and their evidence snippets
        claims_data = []
        for c in claims:
            evidence_records = session.query(ClaimEvidence).filter(ClaimEvidence.claim_id == c.id).all()
            evidence_texts = [f" - {ev.snippet}" for ev in evidence_records if ev.snippet]
            evidence_block = "\n".join(evidence_texts) if evidence_texts else " - No evidence found"
            claims_data.append(f"Claim ID: {c.id}\nStatement: {c.statement}\nEvidence:\n{evidence_block}")
        
        claims_text = "New Extracted Claims and Evidence (To Evaluate):\n" + "\n\n".join(claims_data)
        
        corpus_text = "RAW SOURCE DOCUMENTS (CORPUS):\n" + "\n\n".join(corpus_parts) if corpus_parts else ""
        
        user_prompt = corpus_text + "\n\n" + old_claims_text + claims_text
        user_prompt += """

MANDATORY DOCUMENT AUDIT (perform this even when no compliance rules were supplied):
Review every source document on its own, then compare the documents with each other.
Find materially incompatible statements about the same subject, including conflicting
durations, dates, amounts, parties, duties, or defined terms. Also check clear factual
errors (including calculations, dates, and statements contradicted elsewhere) and clear
legal errors when the document establishes the applicable jurisdiction and time period.
For each issue, explain the conflict/error and provide exact supporting quote(s) with the
source_chunk_id shown above each source section. A contradiction needs evidence for both
sides. For legal issues, name the applicable rule and flag only high-confidence conflicts;
if the jurisdiction, effective date, or rule is unclear, omit the issue. Do not report
style, terminology alignment, generic best practices, or a merely unusual statement.
Return no finding when the documents are internally consistent and no clear error exists.
"""
        if compliance_rules:
            user_prompt += f"\n\nIMPORTANT COMPLIANCE RULES TO CHECK AGAINST:\n{compliance_rules}\n"
            user_prompt += "\nEvaluate each compliance rule against the RAW SOURCE DOCUMENTS. Consider extracted claims only to identify concrete contradictions. Report violations and material contradictions; do not report mere alignment or terminology consistency."
        
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
            system_prompt=ANALYZE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_schema=AnalysisResult,
            max_output_tokens=8192,
            request_id=str(uuid.uuid4()),
            run_id=state.get("run_id"),
            node="analyze",
            purpose="compliance_and_conflict_analysis"
        )
        
        try:
            resp = llm.generate(req)
            
            # Update tokens
            state["total_tokens_used"] = state.get("total_tokens_used", 0) + (resp.input_tokens + resp.output_tokens)
            
            parsed = resp.parsed_content
            if parsed and hasattr(parsed, "findings"):
                run_id = uuid.UUID(state.get("run_id"))
                compliance_checks_total = state.get("compliance_checks_total", 0)
                compliance_checks_passed = state.get("compliance_checks_passed", 0)
                
                for f_info in parsed.findings:
                    # Findings must be grounded in this run's extracted claims or in a
                    # verbatim quote from a source chunk. An explicit missing-rule
                    # result is the one valid finding that has no positive evidence.
                    valid_cids = [cid for cid in getattr(f_info, "claim_ids", []) if cid in extracted_claim_ids]
                    new_claims_data = getattr(f_info, "new_claims", [])
                    quote_matches = []
                    for nc_data in new_claims_data:
                        quote = (nc_data.exact_quote or "").strip()
                        if not quote:
                            continue
                        candidates = [
                            chunk for chunk in chunk_objs
                            if (not nc_data.source_chunk_id or str(chunk.id) == nc_data.source_chunk_id)
                            and quote in chunk.text
                        ]
                        # A model-supplied ID must resolve to the exact quoted text.
                        # Without an ID, accept only an unambiguous single source.
                        if len(candidates) == 1:
                            quote_matches.append((nc_data, candidates[0]))

                    has_compliance_context = bool(compliance_rules and compliance_rules.strip())
                    is_missing_requirement = (
                        has_compliance_context
                        and any(
                            marker in f"{f_info.title} {f_info.summary}".lower()
                            for marker in ("missing", "absent", "not present")
                        )
                        and getattr(f_info, "severity", None) != "passed"
                        and not valid_cids
                        and not quote_matches
                    )
                    if not valid_cids and not quote_matches and not is_missing_requirement:
                        continue

                    compliance_checks_total += 1
                    if getattr(f_info, "severity", None) == "passed":
                        compliance_checks_passed += 1
                        
                    finding = Finding(
                        run_id=run_id,
                        title=f_info.title,
                        summary=f_info.summary,
                        severity=f_info.severity,
                        status="pending"
                    )
                    session.add(finding)
                    session.flush()
                    
                    # Link existing claims to finding
                    for cid in valid_cids:
                        claim = session.get(Claim, uuid.UUID(cid))
                        if claim:
                            finding.claims.append(claim)
                            
                    # Process new claims (e.g. evidence of absence)
                    seen_claims = set()
                    for nc_data, matched_chunk in quote_matches:
                        chunk_id_str = str(matched_chunk.id)
                        claim_sig = (nc_data.statement.strip().lower(), chunk_id_str)
                        if claim_sig in seen_claims:
                            continue
                        seen_claims.add(claim_sig)

                        new_claim = Claim(
                            run_id=run_id,
                            statement=nc_data.statement,
                            confidence=1.0,
                        )
                        session.add(new_claim)
                        session.flush()
                        finding.claims.append(new_claim)
                        
                        if matched_chunk:
                            evidence = ClaimEvidence(
                                claim_id=new_claim.id,
                                chunk_id=matched_chunk.id,
                                snippet=nc_data.exact_quote,
                                relevance=1.0
                            )
                            session.add(evidence)
                            
                    analyzed_finding_ids.append(str(finding.id))
                    
                # Update state with the counts
                state["compliance_checks_total"] = compliance_checks_total
                state["compliance_checks_passed"] = compliance_checks_passed
                    
            session.commit()
        except Exception as e:
            import traceback
            print(f"[ERROR] analyze_node failed: {e}")
            traceback.print_exc()
            session.rollback()
            return {
                "current_stage": "failed",
                "status": "failed",
                "errors": state.get("errors", []) + [f"LLM analysis failed: {str(e)}"]
            }

    return {
        "current_stage": NODE_VERIFY,
        "completed_stages": state.get("completed_stages", []) + [NODE_ANALYZE],
        "analyzed_finding_ids": analyzed_finding_ids,
        "analyzed_claim_ids": analyzed_claim_ids,
    }
