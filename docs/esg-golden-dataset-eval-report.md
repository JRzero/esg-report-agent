# ESG Golden Dataset + Real LLM Eval Acceptance Report

Date: 2026-09-30  
Scope: Backend ESG Agent evaluation. Frontend remains excluded.

## Result

**Scenario-level deterministic ESG evaluation: PASS**

GitHub Actions Service CI run **36666179965** passed all configured service gates.

Observed results:

- dependency consistency: PASS
- Ruff fatal/static checks: PASS
- Python compileall: PASS
- PostgreSQL migration from empty: PASS
- migration upgrade from accepted v1: PASS
- pytest: **37 passed**
- base Agent Eval score: **1.0**
- ESG scenario calibration score: **1.0**
- ESG scenario count: **10**
- performance smoke:
  - requests: 100
  - concurrency: 20
  - p50: **14.26 ms**
  - p95: **67.98 ms**
  - acceptance ceiling: 1000 ms
- service container build: PASS
- non-root container runtime: PASS

The performance figures are regression guards for CI, not production capacity claims.

## Dataset

Versioned dataset:

```text
service/evals/esg_scenarios.json
```

Current domains:

1. workforce
2. greenhouse gas emissions
3. energy
4. water
5. waste
6. employee training
7. occupational health and safety
8. supply chain
9. governance / anti-corruption
10. community investment

Every scenario contains:

```text
section objective
+ confirmed Facts
+ known missing items
+ required Fact coverage
+ prohibited unsupported assertions
+ allowed contextual numbers
+ positive draft
+ unsafe negative draft(s)
```

## Evaluation dimensions

### Fact grounding

Every factual or numeric Claim must reference only confirmed Fact IDs supplied to the scenario.

### Numeric faithfulness

Numbers appearing in generated prose must come from:

- confirmed scenario Fact values
- explicitly allowed contextual numbers
- report year

Numbers invented by the draft produce an `UNSUPPORTED_NUMBER` finding.

### Missing-data discipline

Missing items are explicit scenario context. The model is instructed to omit unsupported assertions
and surface gaps in warnings rather than fill them with plausible-sounding content.

### Unsupported assertions

Each scenario may define high-risk unsupported statements. If they appear in generated content, the
draft fails with `UNSUPPORTED_ASSERTION`.

### Required Fact coverage

Scenarios may require key Facts to be represented in the section. Omission produces
`REQUIRED_FACT_NOT_USED`.

## Calibration model

The deterministic dataset contains both safe and unsafe examples.

A positive example passes only when all quality checks pass.

A negative example is considered correctly evaluated only when the evaluator rejects it.

Therefore a deterministic aggregate score of 1.0 means:

> all positive examples were accepted and all unsafe examples were rejected.

It does not mean that an external LLM has perfect ESG writing quality.

## Real LLM evaluation

The same scenarios can be sent to the configured OpenAI-compatible model:

```bash
uv run python scripts/run_esg_scenario_evals.py --live
```

For faster smoke testing:

```bash
uv run python scripts/run_esg_scenario_evals.py --live --live-limit 3
```

Optional result artifact:

```bash
uv run python scripts/run_esg_scenario_evals.py --live --output live-eval.json
```

The runner returns:

- per-scenario pass/fail
- aggregate score
- pass rate
- grounding metrics
- numeric faithfulness
- unsupported assertion findings
- generated SectionDraft

Real-model results are deliberately not claimed by CI unless the actual deployment endpoint and
credentials are supplied.

## Important interpretation

The backend now has four acceptance layers:

```text
Spec 005  Functional Service Acceptance
Spec 006  Production Hardening
Spec 007  Agent Output Grounding
Spec 008  Scenario-level ESG Golden Dataset
```

This moves the project from merely testing whether the system can call an LLM to testing whether the
LLM output stays inside enterprise ESG evidence boundaries.

## Next dataset evolution

Future datasets should be sourced from anonymized real consulting projects and expanded with:

- multi-document conflicting evidence
- bilingual Chinese/English reporting
- qualitative policy/process disclosures
- multi-year trend narratives
- entity/subsidiary scope differences
- unit conversion cases
- GRI disclosure-specific expectations
- human consultant scoring

Those are dataset-growth tasks, not blockers for the current backend contract.
