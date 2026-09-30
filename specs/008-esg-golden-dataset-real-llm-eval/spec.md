# ESG Golden Dataset + Real LLM Eval

## Intent
Move AI evaluation from synthetic unit-like examples to scenario-level ESG report production cases.

## Scope
- Environment, energy, GHG, water, waste, workforce, training, occupational health, supply chain and governance.
- Scenario context contains confirmed Facts, missing items, report year and section objective.
- Deterministic positive/negative drafts validate the evaluator itself.
- Optional live mode prompts the configured LLM with the exact scenario context and grades the returned SectionDraft.
- CI remains deterministic and credential-free.

## Acceptance criteria
1. At least 10 ESG domain scenarios exist.
2. Every scenario defines explicit confirmed Facts and explicit missing items.
3. Every factual/numeric Claim must cite only scenario Fact IDs.
4. Numbers outside Fact/context allowlists fail.
5. Claims containing scenario-defined unsupported assertions fail.
6. Expected missing items must not be silently converted into asserted facts.
7. Deterministic positive and negative drafts are both graded correctly.
8. CI requires aggregate deterministic score = 1.0.
9. Live mode produces per-scenario scores and a machine-readable summary without being required by normal CI.
10. Dataset and eval results are versioned and reproducible.
