# Agent Eval & Reliability

## Intent
Add a measurable quality gate for ESG AI outputs before frontend work begins.

## Acceptance criteria
- Fact extraction output is rejected when emitted facts reference missing/foreign anchors.
- Section writing output is rejected when factual claims have no confirmed Fact IDs.
- Section writing output is rejected when claims reference Facts outside the allowed confirmed Fact set.
- Deterministic eval cases measure fact grounding, claim grounding, citation completeness and hallucinated references.
- CI fails when the deterministic eval score falls below the configured threshold.
- A live eval mode can call the configured LLM without being required by normal CI.
- OpenViking/LLM deployment smoke remains explicit and environment-dependent.
