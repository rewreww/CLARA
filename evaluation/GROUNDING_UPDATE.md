# Guideline grounding update - 2 November 2026

The first NLM development question exposed a routing bug: home/office BP wording
could bypass guideline retrieval and be answered from model knowledge. BP, ABPM,
and HBPM now reach the guideline path. Generic `blood` no longer implies a lab
request; explicit lab terms remain supported.

The answer contract now uses structured paragraphs with source IDs. CLARA resolves
IDs against the actual passages supplied to the generator and formats the answer
with document title, PDF filename, and physical PDF page(s). It rejects unknown or
missing source references, retries once, and withholds untraceable answers. Source
titles use PDF metadata only when corroborated in the document's opening pages,
otherwise the filename supplies the document label. Private evidence text is not
included in frontend source-card metadata.

Before citing a passage, its whitespace-normalized text must uniquely match the
current PDF. Cross-page excerpts receive all matching physical pages. Stale or
ambiguous passages are excluded. This does not repair extraction errors in tables,
symbols, or figures and does not prove semantic support for every generated claim.

The prompt requires evidence-only guideline claims, explicit preferred options,
relevant conditions/exceptions, and no unrelated treatment plan. It separates
diagnostic definitions from medication indications. There are no question-specific
answers or clinical treatment rules added by this change.

For the configured GPT-OSS Groq adapter, guideline requests use JSON output,
standard (`medium`) reasoning, and a 2,400-token completion budget. Truncated
responses are withheld. Rate-limit retries respect Retry-After up to 60 seconds.
Provider references: https://console.groq.com/docs/reasoning and
https://console.groq.com/docs/api-reference . No generator model was changed.

## Validation and limits

- Service tests cover question routing, source-page verification, unknown citations,
  invalid evidence formats, optional quote validation, truncated provider output,
  both chat routes, no-evidence behavior, and existing chat/history/document behavior.
- Development captures remain under `.clara/evaluation/grounding/`.
- `after/` failed because the provider returned no response text during a retry.
- `after-completion-fix/` and `after-scope-fix/` exposed unsupported additions and
  incomplete citation coverage. These were not treated as successful grounding.
- `final-validation/` had one withheld answer and two rate-limit failures.
- `structured-validation/`, `quote-validation/`, and `verified-grounding/` exposed
  brittle quote copying, including line-wrap hyphens and paraphrased quotations.
- `source-validation/` completed three questions with valid source citations, but
  the BP answer still weakened the ABPM preference. That run used low reasoning.
- `final-bp/` used the final medium reasoning setting and retrieved physical pages
  16, 19, and 20. Its answer identifies possible white-coat hypertension, ABPM as
  preferred, and HBPM as an alternative, without prescribing a drug or treatment
  target. The source wording and numeric symbols still warrant researcher review.

The final formatter consolidates citations from the same PDF. Capture records
retain model attempts and their citation-validation outcomes; normal chat does
not persist these diagnostic traces. The capture harness records the grounding
module and retriever hashes, model configuration, and exact generation context.

No new Ragas scores or clinical correctness claim are made. A valid citation means
the referenced evidence exists and was supplied to the model; it is not an
entailment guarantee. The same unused final thesis set must remain reserved.
Broader patient/mixed-source and guideline testing remains necessary. Existing
embeddings were reused; the corpus was not rebuilt or split into separate databases.

## Activation

The managed local services were restarted with the update. The launcher reached
ready status; the watchdog subsequently reported healthy gateway, tunnel, Vercel
API, backend, and LLM. A real request through the restarted `/chat/stream` endpoint
passed the source-format smoke check and is saved in `grounding/live-smoke.json`.
That artifact contains source cards, not exact generation context, so it must not
be substituted for the capture harness output in Ragas.

The live response identified ABPM as preferred and cited physical PDF pages 16,
19, and 20. It also added a statement about considering treatment if out-of-office
BP remains elevated; this is a remaining scope/semantic-grounding issue, not a
validated treatment recommendation. The new citation checks do not automatically
detect such unsupported inferences. Continue manual review and measured development
evaluation rather than reporting hallucinations as eliminated.

## Concise answers and minimal source display

Following user review, simple questions now request one short paragraph (normally
1-3 sentences and under 80 words), without unasked numerical criteria, hypothetical
branches, or treatment advice. Explicitly detailed/multi-part questions can still
receive the necessary detail. The prior instruction requesting two to four
paragraphs was removed.

The model is instructed to choose the single best supporting excerpt where
sufficient, rather than cite redundant evidence. Citation rendering preserves all
pages actually needed by its chosen sources; it does not force a false one-page
citation or truncate the generated answer. The title and physical pages appear
once at the top, without repeating the filename or adding a duplicate source
footer. PDF filenames remain available in source metadata.

Guideline source cards are sent after answer validation and contain only the cited
sources. The evaluation trace still captures ALL passages supplied to generation,
including uncited passages; display filtering must not change Ragas inputs.

Validation: 17 service tests passed before the final prompt refinement. The
`concise-validation` capture produced short answers for the BP question and a
multi-part device question, without the former numeric/treatment follow-up.
Subsequent source-selection refinement is captured in `concise-minimal-source`.

The final representation uses one primary `source_id` per answer point (older
stored `evidence` lists remain readable). Short, single-part questions receive
an explicit one-paragraph/80-word instruction; overlong model output is retried,
not silently truncated. Explicitly detailed, multi-part, or longer questions are
exempt. This is presentation/intent handling, not a clinical treatment rule.
Final concise BP capture: `concise-final/`. Source previews are deferred until
answer validation so uncited retrieval candidates do not appear as answer sources.
All 18 service tests passed. In that final capture, the BP answer was one short
paragraph citing physical page 19 only; the source cards also showed only page 19.
All three generation-context passages were retained in the evaluation record.
