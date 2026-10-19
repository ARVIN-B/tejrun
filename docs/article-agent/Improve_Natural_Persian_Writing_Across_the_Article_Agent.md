# Task: Improve Natural Persian Writing Across the Article Agent

## Objective

Inspect the entire Article Agent implementation and improve all LLM prompts responsible for article planning, section generation, continuation, reviewing, scoring, revision, rewriting, FAQ generation, introductions, conclusions, summaries, and final article assembly.

The primary goal is to produce **natural, fluent, idiomatic, reader-focused Persian prose** that resembles the work of a competent Persian-language editor and subject-matter writer.

Do not merely append "write like a human" to existing prompts. Identify and address the specific prompt patterns that cause generic, repetitive, formulaic, overly formal, translated-sounding, or semantically redundant Persian writing.

Optimize for writing quality, factual reliability, clarity, and usefulness—not for bypassing AI-detection systems. Do not introduce deceptive claims about human authorship.

## Phase 1: Audit the existing implementation

Before modifying anything:

1. Inspect the repository and identify every prompt template, system instruction, user prompt, output schema, and prompt-building component used by the Article Agent.
2. Trace the complete lifecycle of an article:
   - Topic interpretation and planning
   - Outline and heading generation
   - Section drafting
   - Section continuation or chunk generation
   - Context and memory construction
   - Section review and scoring
   - Revision and rewriting
   - FAQ generation
   - Introduction and conclusion generation
   - Final assembly and quality checks
3. Find duplicated, conflicting, or inconsistent writing instructions across these stages.
4. Identify where generated content is passed into later prompts and whether repeated instructions cause formulaic output.
5. Review the current tests and existing architectural conventions before changing code.

Do not assume that every stage has a separate prompt. Follow the actual implementation and modify the relevant components that exist.

## Phase 2: Establish a shared Persian writing standard

Create a centralized, reusable set of Persian writing principles that can be incorporated into the appropriate prompts without duplicating a huge block of instructions everywhere.

Use the existing architecture and naming conventions. Do not introduce a new framework or unnecessary abstraction just to store these instructions.

The standard must cover the following principles.

### A. Natural, idiomatic Persian

- Write in Persian that sounds originally composed in Persian, not mechanically translated from English.
- Prefer natural Persian word order, familiar expressions, and established terminology for the target audience.
- Avoid unnecessary bureaucratic, ceremonial, or excessively literary phrasing.
- Use a professional but readable tone unless the article's audience or purpose requires another tone.
- Avoid awkward literal translations, unnecessary English sentence structures, and excessive nominalizations.
- Use Persian punctuation, spacing, and half-spaces consistently according to the project's existing editorial conventions.
- Keep terminology consistent throughout an article.

### B. Avoid formulaic openings

Do not default to generic openings such as:
- «در دنیای امروز...»
- «در عصر حاضر...»
- «با پیشرفت روزافزون فناوری...»
- «موضوع X از اهمیت ویژه‌ای برخوردار است...»
- «در این مقاله قصد داریم به بررسی... بپردازیم.»

These phrases are not absolutely forbidden when genuinely appropriate, but they must not appear as automatic templates.

Choose an opening based on the actual topic and reader intent. Depending on the subject, begin with a concrete problem, a useful observation, a question the reader needs answered, a relevant distinction, or the key information itself.

Never invent a real-world scenario, statistic, personal anecdote, or experience merely to make the opening engaging.

### C. Eliminate semantic repetition

- Each paragraph must contribute a distinct idea, explanation, example, qualification, or practical implication.
- Do not restate the same claim using synonyms just to increase article length.
- Avoid repeating the introduction in the conclusion.
- Avoid repeating section summaries in the next section unless the connection is necessary.
- Do not repeat the same keyword, definition, transition, or recommendation unnaturally.
- When two planned sections substantially overlap, resolve the overlap rather than filling both with paraphrases.
- Repetition is acceptable when it improves comprehension, reinforces an essential instruction, or is necessary for a recap. It must have a clear purpose.

### D. Natural sentence and paragraph structure

- Vary sentence length and syntax according to the content. Do not enforce artificial randomness or deliberately create awkward sentences.
- Avoid paragraphs that all have the same length or follow the same rhetorical pattern.
- Do not force every section into a fixed sequence of definition, benefits, disadvantages, examples, and conclusion.
- Use short paragraphs when they improve readability and longer paragraphs when an explanation requires continuity.
- Avoid excessive one-sentence paragraphs, but do not combine unrelated ideas into long blocks.
- Use lists only when the information genuinely benefits from a list. Explain complex relationships in prose when appropriate.
- Use headings that describe the actual content of a section instead of generic or repetitive heading patterns.

### E. Specificity and substance

Replace vague statements with useful explanations.

For example, instead of:
«انتخاب روش مناسب می‌تواند تأثیر زیادی بر بهبود عملکرد داشته باشد.»

Prefer a context-specific explanation that identifies which method matters, under what conditions, and how it affects the result.

Whenever relevant:
- Explain why a recommendation works.
- State the conditions under which it applies.
- Give a concrete example or implementation detail.
- Identify limitations, trade-offs, exceptions, or common mistakes.
- Distinguish established facts from interpretation and recommendations.
- Answer the actual question the reader is likely to have.

Do not add examples, numbers, citations, technical details, or claims unless they are supported by the available context or reliable sources.

### F. Avoid repetitive transitions and filler

Do not mechanically overuse expressions such as:
- «علاوه بر این»
- «از سوی دیگر»
- «نکته حائز اهمیت این است که»
- «شایان ذکر است»
- «در ادامه خواهیم دید»
- «به طور کلی»
- «در نهایت»
- «لازم به ذکر است»

Use transitions only when they express a real logical relationship. Often, a direct sentence is clearer than a transitional phrase.

Remove sentences that only announce what the next sentence will explain.

### G. Appropriate tone and vocabulary

- Determine the audience and purpose before choosing the level of formality.
- Avoid exaggerated adjectives such as «بی‌نظیر»، «شگفت‌انگیز»، «انقلابی» and «حیاتی» unless justified by the subject.
- Avoid promotional language when the article is supposed to be informative or analytical.
- Avoid unsupported certainty and sweeping statements.
- Use technical terminology where useful, but explain it when the intended audience may not know it.
- Do not make every article sound like the same generic SEO article.
- Let the subject matter determine the tone, structure, and depth.

### H. Useful conclusions

- Do not automatically summarize every heading.
- Do not repeat the introduction in different words.
- Conclude with the most useful implication, decision criterion, practical next step, or unresolved limitation when appropriate.
- Do not force a call to action into articles that do not need one.
- Do not create a conclusion merely to satisfy a template if the article's structure does not require one.

### I. Factual integrity

Natural writing must never come at the expense of truth.

- Never invent personal experience, first-person anecdotes, quotations, sources, research findings, statistics, or named experts.
- Do not write «بر اساس تحقیقات» unless supporting research is available.
- Do not turn uncertainty into certainty.
- Do not remove important qualifications merely to make prose more confident.
- If information is missing, use cautious wording, request evidence where the workflow permits it, or omit the unsupported claim.
- Preserve citations, source attribution, and factual meaning during revision.

## Phase 3: Improve the prompts for each stage

### 1. Planning and outline prompts

Ensure the planner produces an outline driven by search intent, reader needs, and logical progression.

- Give every section a distinct purpose.
- Identify and prevent overlapping headings.
- Avoid generating the same standard outline for unrelated topics.
- Do not require a fixed number of headings or subsections unless the task explicitly specifies one.
- Ensure the planned structure provides enough substance for the requested article without encouraging filler.

### 2. Section-generation prompts

Instruct the writer to follow the shared Persian writing standard while fulfilling the section's specific purpose.

Provide the relevant context, intended audience, section objective, existing article content, and necessary terminology without flooding the prompt with redundant material.

- Continue the article naturally from the preceding content.
- Do not restart the article or introduce the overall topic from scratch in every section.
- Do not repeat material already covered unless necessary.
- Keep each section focused on its own objective.
- Do not force a generic introduction or conclusion into every section.
- Preserve any required output format and section boundaries.

### 3. Continuation and chunk-generation prompts

Because long articles may be generated in multiple chunks, explicitly preserve continuity across chunks.

- Continue from the actual last point of the previous chunk.
- Do not repeat its final paragraph or paraphrase its last several sentences.
- Avoid restarting the argument or redefining established terms.
- Preserve terminology, tone, narrative perspective, and the level of detail.
- Ensure the new chunk adds substantive content.
- Do not mention chunking, memory, prompts, or internal generation mechanics in the article itself.

### 4. Review and scoring prompts

Reviewers must evaluate actual writing quality, not simply the presence of headings, keywords, or a prescribed structure.

Evaluate:
- Naturalness and idiomatic Persian
- Clarity and readability
- Repetition of ideas and wording
- Generic openings and conclusions
- Unnecessary filler and transitions
- Translated-sounding phrasing
- Paragraph and sentence monotony
- Specificity and usefulness
- Logical flow and continuity
- Factual accuracy and unsupported claims
- Compliance with the section's intended purpose

When identifying a problem, point to the exact sentence or passage and explain what is wrong.

Do not mark prose as unnatural merely because it is formal, technical, grammatically correct, or well structured. Do not treat sentence-length variation as a requirement to introduce artificial irregularity.

### 5. Revision and rewriting prompts

Revisions must fix the diagnosed problems rather than rewrite everything indiscriminately.

- Preserve correct facts, useful explanations, citations, terminology, and the author's intended meaning.
- Remove redundant sentences and unnecessary filler.
- Replace generic language with context-specific explanations when the required information is available.
- Rewrite unnatural Persian phrasing idiomatically.
- Repair logical transitions and paragraph structure where necessary.
- Preserve appropriate technical depth and required length.
- Do not make the prose longer just to make it appear more elaborate.
- Do not replace precise technical writing with casual or colloquial language unless the audience requires it.
- Avoid repeatedly rewriting acceptable text when no material improvement is needed.

Where possible, provide the reviewer with actionable revision instructions instead of vague feedback such as "make this sound more human."

### 6. FAQ, introduction, conclusion, and final-assembly prompts

Apply the same writing standard to these components.

- FAQs must answer genuine reader questions and avoid restating entire sections.
- Questions should sound like plausible questions from the target audience, not keyword variations generated for SEO.
- Introductions must establish relevance without generic filler.
- Conclusions must add practical value rather than mechanically recap the article.
- Final assembly must preserve continuity and remove accidental duplication across section boundaries.
- Do not allow final polishing to introduce unsupported facts or change the meaning of previously reviewed sections.

## Phase 4: Add a targeted naturalness review

If the existing architecture supports review criteria or scoring dimensions, introduce or refine a Persian naturalness criterion within that system.

Do not add a new model call automatically for every section. First evaluate whether the existing reviewer can handle these checks without materially increasing latency, token consumption, or cost.

The review should detect concrete problems, including:
- Repeated generic phrases
- Redundant sentences and paragraphs
- Empty introductory statements
- Mechanical transitions
- Repeated explanations across sections
- Unsupported claims
- Awkward Persian syntax
- Unnecessary verbosity
- Conclusions that add no value

Require the reviewer to distinguish between:
1. A genuine quality defect
2. An acceptable stylistic choice
3. A subjective preference that does not justify revision

Avoid a vague "human score" or claims that a text can be reliably classified as human-written. Score observable writing qualities instead.

Use the existing scoring and revision thresholds unless there is clear evidence that they need adjustment. Avoid revision loops caused by subjective reviewer feedback.

## Phase 5: Preserve the current architecture and runtime behavior

This is a prompt-quality task, not a full application rewrite.

- Preserve the existing Clean Architecture boundaries and module responsibilities.
- Preserve public interfaces, service contracts, output schemas, and structured response formats unless a specific incompatibility requires a carefully justified change.
- Do not break JSON parsing, section identifiers, checkpoints, database persistence, Celery retries, memory construction, or final document assembly.
- Keep existing word-count, SEO, citation, and formatting requirements where they are legitimate.
- Do not remove existing safety or factuality constraints.
- Do not place the full article or all historical sections into every prompt just to improve continuity.
- Reuse the existing context builder and memory mechanisms.
- Keep prompt instructions concise enough to avoid unnecessary token consumption.
- Do not modify provider rate limits, retry policies, database models, or unrelated infrastructure as part of this task.
- Follow existing project conventions for prompt storage, configuration, testing, and dependency injection.

## Phase 6: Tests and validation

Add or update tests for the modified prompts and review logic.

Include Persian examples that exercise the following problems:
1. A generic opening that should be improved.
2. Two paragraphs repeating the same idea.
3. An unnatural literal translation from English.
4. A vague recommendation that needs concrete conditions.
5. A conclusion that simply repeats the article.
6. A technically correct paragraph that should not be rewritten unnecessarily.
7. A continuation that repeats the end of the previous chunk.
8. A factual claim that must not be fabricated or strengthened during revision.

Tests should verify the relevant behavior, prompt construction, output contracts, and preservation of required metadata. Use deterministic unit tests where possible; do not rely entirely on live LLM calls.

Run the relevant test suite and report:
- Which prompt components were inspected.
- Which files were modified.
- Which writing rules were introduced or consolidated.
- Which tests were added or updated.
- Which tests passed or failed.
- Any remaining limitations or unresolved issues.

## Implementation workflow

1. Inspect first.
2. Summarize the existing prompt architecture and propose a concise implementation plan.
3. Implement the changes in the relevant existing files.
4. Add or update tests.
5. Run the appropriate checks.
6. Report the changes and any trade-offs.

Do not stop after producing an audit or plan. Proceed with implementation unless a blocking ambiguity or destructive change requires my approval.

The final result should improve the naturalness and usefulness of Persian articles while preserving factual integrity, architectural consistency, and the current long-article generation workflow.