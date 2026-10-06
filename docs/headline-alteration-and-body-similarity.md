# Headline Alteration, body similarity and photo-card extraction

Pipeline version `v4.0-headline-title-body-scores` (2026-10-05). This document
describes the implemented behaviour; the code references are authoritative.

## 1. Pipeline

```
S01 normalise → S02 reuse lookup → S03 queries → S04 search → S05 fetch → S06 extract → S07 rank
→ S08 source correspondence → S09 headline alteration → S10 body similarity
→ S11 date verification → S12 result assembly → S13 persistence / cache / delivery
```

| Stage | File | Decides | Reads |
|---|---|---|---|
| S08 | `pipeline/stages/s08_source_correspondence.py` | `source_status`, selected source article | headline, candidate titles, passages discussing the claim, search accounting |
| S09 | `pipeline/stages/s09_headline_alteration.py` | `content_status` (MATCHED / ALTERED / null), `headline_check_status` | claim headline, selected source **title** only |
| S10 | `pipeline/stages/s10_body_similarity.py` | four body scores (no verdict) | submitted body, selected source body |
| S11 | `pipeline/stages/s11_date_verification.py` | `date_status` | the user's claimed date, the report's `datePublished` |
| S12 | `pipeline/stages/s12_result_assembly.py` | correspondence strength, reasoning | outputs of S08–S11 |
| S13 | `pipeline/stages/s13_result_persistence.py` | — (stores, caches, notifies) | the assembled result |

Critical stages: S01, S08, S12, S13.

## 2. Source correspondence (S08)

A candidate corresponds when its title is near-identical to the headline
(LaBSE similarity ≥ `THRESHOLD_CORR_HEADLINE_SIM_ALONE`, 0.85), or when the
similarity is at least 0.72 / 0.55 **and** the claim's own keywords are found in
the title (≥ 0.50) or in the passages that discuss the claim (≥ 0.60). Shared
topic, person or country alone never corresponds. The first STRONG candidate
(else the first PLAUSIBLE one) becomes the selected source. An adequate search
with no corresponding report is `NOT_FOUND`; a failed or inadequate search or
failed retrieval is `INCOMPLETE`.

## 3. Headline Alteration (S09, `analysis/headline_comparison.py`)

Same rule for photo cards, headline-only claims and headline + body claims.
The source body, its passages, body similarity and body-derived NLI are never
inputs.

1. Missing title → no verdict, `SOURCE_TITLE_MISSING`.
2. **Exact match → MATCHED immediately.** Normalisation for this step only:
   Unicode NFC, zero-width characters removed (U+200B, U+2060, U+FEFF), runs of
   whitespace collapsed, and one trailing `।`/`.`/`!`/`?` removed. Names,
   numbers, negation, quotes and internal punctuation are kept.
3. Otherwise both assessments always run:
   * deterministic rules (`analysis/material_differences.py`): numbers, date
     words, negation, planned vs completed, quantifier scope, subject–object
     role reversal, allegation stated as fact, denial removed, named entities
     the title does not carry (when NER is usable);
   * semantic assessment: `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` NLI
     title ⇒ headline and headline ⇒ title, plus LaBSE cosine.
4. Verdict:
   * any material difference → **ALTERED** (each difference quoted);
   * same words in the same order (punctuation/spacing only) → **MATCHED**;
   * semantic equivalence (title ⇒ headline entailment ≥ 0.80, contradiction
     ≤ 0.20, LaBSE cosine ≥ 0.70) → **MATCHED**;
   * semantic divergence (contradiction ≥ 0.70, or entailment < 0.50 while the
     headline carries content words the title does not) → **ALTERED**
     (`main_point`);
   * NLI unavailable → no verdict, `MODEL_UNAVAILABLE`;
   * otherwise → no verdict, `UNDETERMINED`.

"No conflict found" is never a reason for MATCHED. Source not found and a
failed search give no headline verdict (`SOURCE_NOT_FOUND` vs
`SOURCE_CHECK_INCOMPLETE`).

Regression case (must be ALTERED; covered by
`tests/unit/test_headline_comparison.py`, including a test against the real
local models):

* claim: ফার্নান্দেজই পর্তুগালের ‘সবচেয়ে বড় প্রতীক’, বললেন রোনালদো
* title: রোনালদো বললেন, পর্তুগালের হয়ে শিরোপা ক্লাবে জেতা সব ট্রফির চেয়ে বড়

Threshold check on the deployed models (22 hand-written Bangla pairs): every
faithful paraphrase/reordering had title ⇒ headline entailment ≥ 0.88; every
meaning change had ≤ 0.32 except a subject–object swap (0.98), which the
deterministic role rule catches. This is a sanity check, not a validated
accuracy benchmark.

## 4. Body similarity (S10, `analysis/body_similarity.py`)

Only when the claim has a body and a corresponding source report was found.
Each metric is computed independently; a failing metric is unavailable with a
reason and the others are kept. Unavailable is never 0.

| Metric | Definition | Text used |
|---|---|---|
| `tfidf_cosine` | cosine of TF-IDF vectors; TF = count / length; IDF = ln((1+2)/(1+df)) + 1 over the two documents | content words (stop-words removed; numbers, negation, quantifiers kept) |
| `jaccard` | \|unique words in both\| / \|unique words in either\| | all normalised word tokens |
| `normalized_levenshtein` | 1 − edit_distance / max(len_a, len_b) (code points) | NFC, zero-width removed, whitespace collapsed; first 20,000 characters, `truncated` recorded |
| `semantic_cosine` | LaBSE (`sentence-transformers/LaBSE`) embedding cosine; claim body and source body split into ≤450-character sentence chunks (≤120 / ≤200 chunks, truncation recorded); each claim chunk takes its best source chunk; mean weighted by claim-chunk length | raw text |

LaBSE is reused because it already serves the application and supports
Bangla. BanglaBERT is not used for this score: it is not a sentence-embedding
model, so its raw vector cosine is not a meaningful similarity. The score is an
embedding cosine, not BERTScore. Its raw range is [-1, 1] (`raw_value`); the
displayed `value` is max(0, raw).

The scores are not part of any verdict. The UI shows each with its range,
a short explanation and a descriptive band (high ≥ 75 %, moderate 40–74 %,
low < 40 %).

## 5. Photo-card extraction (`photocard/claim_extraction.py`)

The user submits the image only (revised 2026-10-06; OCR and every fallback
were removed).

1. The original image goes to Gemini (`photocard/gemini_image_extractor.py`)
   together with the currently active verified sources and their aliases.
   Headline and printed date are transcribed exactly; the source must be
   identified from visible evidence (name, logo, alias) and returned as one of
   the offered canonical ids (schema `enum`), never guessed. Text in the image
   is treated as data.
2. At most 9 requests: 3 batches of 3 (`GEMINI_ATTEMPTS_PER_BATCH`,
   `GEMINI_BATCHES`, both capped at 3), backoff 1 s / 2 s inside a batch and
   a 10 s pause (`GEMINI_BATCH_PAUSE_SECONDS`) after a failed batch. Retried:
   timeouts, network errors, HTTP 429/5xx, malformed or schema-invalid output.
   HTTP 400/401/403/404 stops immediately. The first success stops the loop.
3. No successful response → the submission fails with a "temporarily
   unavailable, submit again later" message; no verification.
4. A successful response without a headline or without an active verified
   source → the submission fails with a "no valid headline or recognized
   outlet" message; not retried; no verification. A missing date is not a
   failure.
5. Otherwise the headline, the identified source and the printed date
   (`photocard/card_date.py`; only a complete day-month-year, never guessed)
   become the submission's headline, claimed source and claimed date - one
   representation, used exactly like a typed claim's values.

`photocard_extractions` stores the image key, `status`, `failure_code`,
`model_version`, `attempts` and `extraction_details` (per-attempt outcomes,
the raw response, the parsed date).

## 6. Search policy

Outlet-own ("internal") search runs for every source with a configured
`internal_search_url`, and Google (PyGoogleNews) runs for every publisher.
S03 builds up to six queries: headline, all keywords, first 3 keywords, first
4 keywords (when available), plus dated headline/all-keyword variants.

## 7. Persistence, reuse and legacy rows

`verification_results` stores `content_status` (MATCHED / ALTERED / null),
`headline_check_status`, `headline_exact_match`, `body_comparison_status`, the
correspondence measurements and `analysis_details` (headline detail with
differences and semantic scores, body report, date, search, timings). The
expert queue reads the same blob.

A result is reused only if it still exists in the database, has the current
pipeline version, is an original computation (not a copy of another result), a
completed source check, a headline verdict when the source is confirmed, no
INCOMPLETE date and no unavailable body scores. There is no age limit and no
"check again for updated evidence" option: an identical claim is always
answered with its saved result; once the original is deleted it is verified
afresh. Rows written before this version (no
`headline_check_status`) load with `legacy_result = true` and their old content
verdict is not shown as a headline verdict.

Migration `c7e2a9d4f1b3` removed every submission and its dependent rows
(results, jobs, articles, queries, extraction records, expert reviews,
multimodal analyses, result deliveries, submission notifications) and left
users, sources, voting configuration, credibility tiers, expert profiles and
tokens unchanged.

## 8. Limitations

* NLI and NER accuracy on Bangla has not been benchmarked on labelled data;
  the thresholds above were sanity-checked, not validated.
* The NER rule misses names fused with an emphatic particle (ফার্নান্দেজই); the
  semantic assessment still covers such cases.
* Gemini transcription is not assumed to be perfect; users and experts see the
  image beside the extracted headline.
