from __future__ import annotations

import json
from pathlib import Path

from app.evals.scenarios import ESGScenario, build_live_prompt, evaluate_scenario_draft
from scripts.run_esg_scenario_evals import deterministic_eval


DATASET = Path(__file__).resolve().parents[1] / "evals" / "esg_scenarios.json"


def _scenarios() -> list[ESGScenario]:
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    return [ESGScenario.model_validate(item) for item in payload["scenarios"]]


def test_dataset_contains_ten_esg_domains():
    scenarios = _scenarios()
    assert len(scenarios) >= 10
    topics = {scenario.topic for scenario in scenarios}
    assert {
        "workforce",
        "ghg",
        "energy",
        "water",
        "waste",
        "training",
        "occupational_health",
        "supply_chain",
        "governance",
        "community",
    }.issubset(topics)


def test_every_scenario_has_facts_and_missing_items():
    for scenario in _scenarios():
        assert scenario.facts, scenario.id
        assert scenario.missing_items, scenario.id


def test_positive_drafts_pass_and_negative_drafts_fail():
    for scenario in _scenarios():
        positive = evaluate_scenario_draft(scenario, scenario.positive_draft)
        assert positive.passed, (scenario.id, positive.findings)
        for draft in scenario.negative_drafts:
            negative = evaluate_scenario_draft(scenario, draft)
            assert not negative.passed, scenario.id


def test_deterministic_dataset_score_is_perfect():
    result = deterministic_eval(_scenarios())
    assert result["score"] == 1.0
    assert result["scenario_count"] >= 10
    assert result["total"] >= 20


def test_live_prompt_exposes_facts_and_missing_items():
    scenario = _scenarios()[0]
    system, user = build_live_prompt(scenario)
    assert "Every factual or numeric claim must cite" in system
    assert str(scenario.facts[0].id) in user
    assert scenario.missing_items[0] in user
