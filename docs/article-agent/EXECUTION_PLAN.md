# Execution Plan

Mark `DONE` only after evidence.

## M0 Baseline
- [x] inspect repository and all article-agent paths
- [x] identify every production execution path
- [x] run baseline tests/checks

## M1 Full budget planner
- [x] ArticleBudget/Allocation
- [x] complete allocation for all sections + conclusion + FAQ + common_mistakes + applications
- [x] mathematical feasibility invariants
- [x] deterministic rounding
- [x] persist before generation
- [x] tests for 500/1000/5000/10000/20000 words and varied heading counts

## M2 Runtime budget
- [ ] canonical WordCounter
- [ ] BudgetManager
- [ ] reserve/generate/measure/repair/commit
- [ ] short/long/impossible output tests
- [ ] final per-unit accounting

## M3 Durable/idempotent execution
- [ ] persist checkpoints
- [ ] execution/task versioning
- [ ] duplicate-task protection
- [ ] resume after mid-pipeline failure
- [ ] render failure resumes without regenerating article

## M4 Context/memory
- [ ] structured memory expansion
- [ ] relevance selection
- [ ] field-level compaction
- [ ] large article/context tests

## M5 Research
- [ ] explicit modes
- [ ] real provider when enabled
- [ ] provenance
- [ ] failure policy
- [ ] disabled mode is explicit

## M6 Section review/revision
- [ ] strict schema
- [ ] budget-aware review
- [ ] targeted revision
- [ ] re-review

## M7 Article review
- [ ] bounded real-prose review context
- [ ] repetition/contradiction/transitions/coverage
- [ ] affected-unit findings
- [ ] extras review

## M8 Natural writing
- [ ] deterministic style analyzer
- [ ] LLM style review
- [ ] targeted style editor
- [ ] regression fixtures

## M9 Selective final editor
- [ ] affected units only
- [ ] re-review
- [ ] budget preservation

## M10 Redis/Groq limiter
- [ ] distributed request/concurrency coordination
- [ ] token reservation/estimation where possible
- [ ] Retry-After
- [ ] exponential backoff + jitter
- [ ] concurrency tests

## M11 Quality gate
- [ ] all invariants
- [ ] FAQ exactly 4
- [ ] semantic counting
- [ ] normalized keyword validation
- [ ] critical finding handling

## M12 Job lifecycle
- [ ] state transition rules
- [ ] cancellation races
- [ ] user vs provider retry
- [ ] stale-task protection

## M13 DOCX
- [ ] RTL
- [ ] B Nazanin
- [ ] title/headings/FAQ/extras
- [ ] Unicode/open verification

## M14 UI
- [ ] dashboard integration
- [ ] polished responsive UI
- [ ] modal/validation
- [ ] live status/progress
- [ ] cancel/retry/download
- [ ] loading/error/empty/accessibility

## M15 Production hardening
- [ ] required production secret
- [ ] dependencies reproducible
- [ ] security settings
- [ ] migrations
- [ ] logging/observability

## M16 Adversarial verification
- [ ] empty provider output
- [ ] malformed JSON
- [ ] over/under budget
- [ ] repeated/contradictory prose
- [ ] timeout/429
- [ ] cancellation race
- [ ] duplicate task
- [ ] renderer failure
- [ ] research unavailable

## M17 Final verification
- [ ] Django checks/migrations
- [ ] full test suite
- [ ] lint/type checks available
- [ ] real provider smoke
- [ ] 5k and 10k article
- [ ] cancellation/retry/resume
- [ ] concurrent jobs/rate limit
- [ ] DOCX open/read
- [ ] zero P0/P1
