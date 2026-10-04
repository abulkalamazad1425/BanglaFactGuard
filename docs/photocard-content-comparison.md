# Content comparison (local, statement by statement)

Content answers one question: does the submitted claim present the claimed
source's report faithfully? Whether that report is itself true is out of
scope. Source and Date are decided separately; a date mismatch never changes
the content result, so MATCHED + date MISMATCHED is a valid outcome.

Code: `backend/app/features/verification/analysis/content_check.py`
(`ContentComparator`), decided in `analysis/decisions.py::decide_content`,
run inside S11 only after the source is CONFIRMED.

## One check for every claim type

| Submission | Statements compared |
|---|---|
| Photo card (headline from OCR) | the headline |
| Text, headline only | the headline (identical code path) |
| Text, headline + body | the headline **and** every material body sentence |

The comparator replaced the old S10 manipulation detector and the
score-threshold `decide_content`. Retrieval, best-article selection (S01–S08)
and the S09 NLI measurement are unchanged. Photo cards keep their own result
identity (`compute_photocard_hash`); their content logic is the same.

No third-party inference API is called. Only the already-loaded local
embedding, NLI and NER services plus deterministic rules are used.

## Per statement

1. **Evidence selection.** The source title and every body sentence are ranked
   by claim content-word coverage and local embedding similarity. This only
   chooses what to compare with.
2. **Verbatim.** The statement is the source's own text, or a contiguous
   excerpt that drops nothing meaning-bearing (negation, plan/future,
   quantifier, denial, allegation). Result: SUPPORTED. No model is needed, so
   an exact copy is MATCHED whatever an unvalidated NLI score or another
   sentence of the article says.
3. **Concrete conflict** with a sentence that shares ≥70% of the statement's
   content words. Result: CONTRADICTED, with claim and source quoted. The
   conflict kinds are:
   - **Number:** a changed number for the same referent (role word such as নিহত
     or বরাদ্দ, or the noun after the number), or a currency swap.
   - **Negation:** flipped negation on the same verb. "বাড়ায়নি" is not read as
     the negation of "কমিয়েছে".
   - **Modality:** completed versus planned/possible.
   - **Scope:** all versus some, or at least versus at most.
   - **Entity:** a name substituted or roles swapped.
   - **Attribution:** an allegation ("দাবি/অভিযোগ করেছেন") presented as fact.

   A changed number beats an NLI reading that ignores it. Scope and modality
   rules yield to a strong local entailment, and the case is left open.
4. **Facts preserved.** Every content word, number and named entity is in the
   passage, and negation, tense and quantifiers agree. Result: SUPPORTED.
   Shortening and reordering are fine. Dropping a neutral reporting frame
   ("পুলিশ জানিয়েছে, …") is fine.
5. **Paraphrase.** Local NLI entailment ≥ 0.80, contradiction ≤ 0.20, and the
   statement's numbers and names are in the passage. Result: SUPPORTED.
6. Otherwise INSUFFICIENT_EVIDENCE, with the specific reason (word, number or
   name not in the source; no passage discusses it; competing statements;
   semantic support unavailable).

A statement joining facts from separate source sentences (title + a lead
detail) is checked clause by clause.

## Decision

- **ALTERED:** at least one material statement is CONTRADICTED.
- **MATCHED:** every material statement is SUPPORTED.
- **INCOMPLETE:** otherwise. Absence from the source is never ALTERED, and a
  low score alone is never a reason.

An unvalidated NLI contradiction can never produce ALTERED. With
`THRESHOLD_NLI_BANGLA_VALIDATED=true`, a contradiction ≥ 0.90 on a well-aligned
passage may.

## Results

`analysis_details.content_check` holds each finding: part, claim text,
status, kind, basis, explanation, verbatim source quotes, NLI scores. The
`manipulation_flags.check_states` (headline, body, numbers, negation,
entities, scope, attribution, modality) and `discrepancies` that the UI
already renders are derived from the same findings.

`VERIFICATION_PIPELINE_VERSION` is `v3.1-content-evidence`, so results from
the previous content logic are not reused.

## Bounds and limits

- **Comparison bounds:** up to 150 submitted statements. Statements beyond
  that are reported as not compared, which makes the result INCOMPLETE unless
  something was ALTERED.
- **Source size:** up to 800 source sentences.
- **NLI:** up to 240 calls per check, within the 300 / 1,200-character input
  limits of `NLIService`.
- **Rule coverage:** the Bangla rules (negation forms, future endings, number
  referents, case markers) are curated and incomplete. Complex attribution,
  coreference and implicit qualifiers can still need expert review.
- **NLI accuracy:** the NLI model's Bangla accuracy is not established. Tests
  use deterministic fakes and pin the policy, not model accuracy. Before
  claiming accuracy, evaluate on held-out labelled Bangla pairs with the real
  local models. Report false ALTERED, missed alterations and the INCOMPLETE
  rate.
