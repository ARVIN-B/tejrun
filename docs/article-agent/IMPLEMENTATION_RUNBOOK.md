# Implementation Runbook

Repeat until all acceptance criteria pass:
1. read current milestone and relevant code
2. inspect behavior, not class names
3. express invariant in tests
4. implement coherent change
5. run targeted tests
6. fix failures immediately
7. run broader tests
8. inspect diff
9. update plan/findings/status
10. commit coherent milestone
11. continue to next unchecked item

Never stop because tests pass accidentally, a class exists, a prompt improved, or a commit says complete.

If implementation and test disagree, determine the product truth and fix the implementation or test accordingly. Never weaken validation just to get green.

Treat all model outputs as untrusted: empty, malformed, too short, too long, repetitive, contradictory, markdown-contaminated or adversarial.

Database is source of truth for job state. Redis is coordination/broker infrastructure. Output storage is artifact storage.

Persist enough state after every expensive stage to resume safely.

At every session boundary update:
- current milestone
- completed work
- tests/evidence
- remaining work
- decisions
- risks

If context/account/model changes, read the repository docs and continue from the first unchecked item. Never restart from scratch.

Final report must list changed files, migrations, exact commands/results, smoke tests, load checks and limitations. If a required verification could not run, the system is NOT DONE.

## Celery article-job contract

`apps.article_agent.tasks.generate_article_task` is a bound Celery task with
exactly one broker argument: `job_id`. The HTTP flow persists the ArticleJob
and its Celery task ID, then publishes `apply_async(args=[job_id], task_id=…)`.
The task ID is transport metadata for stale-task rejection, never a second task
argument. Retries use `self.retry()` without replacement positional arguments,
so they retain the same one-argument contract.

## Budgeted provider output configuration

`ARTICLE_AGENT_LLM_MAX_OUTPUT_TOKENS` (default `8192`) is passed explicitly
to the Groq-compatible client; do not rely on a provider's short default
completion length. `ARTICLE_AGENT_MAX_BUDGET_REPAIRS` (default `3`) bounds
repair attempts. A unit remains rejected if it is still outside its persisted
minimum/maximum allocation after those attempts.

## Groq quota and routing configuration

The Redis limiter is a local admission controller, not evidence of an HTTP
response from Groq. `RateLimitExceeded` records one of the account/model
concurrency, RPM, TPM, input-TPM or output-TPM dimensions. Its retry delay is
derived from the blocking active lease or counter window. `ProviderRateLimitError`
is emitted only after an actual HTTP 429 and preserves `Retry-After` when the
provider supplied it.

Every call reserves an UTF-8 conservative input estimate and a unit-specific
maximum completion budget. Successful calls reconcile that reservation with
provider usage metadata; unsuccessful/timed-out calls release only concurrency
because provider token consumption is unknown. Account limits always apply.
Optional model limits in `ARTICLE_AGENT_GROQ_MODEL_LIMITS` apply in addition,
so changing model does not bypass an organization/project limit.

`ARTICLE_AGENT_PRIMARY_MODEL` falls back to `LLM_MODEL` for compatibility.
`ARTICLE_AGENT_FALLBACK_MODELS` and `ARTICLE_AGENT_REVIEW_MODEL` are opt-in;
writing stays on the primary model until an eligible *model-scoped local*
capacity rejection occurs. Provider-429 and transient-error fallback are
disabled by default because those failures can be account-wide. Enable them
only after confirming project permissions and quotas. Values for every quota
must come from the exact Groq project/organization Limits view, not examples
or published plan tables.

An empty or non-text provider completion is never passed to `BudgetManager`.
The client retries that individual provider call a bounded number of times
(`ARTICLE_AGENT_EMPTY_RESPONSE_RETRIES`, default `1`); if it remains empty it
raises `ProviderEmptyResponseError`, which is a retryable provider failure.
The job resumes from accepted checkpoints on Celery retry instead of treating
zero words as a normal budget-repair result.

## Current execution status (2026-10-09)

- M1/M2 are verified by planner/runtime-budget tests, including deliberate starvation, short/long repair and impossible-output rejection.
- M3 has versioned execution claims, stale-write guards and persisted section/extras checkpoints; renderer-resume is verified without regenerating prose.
- M4/M5/M10/M13/M14 have implementation plus targeted tests. Large-context and live Redis integration verification remain pending.
- Latest local evidence: `.venv\\Scripts\\python.exe manage.py test apps.article_agent.tests --keepdb --verbosity 1` (63 passing), `.venv\\Scripts\\python.exe manage.py check` (pass), and `.venv\\Scripts\\python.exe manage.py makemigrations --check --dry-run` (no changes). Production deployment verification remains a server-side operation.
- Next exact action: add renderer-failure resume coverage, then complete section/article review, style and lifecycle adversarial verification.
