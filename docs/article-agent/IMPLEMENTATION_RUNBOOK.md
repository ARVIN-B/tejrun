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
