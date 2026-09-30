from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.ai.schemas import SectionDraft
from app.evals.quality import EvalFinding, EvalResult, numeric_faithfulness, validate_section_draft


class ScenarioFact(BaseModel):
    id: UUID
    name: str
    value: str | int | float | Decimal
    unit: str | None = None
    period: str | None = None
    entity_scope: str | None = None


class ScenarioExpectation(BaseModel):
    required_fact_ids: list[UUID] = Field(default_factory=list)
    prohibited_assertions: list[str] = Field(default_factory=list)
    allowed_context_numbers: list[str | int | float | Decimal] = Field(default_factory=list)


class ESGScenario(BaseModel):
    id: str
    topic: str
    section_title: str
    objective: str
    report_year: int
    facts: list[ScenarioFact]
    missing_items: list[str] = Field(default_factory=list)
    expectations: ScenarioExpectation = Field(default_factory=ScenarioExpectation)
    positive_draft: SectionDraft
    negative_drafts: list[SectionDraft] = Field(default_factory=list)


@dataclass(frozen=True)
class ScenarioEval:
    passed: bool
    score: float
    findings: tuple[EvalFinding, ...]
    metrics: dict[str, float]


def _contains_prohibited_assertion(text: str, prohibited: list[str]) -> list[str]:
    normalized = text.casefold()
    return [phrase for phrase in prohibited if phrase.casefold() in normalized]


def evaluate_scenario_draft(scenario: ESGScenario, draft: SectionDraft) -> ScenarioEval:
    allowed_fact_ids = {fact.id for fact in scenario.facts}
    grounding = validate_section_draft(draft, allowed_fact_ids)

    numeric_values: list[Any] = [fact.value for fact in scenario.facts]
    numeric_values.extend(scenario.expectations.allowed_context_numbers)
    numeric_values.append(scenario.report_year)
    numeric = numeric_faithfulness(draft, numeric_values)

    findings: list[EvalFinding] = [*grounding.findings, *numeric.findings]

    combined_text = "\n".join(
        [block.content for block in draft.blocks]
        + [claim.text for block in draft.blocks for claim in block.claims]
    )
    prohibited_hits = _contains_prohibited_assertion(
        combined_text,
        scenario.expectations.prohibited_assertions,
    )
    for phrase in prohibited_hits:
        findings.append(
            EvalFinding(
                "UNSUPPORTED_ASSERTION",
                f"Draft asserts information explicitly marked unsupported: {phrase}",
                "draft",
            )
        )

    cited_ids = {
        fact_id
        for block in draft.blocks
        for claim in block.claims
        if claim.claim_type.upper() in {"FACTUAL", "NUMERIC"}
        for fact_id in claim.fact_ids
    }
    required_ids = set(scenario.expectations.required_fact_ids)
    missing_required = required_ids - cited_ids
    if missing_required:
        findings.append(
            EvalFinding(
                "REQUIRED_FACT_NOT_USED",
                f"Draft omitted {len(missing_required)} required Fact(s)",
                "draft",
            )
        )

    assertion_score = 1.0 if not prohibited_hits else 0.0
    required_score = (
        1.0
        if not required_ids
        else (len(required_ids) - len(missing_required)) / len(required_ids)
    )
    metrics = {
        **grounding.metrics,
        **numeric.metrics,
        "unsupported_assertion_safety": assertion_score,
        "required_fact_coverage": required_score,
    }
    score = sum(metrics.values()) / len(metrics)
    return ScenarioEval(
        passed=not findings,
        score=score,
        findings=tuple(findings),
        metrics=metrics,
    )


def build_live_prompt(scenario: ESGScenario) -> tuple[str, str]:
    system = (
        "You are an enterprise ESG report writer. Use only the confirmed Facts supplied. "
        "Every factual or numeric claim must cite the exact supplied Fact IDs. "
        "Do not convert missing items into facts, achievements, policies or certifications. "
        "If information is missing, omit the unsupported assertion and list it in warnings."
    )
    facts = "\n".join(
        f"- Fact ID {fact.id}: {fact.name} = {fact.value} {fact.unit or ''}; "
        f"period={fact.period or scenario.report_year}; scope={fact.entity_scope or 'unspecified'}"
        for fact in scenario.facts
    )
    missing = "\n".join(f"- {item}" for item in scenario.missing_items) or "- none"
    user = (
        f"Topic: {scenario.topic}\n"
        f"Section title: {scenario.section_title}\n"
        f"Objective: {scenario.objective}\n"
        f"Report year: {scenario.report_year}\n\n"
        f"Confirmed Facts:\n{facts}\n\n"
        f"Known missing items:\n{missing}\n\n"
        "Return a SectionDraft with professional, objective ESG prose."
    )
    return system, user
