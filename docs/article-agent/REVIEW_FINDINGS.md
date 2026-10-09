# Review Findings — Article Agent

Every item must be fixed or disproven by code/tests. Similar class names do not count as implementation.

## Resolved P0

### Environment template contained usable credentials
`.env.example` is a public configuration template, not a secret store. It now
contains placeholders only, and `EnvironmentTemplateTests` prevents sensitive
settings from acquiring usable values again.

## Resolved P1

### Coarse Groq token reservation produced false internal exhaustion
The prior limiter reserved the global output maximum for every request, used a
single undifferentiated quota key and returned the request-counter TTL for all
rejections. It could therefore reject section repair locally without a Groq
HTTP 429. The limiter now reserves per-operation output capacity, enforces
account plus optional model quotas atomically, distinguishes causes, uses
active leases for concurrency retry timing and reconciles successful calls
with provider usage. Unit tests cover quota dimensions, shared coordination,
fallback bounds, 429 distinction and cleanup; real Redis/Groq verification is
still required per deployment.

### Empty provider completions were misclassified as budget failures
`GroqClient` previously converted any completion payload to a string, allowing
empty/whitespace output to reach the writer and eventually become
`unit_budget_unsatisfied:...:0`. Empty non-text responses now receive one
bounded provider-call retry and then become `ProviderEmptyResponseError`, a
retryable provider failure. The zero-word BudgetManager rejection remains in
place for non-provider/fake-generator callers and regression tests cover both
behaviours.

## P0 confirmed

### 1. Full article budget is not planned
Current planner uses a body ratio and does not explicitly allocate conclusion, FAQ, common_mistakes and applications.

Required invariant:
`sum(target_words for every required unit) == requested_total_words`

Also:
- sum(minimums) <= total
- sum(maximums) >= total
- before generating unit N: remaining budget >= minimums of all remaining units
- plan persisted before first generation

### 2. Runtime budget is not enforced
A target in the plan is not enforcement. Provider output must be semantically counted and repaired if short/long, then accepted only inside its bounds. Final edits must revalidate budgets.

### 3. Article review does not receive enough article prose
Current article reviewer mostly sees plan, memory, scores and presence flags. That cannot reliably detect repetition, contradiction, transitions or conclusion coherence.

### 4. Research is effectively a no-op
`GroundingResearcher` returns empty data with confidence 0. This must become a real provider or explicit disabled/no-research mode. Never present empty data as successful research.

### 5. Natural writing layer is missing
`StyleProfile` is descriptive only. Implement deterministic style metrics plus reviewer/editor: generic openings/transitions, repeated phrases/structures, sentence/paragraph variation, template language, keyword stuffing, repetition.

Goal is genuinely natural writing, never detector evasion.

### 6. Final editor over-edits
Current behavior can edit every section when any final-review fix exists. Findings must identify affected units; edit only those and re-review them.

### 7. Context compaction can discard critical data
Use field-level compaction priorities. Never slice JSON strings. Preserve task, invariants, current unit and budget before optional memory/research/prose.

### 8. Resume/idempotency is incomplete
Persist durable checkpoints for plan/budget/research/unit review/edit/final state. Duplicate task execution must be safe. Render failure must resume without regenerating article prose.

### 9. Distributed Groq limiting is absent
Celery retry/backoff is not a distributed limiter. Add Redis coordination for concurrency and request/token reservation where possible, Retry-After, exponential backoff + jitter, bounded retry and tests.

### 10. UI is still basic
`create_article.html` is minimal inline HTML. Replace with dashboard-integrated responsive UI: modal, validation, live progress, stage/current section, cancel/retry/download, loading/error/empty/accessibility states.

## Additional investigation targets
- duplicate task race
- cancellation race
- stale retry task overwriting a newer retry
- provider timeout/cancellation
- malformed LLM JSON / empty output
- partial output and renderer failure
- output file replacement/cleanup
- connection lifecycle
- production SECRET_KEY fallback
- dependency reproducibility
- security headers/hosts
- 10k/20k article behavior
- Persian/Unicode word counting
- keyword normalization
- FAQ schema/cardinality
- progress monotonicity
- retry-count semantics
- stale result_payload
- file authorization
- logging/observability
- legacy execution paths
