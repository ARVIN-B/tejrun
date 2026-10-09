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
- [x] canonical WordCounter
- [x] BudgetManager
- [x] reserve/generate/measure/repair/commit
- [x] short/long/impossible output tests
- [x] final per-unit accounting

## M3 Durable/idempotent execution
- [x] persist checkpoints
- [x] execution/task versioning
- [x] duplicate-task protection
- [x] resume after mid-pipeline failure
- [x] render failure resumes without regenerating article

## M4 Context/memory
- [x] structured memory expansion
- [x] relevance selection
- [x] field-level compaction
- [ ] large article/context tests

## M5 Research
- [x] explicit modes
- [x] real provider when enabled
- [x] provenance
- [x] failure policy
- [x] disabled mode is explicit

## M6 Section review/revision
- [x] strict schema
- [x] budget-aware review
- [x] targeted revision
- [x] re-review

## M7 Article review
- [x] bounded real-prose review context
- [x] repetition/contradiction/transitions/coverage
- [x] affected-unit findings
- [x] extras review

## M8 Natural writing
- [ ] deterministic style analyzer
- [ ] LLM style review
- [ ] targeted style editor
- [ ] regression fixtures

## M9 Selective final editor
- [x] affected units only
- [x] re-review
- [x] budget preservation

## M10 Redis/Groq limiter
- [x] distributed request/concurrency coordination
- [x] token reservation/estimation where possible
- [x] Retry-After
- [x] exponential backoff + jitter
- [x] concurrency tests

## M11 Quality gate
- [x] all invariants
- [x] FAQ exactly 4
- [x] semantic counting
- [x] normalized keyword validation
- [x] critical finding handling

## M12 Job lifecycle
- [ ] state transition rules
- [ ] cancellation races
- [ ] user vs provider retry
- [ ] stale-task protection

## M13 DOCX
- [x] RTL
- [x] B Nazanin
- [x] title/headings/FAQ/extras
- [x] Unicode/open verification

## M14 UI
- [x] dashboard integration
- [x] polished responsive UI
- [x] modal/validation
- [x] live status/progress
- [x] cancel/retry/download
- [x] loading/error/empty/accessibility

## M15 Production hardening
- [x] required production secret
- [ ] dependencies reproducible
- [x] security settings
- [x] migrations
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
