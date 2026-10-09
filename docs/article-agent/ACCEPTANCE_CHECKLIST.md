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
- [x] remaining-budget invariant enforced
- [x] plan persisted first

## Runtime budget
- [x] canonical semantic word counter
- [x] Persian/Unicode tests
- [x] FAQ counted semantically
- [x] no dict/string counting
- [x] short output repaired
- [x] long output compressed
- [x] impossible output fails safely
- [x] edits revalidate budget
- [x] per-unit final accounting

## Context/memory
- [ ] structured bounded memory
- [ ] relevance selection
- [ ] field-aware compaction
- [ ] valid JSON always
- [ ] large article tests

## Research
- [x] explicit mode
- [x] no fake research
- [x] real provider when enabled
- [x] provenance
- [x] failure policy

## Review/revision
- [x] section reviewer sees real draft
- [x] article reviewer sees bounded real prose
- [x] repetition/contradiction/transition checks
- [x] findings identify affected units
- [x] targeted revision
- [x] targeted final editing
- [x] re-review after edits

## Natural writing
- [ ] generic openings/transitions detected
- [ ] repeated phrases/structures detected
- [ ] sentence/paragraph variation measured
- [ ] template language measured
- [ ] keyword stuffing measured
- [ ] style editor implemented
- [ ] no detector-evasion objective

## Rate limiting
- [x] Redis distributed coordination
- [x] concurrency protection
- [x] request/token reservation where possible
- [x] Retry-After
- [x] jittered backoff
- [x] bounded retries
- [x] concurrency tests

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
- [x] headings preserved/unique
- [x] no empty required unit
- [x] FAQ exactly 4
- [x] extras present
- [x] all budgets valid
- [x] critical findings block completion
- [x] failed reviews block completion
- [x] research requirements pass
- [x] normalized keyword validation
- [x] final report persisted

## DOCX/UI/Security
- [x] real valid DOCX
- [x] title/headings/order
- [x] bold headings
- [x] Persian RTL
- [x] B Nazanin configured
- [x] FAQ/extras
- [x] Unicode
- [x] polished dashboard UI
- [x] responsive/modal/validation
- [x] live status/progress
- [x] cancel/retry/download
- [x] loading/error/empty/accessibility
- [x] no silent production secret
- [ ] ownership/file authorization
- [x] CSRF/security headers
- [ ] no secret leakage
- [ ] reproducible dependencies
- [x] clean migrations

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
