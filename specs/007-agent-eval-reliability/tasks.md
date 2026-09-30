# Tasks

- [x] Add reusable Fact extraction grounding validator
- [x] Add reusable Section draft grounding validator
- [x] Reject invalid Fact anchor references
- [x] Reject factual claims without Fact citations
- [x] Reject hallucinated Fact IDs
- [x] Add deterministic golden ESG eval cases
- [x] Add eval scoring CLI
- [x] Add CI eval threshold gate
- [x] Add validator regression tests
- [x] Add optional live LLM eval mode
- [x] Publish Agent Eval acceptance report

## Acceptance rule

Normal CI runs deterministic ESG Agent evaluation and requires:

```text
score >= 1.0
```

The deterministic suite includes both positive and negative golden cases. A negative case passes only
when the evaluator correctly rejects the unsafe output.

Live LLM evaluation remains opt-in because it depends on deployment-specific model endpoints,
credentials, model versions and latency:

```bash
uv run python scripts/run_evals.py --live
```

A green deterministic CI therefore proves the application-side AI quality contract, not the behavior
of every external model deployment.
