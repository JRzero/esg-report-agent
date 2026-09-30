from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.ai.llm import LLMGateway
from app.ai.schemas import SectionDraft
from app.evals.scenarios import ESGScenario, build_live_prompt, evaluate_scenario_draft


def load_scenarios(path: Path) -> list[ESGScenario]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [ESGScenario.model_validate(item) for item in payload["scenarios"]]


def deterministic_eval(scenarios: list[ESGScenario]) -> dict:
    rows = []
    matched = 0
    total = 0
    for scenario in scenarios:
        positive = evaluate_scenario_draft(scenario, scenario.positive_draft)
        positive_match = positive.passed
        matched += int(positive_match)
        total += 1
        rows.append(
            {
                "scenario": scenario.id,
                "variant": "positive",
                "expected_pass": True,
                "actual_pass": positive.passed,
                "matched": positive_match,
                "score": positive.score,
                "metrics": positive.metrics,
                "findings": [finding.__dict__ for finding in positive.findings],
            }
        )
        for index, draft in enumerate(scenario.negative_drafts):
            result = evaluate_scenario_draft(scenario, draft)
            row_match = not result.passed
            matched += int(row_match)
            total += 1
            rows.append(
                {
                    "scenario": scenario.id,
                    "variant": f"negative-{index + 1}",
                    "expected_pass": False,
                    "actual_pass": result.passed,
                    "matched": row_match,
                    "score": result.score,
                    "metrics": result.metrics,
                    "findings": [finding.__dict__ for finding in result.findings],
                }
            )
    score = matched / total if total else 1.0
    return {
        "score": score,
        "matched": matched,
        "total": total,
        "scenario_count": len(scenarios),
        "results": rows,
    }


async def live_eval(scenarios: list[ESGScenario], limit: int | None = None) -> dict:
    gateway = LLMGateway()
    rows = []
    selected = scenarios[:limit] if limit else scenarios
    for scenario in selected:
        system, user = build_live_prompt(scenario)
        draft = await gateway.generate_structured(system, user, SectionDraft, "STRONG")
        result = evaluate_scenario_draft(scenario, draft)
        rows.append(
            {
                "scenario": scenario.id,
                "passed": result.passed,
                "score": result.score,
                "metrics": result.metrics,
                "findings": [finding.__dict__ for finding in result.findings],
                "draft": draft.model_dump(mode="json"),
            }
        )
    aggregate = sum(row["score"] for row in rows) / len(rows) if rows else 1.0
    pass_rate = sum(int(row["passed"]) for row in rows) / len(rows) if rows else 1.0
    return {
        "score": aggregate,
        "pass_rate": pass_rate,
        "scenario_count": len(rows),
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        default=str(Path(__file__).resolve().parents[1] / "evals" / "esg_scenarios.json"),
    )
    parser.add_argument("--min-score", type=float, default=1.0)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--live-limit", type=int, default=None)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    scenarios = load_scenarios(Path(args.dataset))
    deterministic = deterministic_eval(scenarios)
    payload: dict = {"deterministic": deterministic}

    if args.live:
        payload["live"] = asyncio.run(live_eval(scenarios, args.live_limit))

    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")

    if deterministic["score"] < args.min_score:
        raise SystemExit(
            f"Scenario eval score {deterministic['score']:.3f} < required {args.min_score:.3f}"
        )
    if args.live and payload["live"]["pass_rate"] < 1.0:
        raise SystemExit("One or more live ESG scenarios failed grounding requirements")


if __name__ == "__main__":
    main()
