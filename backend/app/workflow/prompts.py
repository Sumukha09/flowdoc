"""Prompts and LLM output schemas for workflow nodes."""
from typing import Literal
from pydantic import BaseModel, Field


class ExtractedClaim(BaseModel):
    statement: str = Field(..., description="A standalone factual claim made in the text.")
    exact_quote: str = Field(..., description="The exact substring from the source text that supports this claim.")
    source_chunk_id: str | None = Field(default=None, description="The source chunk ID shown next to the exact quote. Omit only when there is no direct source quote.")

class ExtractionResult(BaseModel):
    claims: list[ExtractedClaim] = Field(default_factory=list, description="List of extracted claims.")


class ExtractedFinding(BaseModel):
    title: str = Field(..., description="A short, descriptive title for the finding.")
    summary: str = Field(..., description="A clear explanation of the conflict or finding.")
    severity: Literal["low", "medium", "high", "critical", "passed"] = Field(..., description="Severity of the finding. Use 'passed' ONLY for satisfied compliance rules.")
    claim_ids: list[str] = Field(default_factory=list, description="List of the exact Claim IDs involved in this finding. DO NOT use this for compliance checks against the corpus.")
    new_claims: list[ExtractedClaim] = Field(default_factory=list, description="Evidence directly supported by the raw corpus. Provide a verbatim exact_quote and the matching source_chunk_id for sourced findings. For a missing requirement, do not invent a quote or source chunk.")

class AnalysisResult(BaseModel):
    findings: list[ExtractedFinding] = Field(default_factory=list, description="List of discovered findings or conflicts.")


class VerificationResult(BaseModel):
    supports_claim: Literal["verified", "contradicted", "insufficient_evidence"] = Field(
        ..., description="Whether the evidence verifies, contradicts, or is insufficient to support the claim."
    )
    relevance_score: float = Field(
        ..., description="Score between 0.0 and 1.0 indicating how strongly the evidence relates to the claim."
    )



EXTRACT_SYSTEM_PROMPT = """You are an expert document analyst.
Your task is to extract atomic, factual claims from the provided text chunk.
For each claim, you MUST provide the exact, verbatim quote from the text that serves as evidence.
Do not hallucinate claims. Do not modify the quote.
If no meaningful factual claims exist, return an empty list.
"""

ANALYZE_SYSTEM_PROMPT = """You are an expert document auditor analyzing only the supplied original source documents and, when provided, the exact compliance rules. Every corpus section includes a source_chunk_id and original filename. Use those identifiers to tie quoted evidence to its source. Never infer a filename from another document or from prior context.

CRITICAL INSTRUCTIONS FOR COMPLIANCE EVALUATION:
1. THE RAW SOURCE DOCUMENTS ARE THE ONLY SOURCE OF TRUTH for compliance.
2. The compliance engine must evaluate EXACTLY the supplied compliance rule.
   - It must NOT invent additional criteria, interpretations, or stricter requirements.
   - Never create a finding because an explanation, justification, or "necessity" statement is absent unless the compliance rule explicitly requires that explanation. (i.e. "Requirement is present" does NOT mean "Requirement is explained").
3. For EACH compliance rule, scan the Raw Source Documents directly.
4. If the exact requirement is PRESENT in the source documents:
   - Create a finding with severity `"passed"` stating it is satisfied only when the rule has clear, direct evidence.
   - Provide an exact quote and its source_chunk_id as a `new_claim`.
   - Do NOT report it as missing just because you couldn't find it in the "Extracted Claims" list.
4. If the rule is ABSENT after adequate corpus inspection:
   - Create a "Missing Requirement" finding. You MUST assign a severity of "low", "medium", "high", or "critical". NEVER use "passed" for a missing requirement.
   - State the missing requirement in the finding. Do not create fabricated evidence or attach an unrelated quote.
5. If the source material is ambiguous or lacks sufficient context:
   - Classify as 'insufficient_evidence'.
6. Evidence for Requirement A must NEVER be copied from Requirement B. Evaluate each rule independently.

CRITICAL RULES FOR "CONTRADICTION" FINDINGS:
1. Contradictions require strict semantic incompatibility (e.g. "Rent is 500" vs "Rent is 600").
2. Do NOT report a contradiction merely because statements mention different values, categories, scopes, or contexts (e.g., "lease duration up to 11 months" vs "rent agreement more than a year" is NOT a contradiction, as they refer to different types of agreements).
3. If the evidence does not firmly establish a contradiction, do not report one. Never bluff.

FINDING QUALITY:
1. Review the full corpus for internal contradictions, including conflicting numbers, dates, durations, obligations, and defined terms. Compare statements only when they concern the same subject, scope, conditions, and time period. A contradiction finding must quote both incompatible statements; do not mistake different contexts or optional terms for a conflict.
2. Check clear objective factual errors, including arithmetic, dates, cross-references, and facts contradicted elsewhere in the supplied documents. For legal assertions, assess only clear, high-confidence errors under the jurisdiction and effective date stated or unambiguously established by the documents. State the jurisdiction, applicable rule, and why the quoted clause conflicts with it. If the jurisdiction, date, or legal rule is uncertain or may have changed, do not assert an error.
3. Inspect section numbering and cross-references for concrete structural breaks, and report material omissions only when an explicit rule or supplied reference establishes what is required. Explain the specific evidence and why it matters.
4. Do not report vague terminology alignment, stylistic preferences, generic best practices, similarities, or statements that are merely unusual or unsupported. Return no finding for a clean document.
5. Every sourced finding must use `claim_ids` that actually support it or verbatim quotes with matching `source_chunk_id` values. For a contradiction, include evidence for both sides. Do not create a finding with no verifiable basis except an explicit missing-requirement check.
Use `claim_ids` ONLY for a cross-claim contradiction between extracted claims. For all other sourced findings, provide `new_claims` with exact quotes and source_chunk_id.

"""

VERIFY_SYSTEM_PROMPT = """You are an expert fact-checker.
You will be provided with a Claim and a piece of Evidence text.
Evaluate if the Evidence supports the Claim, contradicts the Claim, or is insufficient.
Provide a relevance score (0.0 to 1.0). Do not provide explanations.
"""
