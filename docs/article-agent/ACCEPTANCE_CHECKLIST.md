# Hard Acceptance Checklist

## Planner
- [x] full budget before first LLM call
- [x] every section allocated
- [x] conclusion allocated
- [x] FAQ allocated
- [x] common_mistakes allocated
- [x] applications allocated
- [x] target sum equals requested total
- [x] min/max feasibility proven
- [ ] remaining-budget invariant enforced
- [x] plan persisted first

## Runtime budget
- [ ] canonical semantic word counter
- [ ] Persian/Unicode tests
- [ ] FAQ counted semantically
- [ ] no dict/string counting
- [ ] short output repaired
- [ ] long output compressed
- [ ] impossible output fails safely
- [ ] edits revalidate budget
- [ ] per-unit final accounting

## Context/memory
- [ ] structured bounded memory
- [ ] relevance selection
- [ ] field-aware compaction
- [ ] valid JSON always
- [ ] large article tests

## Research
- [ ] explicit mode
- [ ] no fake research
- [ ] real provider when enabled
- [ ] provenance
- [ ] failure policy

## Review/revision
- [ ] section reviewer sees real draft
- [ ] article reviewer sees bounded real prose
- [ ] repetition/contradiction/transition checks
- [ ] findings identify affected units
- [ ] targeted revision
- [ ] targeted final editing
- [ ] re-review after edits

## Natural writing
- [ ] generic openings/transitions detected
- [ ] repeated phrases/structures detected
- [ ] sentence/paragraph variation measured
- [ ] template language measured
- [ ] keyword stuffing measured
- [ ] style editor implemented
- [ ] no detector-evasion objective

## Rate limiting
- [ ] Redis distributed coordination
- [ ] concurrency protection
- [ ] request/token reservation where possible
- [ ] Retry-After
- [ ] jittered backoff
- [ ] bounded retries
- [ ] concurrency tests

## Jobs
- [ ] explicit state transitions
- [ ] duplicate task safe
- [ ] durable checkpoints
- [ ] resume after mid-pipeline failure
- [ ] render failure does not regenerate prose
- [ ] cancellation race safe
- [ ] user retry distinct from provider retry
- [ ] stale task cannot overwrite newer retry

## Quality
- [ ] headings preserved/unique
- [ ] no empty required unit
- [ ] FAQ exactly 4
- [ ] extras present
- [ ] all budgets valid
- [ ] critical findings block completion
- [ ] failed reviews block completion
- [ ] research requirements pass
- [ ] normalized keyword validation
- [ ] final report persisted

## DOCX/UI/Security
- [ ] real valid DOCX
- [ ] title/headings/order
- [ ] bold headings
- [ ] Persian RTL
- [ ] B Nazanin configured
- [ ] FAQ/extras
- [ ] Unicode
- [ ] polished dashboard UI
- [ ] responsive/modal/validation
- [ ] live status/progress
- [ ] cancel/retry/download
- [ ] loading/error/empty/accessibility
- [ ] no silent production secret
- [ ] ownership/file authorization
- [ ] CSRF/security headers
- [ ] no secret leakage
- [ ] reproducible dependencies
- [ ] clean migrations

## Verification
- [ ] Django checks
- [ ] migrations checks
- [ ] full tests
- [ ] lint/type checks available
- [ ] real provider smoke
- [ ] 5k article
- [ ] 10k article
- [ ] cancellation
- [ ] retry
- [ ] resume
- [ ] concurrent jobs
- [ ] DOCX open/read
- [ ] no P0/P1
