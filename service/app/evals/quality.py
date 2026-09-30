from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from app.ai.schemas import FactExtractionResult, SectionDraft


@dataclass(frozen=True)
class EvalFinding:
    code: str
    message: str
    path: str


@dataclass(frozen=True)
class EvalResult:
    passed: bool
    score: float
    findings: tuple[EvalFinding, ...]
    metrics: dict[str, float]


def validate_fact_extraction(
    result: FactExtractionResult,
    allowed_anchor_ids: set[UUID],
) -> EvalResult:
    findings: list[EvalFinding] = []
    total = len(result.facts)
    grounded = 0
    for index, fact in enumerate(result.facts):
        path = f"facts[{index}]"
        ids = set(fact.anchor_ids)
        if not ids:
            findings.append(EvalFinding("FACT_WITHOUT_EVIDENCE", "Fact has no evidence anchor", path))
            continue
        foreign = ids - allowed_anchor_ids
        if foreign:
            findings.append(
                EvalFinding(
                    "UNKNOWN_EVIDENCE_ANCHOR",
                    f"Fact references {len(foreign)} unknown evidence anchor(s)",
                    path,
                )
            )
            continue
        grounded += 1
    precision = 1.0 if total == 0 else grounded / total
    return EvalResult(
        passed=not findings,
        score=precision,
        findings=tuple(findings),
        metrics={"fact_grounding_precision": precision},
    )


def validate_section_draft(
    draft: SectionDraft,
    allowed_fact_ids: set[UUID],
) -> EvalResult:
    findings: list[EvalFinding] = []
    factual_claims = 0
    grounded_claims = 0

    for block_index, block in enumerate(draft.blocks):
        for claim_index, claim in enumerate(block.claims):
            path = f"blocks[{block_index}].claims[{claim_index}]"
            if claim.claim_type.upper() not in {"FACTUAL", "NUMERIC"}:
                continue
            factual_claims += 1
            ids = set(claim.fact_ids)
            if not ids:
                findings.append(
                    EvalFinding(
                        "FACTUAL_CLAIM_WITHOUT_FACT",
                        "Factual claim must cite at least one confirmed Fact",
                        path,
                    )
                )
                continue
            unknown = ids - allowed_fact_ids
            if unknown:
                findings.append(
                    EvalFinding(
                        "UNKNOWN_FACT_REFERENCE",
                        f"Claim references {len(unknown)} Fact(s) outside the confirmed Fact context",
                        path,
                    )
                )
                continue
            grounded_claims += 1

    completeness = 1.0 if factual_claims == 0 else grounded_claims / factual_claims
    return EvalResult(
        passed=not findings,
        score=completeness,
        findings=tuple(findings),
        metrics={"claim_grounding_completeness": completeness},
    )


def numeric_tokens(text: str) -> set[str]:
    return set(re.findall(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?%?", text))


def normalized_number(value: Decimal | int | float | str) -> set[str]:
    raw = str(value)
    variants = {raw}
    try:
        number = Decimal(raw.replace(",", ""))
        variants.add(format(number, "f").rstrip("0").rstrip(".") if "." in format(number, "f") else format(number, "f"))
        if number == number.to_integral():
            integer = int(number)
            variants.add(str(integer))
            variants.add(f"{integer:,}")
    except Exception:
        pass
    return {item for item in variants if item}


def numeric_faithfulness(
    draft: SectionDraft,
    allowed_numeric_values: Iterable[Decimal | int | float | str],
) -> EvalResult:
    allowed: set[str] = set()
    for value in allowed_numeric_values:
        allowed.update(normalized_number(value))

    findings: list[EvalFinding] = []
    found = 0
    supported = 0
    for block_index, block in enumerate(draft.blocks):
        for token in numeric_tokens(block.content):
            found += 1
            if token in allowed:
                supported += 1
            else:
                findings.append(
                    EvalFinding(
                        "UNSUPPORTED_NUMBER",
                        f"Numeric token {token} is not present in the allowed Fact values",
                        f"blocks[{block_index}].content",
                    )
                )
    score = 1.0 if found == 0 else supported / found
    return EvalResult(
        passed=not findings,
        score=score,
        findings=tuple(findings),
        metrics={"numeric_faithfulness": score},
    )
