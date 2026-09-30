# Tasks

- [x] Define ESG scenario schema
- [x] Implement scenario evaluator
- [x] Add 10 domain scenarios
- [x] Add positive/negative calibration drafts
- [x] Add missing-data discipline checks
- [x] Add unsupported-assertion checks
- [x] Add real LLM scenario prompt builder
- [x] Add deterministic dataset runner
- [x] Add optional live dataset runner
- [x] Add unit/regression tests
- [x] Add CI gate
- [x] Publish acceptance report

## Deterministic acceptance

CI executes:

```bash
uv run python scripts/run_esg_scenario_evals.py --min-score 1.0
```

The score measures whether the evaluator correctly accepts every positive draft and rejects every
unsafe negative draft across the scenario dataset.

## Live model evaluation

Real model behavior remains explicit and environment-dependent:

```bash
uv run python scripts/run_esg_scenario_evals.py --live
```

Optional narrowing:

```bash
uv run python scripts/run_esg_scenario_evals.py --live --live-limit 3
```

The live run uses the configured OpenAI-compatible LLM endpoint and returns per-scenario findings.
