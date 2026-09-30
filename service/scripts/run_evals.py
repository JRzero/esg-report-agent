from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID

from app.ai.llm import LLMGateway
from app.ai.schemas import SectionDraft
from app.evals.quality import numeric_faithfulness, validate_section_draft


def deterministic_eval(dataset: Path) -> dict:
    payload = json.loads(dataset.read_text(encoding="utf-8"))
    rows = []
    correct = 0
    for case in payload["cases"]:
        draft = SectionDraft.model_validate(case["draft"])
        grounding = validate_section_draft(
            draft,
            {UUID(value) for value in case["allowed_fact_ids"]},
        )
        numeric = numeric_faithfulness(draft, case.get("allowed_numeric_values", []))
        actual_pass = grounding.passed and numeric.passed
        expected_pass = bool(case["expect_pass"])
        matched = actual_pass == expected_pass
        correct += int(matched)
        rows.append(
            {
                "id": case["id"],
                "expected_pass": expected_pass,
                "actual_pass": actual_pass,
                "matched": matched,
                "grounding": grounding.metrics,
                "numeric": numeric.metrics,
                "findings": [
                    finding.__dict__
                    for finding in (*grounding.findings, *numeric.findings)
                ],
            }
        )
    score = correct / len(rows) if rows else 1.0
    return {"score": score, "cases": rows, "count": len(rows)}


async def live_eval() -> dict:
    class LiveResult(SectionDraft):
        pass

    prompt = (
        "Use no invented facts. Return one paragraph and one FACTUAL claim using only this fact: "
        "Fact ID 11111111-1111-1111-1111-111111111111, employee total 1287 people in 2026."
    )
    draft = await LLMGateway().generate_structured(
        "You are an ESG report writer. Factual claims must cite supplied Fact IDs.",
        prompt,
        LiveResult,
    )
    grounding = validate_section_draft(
        draft,
        {UUID("11111111-1111-1111-1111-111111111111")},
    )
    numeric = numeric_faithfulness(draft, [1287, 2026])
    return {
        "passed": grounding.passed and numeric.passed,
        "grounding": grounding.metrics,
        "numeric": numeric.metrics,
        "findings": [
            finding.__dict__ for finding in (*grounding.findings, *numeric.findings)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        default=str(Path(__file__).resolve().parents[1] / "evals" / "golden_cases.json"),
    )
    parser.add_argument("--min-score", type=float, default=1.0)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    result = deterministic_eval(Path(args.dataset))
    print(json.dumps({"deterministic": result}, ensure_ascii=False, indent=2))
    if result["score"] < args.min_score:
        raise SystemExit(
            f"Deterministic eval score {result['score']:.3f} < required {args.min_score:.3f}"
        )

    if args.live:
        live = asyncio.run(live_eval())
        print(json.dumps({"live": live}, ensure_ascii=False, indent=2))
        if not live["passed"]:
            raise SystemExit("Live LLM eval failed")


if __name__ == "__main__":
    main()
