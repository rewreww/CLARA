# Guideline retrieval and claim validation

CLARA must distinguish finding a related PDF page from proving a clinical claim.
The reported failure cited physical page 18 of the old renal/metabolic screening
guideline for a medication recommendation. That page is scope/background text.
Matching its filename or mentioning CKD is insufficient evidence.

## Runtime path

1. Search the indexed collection using local MiniLM embeddings and BM25. Normalize
   renal/kidney terminology, keep the current question in focus, and down-rank
   background sections. Treatment questions omit identifiable scope/contents pages.
2. Verify retrieved text against the original PDFs, and include bounded adjacent
   passages for recommendations continued across pages. Supply at most five source
   groups for simple questions and eight for broad questions.
3. Ask the generator for short answer points, each referencing server-owned passage
   IDs. The server resolves those IDs to original text; the model does not invent
   the displayed supporting excerpt.
4. Reject malformed output, unknown passages, and quotations absent from the cited
   source. Separately ask the configured evidence reviewer to evaluate every point
   against its own evidence, including conditions, thresholds, negation, drug
   preference, and recommendation strength. Absence claims also receive the full
   retrieval bundle so that an unrelated selected passage cannot establish absence.
5. Allow one formatting repair and one evidence repair, with validation feedback
   (at most three drafts). If the same validation fails again, withhold the
   recommendation and final citations. A reviewer outage
   also withholds the answer. No unvalidated draft is streamed to the user.
6. Recheck supporting text against the unchanged PDF and resolve physical pages.
   Display accepted sources and their supporting excerpts in the PDF panel.

The default reviewer uses GPT-OSS-120B through the existing Groq connection when
the generator is OpenRouter. `GROUNDING_REVIEW_PROVIDER` and
`GROUNDING_REVIEW_MODEL` can override the reviewer. The generator is unchanged.
Operational failures can use the other configured free provider once. Refusals
do not trigger provider switching. OpenRouter review requires a `:free` model.
Fallback may use the same model as generation, so review is a separate check,
not a guarantee of model independence. Requests are bounded and exact review
results are cached in memory; API keys and prompts are not written to normal logs.

## Verification

Backend regressions cover exact source identity, wrong-page quotations, unrelated
real quotations, mandatory review, missing review results, outages, fallback
policy, page resolution, retrieval vocabulary, and existing chat behavior.
Run from `ai-services/llm_service`:

```powershell
..\..\.venv\Scripts\python.exe -m unittest discover -p test_*.py
```

For live development regressions using actual PDFs and configured providers:

```powershell
.\.venv\Scripts\python.exe evaluation\verify_claim_grounding.py --output .clara\evaluation\claim-grounding
```

This records exact evidence, model drafts, review verdicts, citations, and timings.
It uses previously discussed development questions, not the reserved thesis test
set. A result with sources means the pipeline accepted it; it is not an automatic
clinical-correctness score. Inspect the answer and cited text as well as the verdict.

### Development run, 7 November 2026

The final reviewer rejected all six adversarial cases and accepted the correctly
qualified positive control. The renal-failure question returned supported citations
to physical pages 42–43 of the main hypertension guideline (about 30 seconds with
a cold embedding model). Earlier warm control questions took about 5–10 seconds;
multi-part questions with repairs took longer. These are observations, not latency
guarantees. The final broad comorbidity retest was interrupted by provider rate
limits and is not recorded as a passing end-to-end result. Its retrieval did find
treatment passages; generation and validation must still be retested after quota
recovery. Earlier weaker-reviewer runs missed a recommendation-strength error,
which motivated the stronger default reviewer and the added negative control.

## Limits and performance

Semantic review is model-based and can miss an error or reject valid text. It does
not prove corpus completeness, guideline currency, or suitability for an individual
patient. Keep clinician review and manual source checks. Missing retrieved support
must be described as a limitation of the supplied passages, not proof that the
entire guideline contains no recommendation.

Local embeddings and lexical indexes are cached; the first query after restart
incurs model loading. Review adds an API call, and a repair adds another generation
and review. Free-provider quotas and fallback affect latency. Accuracy checks are
not bypassed to make a response faster.
