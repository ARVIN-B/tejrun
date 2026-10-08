# Article Agent — Master Production Specification

## Goal
Build a production-grade asynchronous Article Agent in the existing Django/Celery/PostgreSQL/Redis/Groq architecture.

Input: title, ordered headings, total requested words, keywords, language/audience/tone/purpose.
Output: complete article, exact heading order, exactly four FAQs, conclusion, common_mistakes, applications, quality report and valid DOCX, with durable job state and resumability.

The article must be useful, coherent and natural. Do not fabricate facts/sources. Do not optimize for AI-detector evasion.

## Architecture
Preserve the sound layered architecture:
Presentation -> Application -> Domain -> Infrastructure.
The LLM is an infrastructure dependency; application code owns state, budgets, validation, persistence, retry, cancellation and acceptance.

## Canonical article units
1. every user section
2. conclusion
3. FAQ (exactly 4 Q/A pairs)
4. common_mistakes
5. applications

### ArticleBudget
Create a domain/application budget model with:
- total_words
- allocations for every unit
- reserved_words
- consumed_words
- remaining_words

Each allocation contains:
- unit_id/type
- target_words
- minimum_words
- maximum_words
- priority
- generated_words
- status

Hard invariants:
- sum(target_words) == requested total
- sum(minimums) <= total <= sum(maximums)
- minimum <= target <= maximum
- before every generation: remaining >= minimums of every remaining required unit

No generation begins if these invariants fail.

## Planner
Deterministically allocate the whole budget before the first LLM writing call. Reserve minimums for every unit, distribute remaining words with explicit weights, repair integer rounding deterministically, validate and persist the plan. Do not use a fixed body ratio with extras left implicit.

The plan should also contain semantic purpose, key points, dependencies, research requirements and keyword intent.

## Runtime BudgetManager
Implement reserve -> generate -> semantic count -> expand/compress -> re-count -> accept/commit.

No unit is accepted merely because it is non-empty. If it cannot satisfy its bounds after bounded repair attempts, fail safely with a structured error.

Every revision/final edit revalidates its unit budget.

## Canonical WordCounter
One semantic word counter for planner diagnostics, runtime budgets and QualityGate.
- normalize whitespace
- handle Persian/zero-width characters safely
- count article prose only
- count FAQ Q/A semantically
- never count `str(dict).split()` or JSON syntax

Final report: requested, allocated, actual, delta, percentage delta, per-unit target/min/max/actual.

## Section writing
Writer receives only bounded, relevant context: current plan, budget, key points, relevant memory/research/style and useful neighboring summaries. It must return prose only and obey heading/keyword/factual constraints.

## Section review/revision
Review relevance, completeness, factual caution, usefulness, repetition, naturalness, heading alignment, keyword use, structure, budget and continuity. Strict structured result. Failed review triggers targeted revision and re-review; bounded attempts; hard failures cannot silently pass.

## Article Memory
Structured bounded memory: covered_topics, section_summaries, important_facts, claims_made, examples_used, terms_introduced, avoid_repeating, style_notes, open_threads, keyword_usage, unresolved_claims, research_notes. Memory is not a transcript. Use deterministic compaction first.

## Article-level review
Build a bounded review representation containing real article prose: heading, target/actual words, summary, opening/closing excerpts, current section prose where needed, claims/facts/evidence, keywords, extras and style metrics.

Detect:
- repetition
- contradiction
- missing bridges/transitions
- weak conclusion
- redundant FAQ
- common-mistake/application mismatch
- keyword stuffing
- imbalance
- unsupported claims
- template language
- inconsistent terminology
- repeated examples
- unresolved threads

Every finding must include type, severity, description, affected unit indexes and actionable recommendation.

## Final Editor
Only edit affected units. Preserve meaning/facts/heading intent/budget. Re-review edited units. Never perform an unnecessary whole-article rewrite.

## Natural writing quality
Implement deterministic metrics:
- generic_opening_count
- generic_transition_count
- repeated_phrase_count
- repeated_sentence_pattern_count
- sentence_length_variance
- paragraph_length_variance
- keyword_stuffing_score
- template_phrase_score
- repeated_example_count
- repeated_structure_count

Add an LLM style reviewer and targeted editor. Improve specificity, rhythm, coherence and non-template language without inventing facts. No detector-evasion objective.

## Research
Explicit modes: required / optional / disabled.
If enabled, wire a real provider with provenance. If unavailable, use explicit disabled/no-research mode and prohibit unsupported factual specificity. Never label empty returned data as successful research.

## Groq adapter
Environment-based configuration, timeout, cancellation where SDK permits, normalized provider exceptions, usage metadata when available, no secret leakage.

## Distributed rate limiting
Redis-backed coordination across Celery workers:
- concurrency limit
- request reservation
- token reservation/estimation when possible
- Retry-After
- exponential backoff + jitter
- bounded retries
- structured metrics/logs

Add concurrent worker tests.

## Job lifecycle
States: queued, planning, researching, writing, reviewing, revising, final_review, editing, quality_check, rendering, completed, failed, cancel_requested, cancelled.

Persist checkpoints for request, plan/budget, research, each unit, reviews/revisions, article review/edit and final artifact.

Idempotency requirements:
- duplicate task invocation is safe
- worker crash after unit N resumes from accepted checkpoint
- renderer failure does not regenerate prose
- stale task cannot overwrite newer retry

## Cancellation
Queued cancellation prevents execution. Active cancellation is observed between expensive calls and provider cancellation is attempted when supported. Cancellation and completion must be race-safe; cancelled jobs never become completed afterward.

## Retry
Separate provider retries from user job retries. User retry preserves accepted checkpoints and resets only transient/error state. Prevent old workers from overwriting new retry state.

## QualityGate
Reject missing/empty units, heading mutations, FAQ != 4, missing extras, budget violations, critical findings, failed reviews, research requirement failures and invalid document generation. Final tolerance is diagnostic, not a replacement for per-unit validation.

## FAQ
Exactly four non-empty Q/A pairs. Prefer reliable structured output if supported; otherwise robust parse + strict validation + repair. Do not depend on fragile line parsing alone.

## Context management
Field-level compaction priority:
1 task/invariants
2 current unit + budget
3 relevant plan constraints
4 relevant research
5 relevant memory
6 bounded prose
7 low-priority metadata

Never slice serialized JSON. Test 2k/5k/10k/20k articles and pathological context.

## DOCX
Real .docx, title and heading order, bold headings, Persian RTL, B Nazanin when configured/available, FAQ/extras, Unicode. Test by opening/reading generated document.

## UI
Replace the basic article template with polished existing-dashboard styling: responsive dark/glass UI, reusable classes, modal, title/word count/headings/keywords separated by `-`, validation, live progress, stage/current section, cancel/retry/download, loading/error/empty states and accessibility. Avoid reload-driven normal UX.

## Security/production
No silent production secret fallback. Environment secrets. Verify DEBUG/hosts, secure cookies, CSRF, HSTS, clickjacking/content-sniffing headers, ownership/file authorization, no API key/prompt leakage, reproducible dependencies and clean migrations.

## Tests
Cover domain/contracts, planner invariants, runtime budgets, memory/context, research modes/failures, section/article review, style metrics, rate-limit concurrency, duplicate tasks, mid-pipeline failure/resume, cancellation races, retries, malformed/empty model output, renderer failure, UI ownership/CSRF, DOCX, 10k/20k load-ish scenarios.

## Definition of done
Not done because a class exists, prompt improved, mocks pass or a commit says complete.

Done only when all acceptance items pass, full suite and available lint/type checks pass, migrations/checks pass, real configured-provider smoke test passes, 5k/10k smoke tests pass, cancellation/retry/resume/concurrency/DOCX smoke tests pass, and no P0/P1 finding remains.
