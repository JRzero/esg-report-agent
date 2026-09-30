# ESG Report Agent - Agent Eval & Reliability Acceptance

Date: 2026-09-30  
Scope: Backend AI workflows and deterministic ESG output-quality gates. Frontend remains excluded.

## Result

**Agent Eval Deterministic Acceptance: PASS**

GitHub Actions Service CI run **36663764810** passed the complete backend gate.

Observed results:

- dependency consistency: PASS
- Ruff fatal/static checks: PASS
- Python compileall: PASS
- PostgreSQL migration from empty: PASS
- migration upgrade from accepted v1: PASS
- pytest: **32 passed**
- deterministic Agent Eval score: **1.0**
- performance smoke:
  - requests: 100
  - concurrency: 20
  - p50: **12.22 ms**
  - p95: **60.58 ms**
  - acceptance ceiling: 1000 ms
- service container build: PASS
- non-root container verification: PASS

The performance result is a CI regression guard, not a production capacity benchmark.

## Runtime AI quality gates

### Fact Extraction

AI Fact Extraction now fails closed when the model:

- emits a Fact without evidence anchors
- references an anchor not present in the source DocumentVersion
- references an anchor outside the supplied evidence context

Invalid model output raises:

```text
AI_OUTPUT_UNGROUNDED
```

No partial Fact set is silently accepted.

### Section Planning

A generated writing plan may only reference confirmed Facts supplied in the project context.

Hallucinated or cross-context Fact IDs cause the workflow to fail instead of persisting a misleading
plan.

### Section Writing

For claims classified as FACTUAL or NUMERIC:

- at least one Fact ID is required
- every referenced Fact ID must belong to the confirmed Fact set supplied to the model

If the rule is violated, the draft is rejected before ReportBlock persistence.

This prevents the previous failure mode where an unsupported claim could be persisted and merely
marked UNVERIFIED after the fact.

## Eval framework

Reusable evaluators are implemented in:

```text
service/app/evals/quality.py
```

Current deterministic metrics include:

- Fact grounding precision
- Claim grounding completeness
- Numeric faithfulness

Golden cases are stored in:

```text
service/evals/golden_cases.json
```

The dataset intentionally includes both valid and invalid outputs. CI succeeds only when the evaluator
accepts valid cases and rejects unsafe cases correctly.

## CI quality gate

CI executes:

```bash
uv run python scripts/run_evals.py --min-score 1.0
```

This makes ESG AI output quality part of the merge contract, alongside migrations, tests, performance
smoke and container checks.

## Optional live model eval

A live model can be tested explicitly with:

```bash
uv run python scripts/run_evals.py --live
```

This uses the configured OpenAI-compatible LLM endpoint.

Because model behavior can vary with provider, version, prompt implementation and credentials, live
model evaluation is not claimed by normal CI unless an actual endpoint is supplied.

## OpenViking

OpenViking runtime/deployment hardening was already accepted in Spec 006.

The existing live integration runner verifies:

- OpenViking readiness
- upload/import
- asynchronous task completion
- subsequent retrieval

with:

```bash
RUN_LIVE_INTEGRATIONS=true uv run python scripts/live_integrations.py
```

## Conclusion

After Spec 005, Spec 006 and Spec 007, the backend now has three distinct acceptance layers:

```text
Functional Service Acceptance
        +
Production Hardening
        +
Agent Output Quality / Eval
```

The remaining environment-dependent item is real deployment connectivity and behavior for the chosen
LLM/OpenViking endpoints. The application-side contracts are accepted.
