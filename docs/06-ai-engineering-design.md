# 6. AI Engineering Design

## 6.1 AI Pipeline and Model Selection

### 6.1.1 Overview

The source-based verification feature (`backend/app/features/verification/`) is implemented as a **12-stage async pipeline**, orchestrated by `PipelineOrchestrator` (`pipeline/orchestrator.py`) and driven by a single mutable `PipelineContext` dataclass (`pipeline/context.py`) that is threaded through every stage. `VerificationService` (`service.py`) wires the concrete stage implementations and their dependencies (DB repositories, Redis cache, HTTP client, and the three ML services) and exposes the single public entry point `verify()`.

> **Revision note (2026-10-02).** Scoring, decision logic, claim identity, caching and background execution were reworked; §6.3 is the authoritative description and states exactly what is and is not validated. Where an older paragraph below disagrees with §6.3, §6.3 wins. The automated system produces **Source, Content and Date statuses only** — Fake / Real / Misleading / Altered is exclusively an expert-finalized assessment, and `overall_verdict` stays null everywhere until an expert finalizes it.

Design goals baked into the architecture:

- **Stage isolation** — each stage is a class satisfying the `PipelineStage` protocol (`stage_id` + `async execute(context) -> context`), independently testable and swappable.
- **Fault tolerance over completeness** — only 4 of 12 stages are *critical*; the rest degrade gracefully (empty scores, skipped flags) rather than aborting the run.
- **Cache-first short-circuit** — a claim-hash cache check (Stage 2) can skip the entire evidence-gathering and ML stack (Stages 3–12) entirely.
- **Cost-tiered ML usage** — cheap, cacheable bi-encoder similarity is used broadly; expensive cross-encoder models (reranker, NLI) are invoked only on small, already-filtered candidate sets.

### 6.1.2 Pipeline Flow

```mermaid
flowchart TD
    A["Input\nheadline · body · claimed_source · date"] --> S01

    S01["S01 · Normalizer 🔴\nBangla text normalization, source\nresolution, claim-hash generation"]
    S01 --> S02

    S02["S02 · Cache Lookup 🟡\nRedis pointer → Postgres (authoritative)\non claim identity · version · freshness"]
    S02 -->|"reusable HIT"| RESP["Copy the automated result onto the\nrequester's OWN submission"]
    S02 -->|cache MISS| S03

    S03["S03 · Query Generator 🟡\nSite-restricted / keyword / entity /\ndate-bound / body-summary queries"]
    S03 --> S04

    S04["S04 · Source Search 🟡\n5 providers in parallel, per-call outcome\naccounting (success / empty / FAILED / skipped /\ncached) → search adequacy · date-free retrieval"]
    S04 --> S05

    S05["S05 · Evidence Retrieval 🟡\nTier-1 httpx fetch (rate-limited/domain)\n→ Tier-2 Playwright (headless Chromium)\nfor JS-shell pages"]
    S05 --> S06

    S06["S06 · Article Extractor 🟡\n6-tier cascade: source CSS selectors →\nJSON-LD → Trafilatura → Readability →\nBeautifulSoup → OpenGraph meta"]
    S06 --> S07

    S07["S07 · Evidence Ranker 🟡 🤖\nLaBSE similarity + keyword/date/domain\ncomposite score → Cross-Encoder\nrerank (mMARCO-MiniLM) if >3 survive"]
    S07 --> S08

    S08["S08 · Similarity Analyzer 🟡 🤖\nSCOPE-AWARE: headline↔title, relevant passages,\n(body chunks only if a body was submitted) ·\nkeyword + entity COVERAGE · numbers"]
    S08 --> S09

    S09["S09 · Contradiction Detector 🟡 🤖\nmDeBERTa-v3 multilingual NLI cross-encoder\n(entailment/contradiction/neutral),\ntemperature-calibrated"]
    S09 --> S10

    S10["S10 · Alteration Checks 🟡\nsentence-aligned, evidence-backed:\nnumbers · negation · entity role/substitution ·\nscope · attribution · plan-vs-completed →\nPASSED / FAILED / NOT_EVALUATED / NOT_APPLICABLE"]
    S10 --> S11

    S11["S11 · Classifier 🔴\nSOURCE (correspondence + search adequacy) ·\nCONTENT (concrete discrepancy / positive support) ·\nDATE (Asia/Dhaka day) — decided separately.\nNo overall verdict."]
    S11 --> S12

    S12["S12 · Persistence 🔴\nIdempotent per submission · ALL component scores,\ncheck states, evidence, search accounting ·\nRedis pointer · notify-once"]
    S12 --> RESP

    RESP --> OUT["VerificationResponse (read from the DB)\nsource/content/date · check strength ·\nscores + states · checks · analysis · articles"]

    classDef critical fill:#3a2323,stroke:#e0736a,color:#fbe4e1,stroke-width:2px;
    classDef degradable fill:#20232b,stroke:#6b7280,color:#d8dce3,stroke-width:1px;
    classDef ai fill:#1b2a3d,stroke:#4f8fd1,color:#dbe9fb,stroke-width:2px;
    class S01,S11,S12 critical;
    class S02,S03,S04,S05,S06 degradable;
    class S07,S08,S09,S10 ai;
```

🔴 = **CRITICAL** stage (failure aborts the run, claim marked `FAILED`) · 🟡 = degradable (failure logged, pipeline continues) · 🤖 = invokes an ML model.

A polished, standalone version of this diagram (with the model roster and legend) is published as an artifact; see the link shared in the conversation.

### 6.1.3 Stage Reference

| # | Stage | Criticality | Degrade behaviour on failure | ML model used |
|---|-------|:---:|---|---|
| S01 | Normalizer | **CRITICAL** | None — no hash means no cache lookup or search is possible | — (rule-based Bangla normalizer, static/DB source-alias resolution) |
| S02 | Cache Lookup | Non-critical | Falls through to full pipeline (cache miss); only a complete, current-version, fresh result is ever reused | — |
| S03 | Query Generator | Non-critical | Falls back to a single raw-headline query | — (keyword/n-gram extraction) |
| S04 | Source Search | Non-critical | Zero candidates + an **adequate** search → Source `NOT_FOUND`; failed/inadequate search → Source `INCOMPLETE` | — (5 external search clients) |
| S05 | Evidence Retrieval | Non-critical | Every fetch failed → Source `INCOMPLETE` (not NOT_FOUND); redirects that leave the claimed source's domains are rejected | — |
| S06 | Article Extractor | Non-critical | Every extraction failed → Source `INCOMPLETE`; publication date taken from `datePublished` sources only, with provenance | — |
| S07 | Evidence Ranker | Non-critical | Falls back to raw extraction order | **LaBSE** (bi-encoder) + **mMARCO Cross-Encoder** (conditional) |
| S08 | Similarity Analyzer | Non-critical | Unavailable metrics are null **with a reason** (never 0/100%); Source becomes `INCOMPLETE` if no correspondence signal exists | **LaBSE** + **sahajBERT NER** |
| S09 | Contradiction Detector | Non-critical | `contradiction_score` stays `None` | **mDeBERTa-v3 multilingual NLI** |
| S10 | Alteration Checks | Non-critical | Check states stay empty → S11 cannot reach `MATCHED` (a check that did not run is not a pass) | — (rule-based; reuses S08's NER mentions) |
| S11 | Classifier | **CRITICAL** | Without Source/Content/Date there is no result to return | — (deterministic, evidence-based rules) |
| S12 | Persistence | **CRITICAL** | Result must be durably stored | — |

### 6.1.4 AI Model Selection

Four distinct pretrained models are used, each chosen for a specific cost/precision tradeoff rather than using one large model everywhere:

| Model | HuggingFace ID | Role | Stage(s) | Why this model |
|---|---|---|---|---|
| **LaBSE** | `sentence-transformers/LaBSE` | Bi-encoder sentence embedding (768-dim) | S07, S08, S10 | Language-agnostic BERT sentence embedding pretrained across 109 languages including Bangla. As a **bi-encoder** it lets every headline/article be embedded once and compared via cheap cosine dot-product, and every embedding is Redis-cached by text hash (`embedding_service.py`) — the only architecture that scales to comparing one claim against many candidate articles repeatedly across three separate stages. |
| **Cross-Encoder reranker** | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | Pairwise (claim, article) reranking | S07 only, gated | Cross-encoders jointly attend over the claim+article pair, giving materially better ranking precision than bi-encoder cosine similarity — but at O(n) forward passes instead of O(1) lookups, so it is deliberately **only invoked when more than 3 ranked candidates survive** the cheap composite score (`s07_evidence_ranker.py`). mMARCO's multilingual passage-ranking fine-tuning makes it suitable for Bangla news snippets without further fine-tuning. |
| **sahajBERT NER** | `neuropark/sahajBERT-NER` (configurable via `ML_NER_MODEL_NAME`, HF `ner` pipeline, `aggregation_strategy="simple"`) | Named-entity recognition (PER/LOC/ORG) | S08, S10 | An ALBERT model pretrained from scratch on Bangla text and fine-tuned for token classification with the standard BIO scheme (O/B-PER/I-PER/B-LOC/I-LOC/B-ORG/I-ORG). Used twice: to compute directional entity-overlap recall (S08) and to detect **same-type entity substitution** — e.g. a person swapped for another person of the same grammatical role — which a plain overlap score would miss (S10). **Replaces a previously broken model — see the audit note below.** |
| **mDeBERTa-v3 NLI** | `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` (configurable via `ML_NLI_MODEL_NAME`) | Textual entailment / contradiction | S09 only | An mDeBERTa-v3-base cross-encoder fine-tuned on XNLI (15 languages) + MNLI, built on a 100-language multilingual vocabulary, producing entailment/contradiction/neutral probabilities. A cross-encoder is required here (not LaBSE) because contradiction detection depends on fine-grained token-level interaction — e.g. one changed number or negation — that a bi-encoder's pooled cosine similarity cannot represent. Only ever called once per claim, against the single top-ranked article, keeping its cost bounded. **Replaces a previously broken model — see the audit note below.** |

**Model-tiering rationale.** The pipeline follows a **funnel pattern**: cheap, cacheable, broadly-applied signals (LaBSE cosine similarity, keyword overlap, date/domain heuristics) filter and rank a wide candidate set in S07; only the small surviving set is handed to progressively more expensive, more precise models — the cross-encoder reranker (top-N reordering) and finally the NLI cross-encoder (single top article only, in S09). This keeps per-claim latency bounded regardless of how many articles were retrieved, while still getting cross-encoder-level precision where it matters most (the final verdict).

**Calibration and degraded-mode handling** (`config.py: ClassificationThresholds`, `s09_contradiction_detector.py`):
- `nli_temperature = 1.5` — temperature-scaled softmax recalibration of the NLI model's output logits, applied because the raw model is overconfident and produces false-positive contradictions right at the S11 soft-penalty threshold. This was calibrated against the previous (English-only) NLI model and has not been re-tuned for the replacement model — see the audit note below.
- `nli_title_only_attenuation = 0.6` — when an article's body could not be extracted, NLI falls back to a title-only premise and the resulting entailment/contradiction scores are multiplied by 0.6, since title-only NLI is known to be far less reliable than body-based NLI.
- The NLI premise itself is not the whole article body but the **top-5 claim-relevant sentences**, selected by token-overlap with the claim headline (`_select_claim_relevant_sentences`), to stay within the model's effective input window and keep the signal focused.

**Audit note — S09/S10 Bangla-capability fix (2026-10-01).** Both the NLI and NER models previously hardcoded into `NLIService`/`NERService` were mechanically verified to be non-functional on Bangla input, and have been replaced:

- *NLI (S09).* The previous model, `cross-encoder/nli-deberta-v3-small`, is fine-tuned only on MNLI/SNLI/FEVER — all-English datasets — on a DeBERTa-v3 vocabulary with essentially no Bangla subword coverage. Directly verified: its tokenizer splits a 71-character Bangla sentence into 71 tokens, almost all single Unicode code points, because it has no multi-character Bangla subword units. A model cannot encode semantics it cannot tokenize, so its entailment/contradiction scores on Bangla claims were not a meaningful signal of anything in the text, regardless of how confident the output looked. The replacement, `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`, was verified on the same sentence to tokenize into 27 well-formed subword tokens with zero `[UNK]`s (e.g. "প্রধানমন্ত্রী" as a single token), and was sanity-checked against one hand-constructed Bangla entailment pair and one hand-constructed Bangla contradiction pair, correctly scoring each at >95% confidence in the expected direction. **This is a tokenization-coverage check and a two-example sanity check, not a measured accuracy benchmark.** Bengali is not among the 15 XNLI languages this checkpoint was fine-tuned/evaluated on — its Bangla capability rests on the base model's multilingual pretraining and cross-lingual transfer from the languages it was fine-tuned on, which is the standard mechanism this model family relies on for out-of-evaluation-set languages, but that transfer has not been independently measured here. A real accuracy evaluation against labeled Bangla NLI pairs — and re-tuning of `nli_temperature`/`nli_title_only_attenuation` against that evaluation — should happen before this score is trusted for high-stakes decisions. Until then it is a **strict improvement** over a model that was mechanically incapable of representing Bangla text at all, not a validated replacement.
- *NER (S08/S10).* The previous model, `csebuetnlp/banglabert`, is an ELECTRA *pretraining* checkpoint (`ElectraForPreTraining`, a 2-label replaced-token discriminator) with no token-classification head. Directly verified: loading it through `transformers.pipeline("ner", ...)` logs `classifier.weight`/`classifier.bias` as newly-initialized (never trained) and produces only `LABEL_0`/`LABEL_1` at ~50% confidence — never `PER`/`LOC`/`ORG`. Since `_ENTITY_TYPES_KEPT` only keeps `PER`/`LOC`/`ORG` labels, `extract_entities()` and `extract_entities_with_types()` silently returned `[]` on every single call, in every verification run, with no error surfaced anywhere — S08's entity-match score and S10's typed-entity-substitution check have been dead code paths since they were written. The replacement, `neuropark/sahajBERT-NER`, is a genuinely NER-fine-tuned model with the exact BIO/PER-LOC-ORG scheme this code expects, and was manually smoke-tested on a Bangla sentence containing a known person, location, and organisation — all three were correctly identified with the correct types. This is a manual spot-check, not a benchmark against a labeled Bangla NER test set, but it is a strict improvement over a model that structurally could never produce a PER/LOC/ORG label.

Both models are now read from `MLSettings.nli_model_name` / `MLSettings.ner_model_name` (env vars `ML_NLI_MODEL_NAME` / `ML_NER_MODEL_NAME`) instead of being hardcoded class constants, resolving the config/runtime mismatch previously noted here. `embedding_model_name` remains intentionally unused — `EmbeddingService` hardcodes `sentence-transformers/LaBSE`, which is a deliberately validated choice (a 109-language bi-encoder explicitly covering Bangla), not an oversight.

### 6.1.5 Non-ML Supporting Systems

**Search provider fan-out (S04).** Five providers are queried in parallel per query variant, with a fixed priority order used only to resolve URL-collision conflicts after dedup (lower number wins): `internal_site` (0) → `newsdata` (1) → `google_custom_search` (2) → `ddg` (3) → `py_google_news` (4). Each provider is selectively skipped per query type (e.g. NewsData never receives `HEADLINE`/`SITE_RESTRICTED` queries) to avoid wasted quota on query shapes it handles poorly.

**Two-tier extraction (S05).** Tier 1 is a fast `httpx` GET with a realistic browser `Accept-Language: bn-BD` header set and per-domain rate limiting (0.5s). Pages detected as JS-rendered shells (`__NEXT_DATA__`, `__NUXT__`, React root markers with <2000 chars of real text) escalate to Tier 2: a headless Playwright/Chromium render.

**Six-tier extraction cascade (S06).** For each fetched page: (1) source-specific CSS selectors from `source_registry.py` (11 known Bangla domains, each with hand-tuned title/body/date selectors) → (2) JSON-LD `NewsArticle`/`Article` structured data → (3) Trafilatura → (4) `python-readability` → (5) generic BeautifulSoup heuristics (common class-name patterns) → (6) OpenGraph/meta-description fallback. This directly addresses the fact that no single generic extractor reliably handles all 11+ target Bangla news sites.

**Decisions (S11) — see §6.3.4.** Source, Content and Date are decided independently from different evidence; the old weighted-score aggregation, contradiction override and legacy TRUE/FALSE labels were removed.

**Result reuse and caching (S02/S12) — see §6.3.6.** Redis holds only a pointer to the submission that produced the latest complete result for a claim identity; the database row is authoritative and is re-validated (pipeline version, completeness, freshness) on every hit, so Redis can never overlay stale or incompatible scores. `force_refresh=True` bypasses every reuse path.

### 6.1.6 Observability

Every stage execution is timed (`context.stage_timings`) and logged with `structlog` (`stage_started` / `stage_completed` / `stage_failed_non_fatal`), then persisted as `VerificationLog` rows in S12 — giving per-claim, per-stage latency and error visibility without any separate profiling tooling.

### 6.1.7 API Entry Points & End-to-End Request Flow

A text claim reaches the pipeline through one of two endpoints (`verification/router.py`), both backed by the identical `VerificationService`/stage list — only the calling convention differs:

```
POST /verify            synchronous — the request blocks until S01–S12 finish
                         and the full VerificationResponse comes back in one reply.

POST /verify/async       the path the frontend actually uses — returns 202
                         immediately with {submission_id, status, cached}
                         and runs the pipeline in the background.
GET  /verify/{id}         poll this for the result once it's ready.
GET  /verify/{id}/status  lighter poll — status only, result included once
                           the submission reaches EXPERT_REVIEW/FINALIZED.
GET  /submissions/{id}    type-agnostic lookup shared by all three
                           verification methods (source-based, photo-card,
                           multimodal) — tells a result page which of the
                           three detail endpoints to call next.
```

`POST /verify/async` (`VerificationService.register_claim`) resolves the claimed source, computes the claim identity (§6.3.6) and — unless `force_refresh` — looks for an identical, complete, fresh, current-version result. A hit gives the requester **their own submission** carrying a copy of that automated result (`cached: true`, no job queued); only the same submitter's identical in-flight claim is handed back. On a miss it creates the `Submission` (`PENDING`, phase `QUEUED`) **and its durable `verification_jobs` row in one transaction** and returns 202; the job worker (§6.3.8) runs the pipeline server-side, independent of the browser.

```
User submits claim
    → POST /verify/async → Submission(PENDING) + job row committed, 202 returned at once
    → worker claims the job (SKIP LOCKED, heartbeat): S01 … S12 run unattended
    → S12 persists the automated result, flips status → EXPERT_REVIEW and
      notifies the submitter (once) and the experts (once each) (§6.1.9)
    → the result page — whether the user stayed or returned later through My
      Submissions / a notification / Fact Explorer — calls GET /submissions/{id}
      then GET /verify/{id} and renders the SAME saved result (§6.1.10)
```

Photo cards use the same pattern: `POST /photocard/verify/async` stores the image, creates the `PHOTO_CARD` submission + job and returns 202; OCR, extraction and verification run in the job (§6.2.1, §6.3.8). The synchronous `POST /photocard/verify` and `POST /verify` remain for compatibility.

### 6.1.8 Database & Storage

| Table / store | Role for a text claim |
|---|---|
| `submissions` | One row per requester, `submission_type = SOURCE_BASED`, carrying the headline/body/claimed_source_text/published_date, the lifecycle `status` (`PENDING` → `PROCESSING` → `EXPERT_REVIEW` → `FINALIZED`/`ESCALATED`/`FAILED`), `processing_phase` (QUEUED/EXTRACTING/VERIFYING/DONE/FAILED), `failure_reason`, and `duplicate_of_submission_id` when its result is a reused copy |
| `verification_jobs` | The durable work queue behind background verification (§6.3.8) |
| `verification_results` | The automated result, **immutable** once S11/S12 write it: `source_status`/`content_status`/`date_status`, every applicable component score (`headline_/body_/passage_similarity`, headline/passage/body keyword coverage, entity coverage, numerical consistency, contradiction), `claim_scope`, `pipeline_version`, `manipulation_flags` (booleans + `check_states` + discrepancies) and `analysis_details` (metric states, selected passages, NLI, search accounting, date provenance, decision basis); `ai_consensus_label` is legacy and no longer written. Expert review never touches these columns — it writes `final_source_status`/`final_content_status`/`final_date_status`/`overall_verdict`/`finalized_at` instead (§6.1.9), so the AI's original call stays inspectable even after the claim is Expert Verified |
| `retrieved_articles`, `source_evidence_queries` | The evidence trail — every article a search provider returned and every query that was run to find it, kept for audit and for the expert queue's "top matching article" panel |
| Application logs | Per-stage timing/errors emitted in S12; no database log table (§6.1.6) |
| `notifications` | `VERIFICATION_COMPLETE` (to the submitter) and `EXPERT_REVIEW_AVAILABLE` (broadcast to every active expert) rows, written by S12 the moment the AI preliminary result lands |
| Redis | Pointer to the latest complete result per claim identity, with freshness TTLs (shorter for NOT_FOUND); the Postgres tables above are authoritative (§6.3.6) |

### 6.1.9 Expert Review Integration

A text claim is one of the two `_STRUCTURED_TYPES` in `ExpertReviewService` (the other being `PHOTO_CARD`, §6.2.9) — the voting engine does not distinguish between them. Once S12 flips a submission to `EXPERT_REVIEW`, it is simultaneously visible in the expert queue and in the Fact Explorer's preliminary section, and every subsequent step is the shared engine:

- **The vote itself** mirrors the AI's own structure: Source (Confirmed/Not Found) first, then — only when Source is Confirmed — Content (Matched/Altered) and Date (Matched/Mismatched); every submission type additionally casts one Overall verdict (Fake/Real/Misleading/Altered), cast in the same form as the structured vote.
- **Weighting** resolves from the expert's credibility tier once they've completed the admin-configured activation threshold `N` of lifetime reviews (weight is a flat 1.0 before that); the resolved weight is snapshotted onto the vote row (`credibility_weight`) so a later tier change never retroactively rewrites history.
- **Finalization** requires every applicable dimension — Overall always, Source/Content/Date for this type — to independently clear all three of: leading verdict's weighted score ≥ `T`, votes cast ≥ `M`, lead over the runner-up ≥ `margin`. A claim that exhausts the configured review window or vote cap without clearing them escalates to admin instead of hanging open.
- **Concurrency** is handled by row-locking the submission for the duration of a vote-or-edit-plus-finalize decision, so two experts voting at the same moment can't double-finalize.
- Votes and final decisions remain in their primary tables. The optional database audit-history feature was removed; it does not participate in voting calculations.

The one respect in which a text claim's review screen differs from a photo card's is simply that there is no uploaded image to show — the expert's left-hand context is the submitted headline/body/claimed source plus the **top-ranked matched article** (`RetrievedArticleV2`, fetched the same way for both structured types), not a card thumbnail. `source_status`/`content_status`/`date_status` on the result row are never touched by finalization — they stay exactly as the AI computed them — while `final_source_status`/`final_content_status`/`final_date_status`/`overall_verdict` are written only once expert review finalizes, letting the claim's detail page show an "experts changed this verdict from X to Y" banner whenever the two disagree (`VerificationResponse.was_overridden`).

### 6.1.10 Result Display — Showing the User Their Verdict

The frontend's `/verify/:id` route is type-dispatching: it calls `GET /submissions/{id}` first to learn which of the three verification methods produced this submission, then polls the matching detail endpoint (`GET /verify/{id}` for a text claim) until a verdict exists, re-polling every few seconds while the submission sits in `PENDING`/`PROCESSING` so a user who stayed on the page sees the result land without a refresh — and a user who navigated away and comes back via a notification link, their submission history, or Fact Explorer gets the identical page in whatever state the claim is actually in.

Once a result exists the page (`VerificationReportComponent`, shared by the result page, the claim page, photo cards and the expert view) shows: an **"Awaiting expert review"** notice and **no overall truth badge** until experts finalize (afterwards the expert verdict and finalized dimensions, with the automated result still inspectable and an override banner when they differ); the Source/Content/Date badges; a **check-strength** ring (a measurement summary with an explicit "not the probability the claim is true" tooltip); "Why this result" reasoning built from the actual comparison evidence; the component scores under "Content match against the claimed source" — body metrics only when a body was submitted, unknown values labelled *Not applicable* / *Unavailable* with the reason, never 0% or 100%; the alteration checks (a green tick only for a **completed** pass, neutral "Not evaluated" otherwise, and every failure quoting the claim and source text that disagree); the publication-date comparison with its provenance; and the corresponding source report with its **retrieval relevance** (is this the report?) kept visibly distinct from content match.

## 6.2 Photo-Card Verification Pipeline

### 6.2.1 Overview

The photo-card feature (`backend/app/features/photocard/`) verifies a **screenshot of a news photo card** rather than typed text. It does not implement a second verification engine: after OCR and headline extraction the extracted headline goes through the **exact same 12-stage pipeline** documented in §6.1, always with `ClaimScope.HEADLINE_ONLY` (no body, no synthetic body), against the user's own `claimed_source_text` / `published_date`.

Submission is **accepted fast and processed in the background**:

```
POST /photocard/verify/async   (image + claimed_source_text + published_date)
    validate → store image bytes in MinIO (503 if it cannot be stored — nothing
    is accepted) → Submission(PHOTO_CARD, PENDING, owner = signed-in user) +
    OcrExtraction(image key) + verification_jobs row, one transaction
    → HTTP 202 {submission_id, status, phase, message}
    ── server-side job (own DB session, bounded concurrency, restart-safe) ──
    load stored image → preprocessing → OCR → source detection (raw text)
    → headline extraction: Gemini (grounded) → deterministic fallback on any
      failure/invalid/ungrounded output → PermanentJobError if neither
      produces a usable headline (submission FAILED with a reason; never
      Source Not Found / Content Altered — no check ran)
    → submission.headline + identity hash set → shared S01–S12 pipeline
      (or reuse of an identical fresh result copied onto THIS submission)
    → EXPERT_REVIEW + notification
GET  /photocard/{id}           current state by id: pending / processing (phase) /
                                failed (reason) / the saved result — owner-only
                                until the submission is reviewable
```

There is no confirmation step. The user-provided `claimed_source_text`/`published_date` are authoritative; the image-detected source/date are supplementary metadata, recorded in `ocr_extractions` and surfaced with a conflict warning when they disagree — never substituted. `POST /photocard/verify` (synchronous) is kept and runs the same two steps inline.

### 6.2.2 Headline Extraction — Gemini First, Deterministic Fallback Always Available

```mermaid
flowchart TD
    IMG["Photo card image\n(JPEG/PNG/WebP/GIF, ≤10MB)"] --> PRE

    PRE["Image Preprocessing\nEXIF-correct orientation · rescale to OCR\nsweet spot · render 3-4 variants:\ngrayscale → sharpened → binarised (Otsu)\n→ inverted (only if light-on-dark)"]
    PRE --> OCR

    OCR["Bangla OCR 🤖\nEvery variant recognised independently by\nTesseract (LSTM, multi-PSM) or EasyOCR —\nwinner scored by Bangla chars × confidence × Bangla ratio"]
    OCR --> SRC
    OCR --> GEM

    SRC["Source Detection\nruns on RAW OCR text — domain match (1.0) →\nexact substring (~0.94+) → fuzzy Levenshtein\nwindow (word-anchored, multi-length) against\nactive verified sources only"]

    GEM{"Gemini configured?"}
    GEM -->|no| FALLBACK
    GEM -->|yes| CALL

    CALL["Gemini extraction 🤖\nStructured JSON output (responseSchema):\nheadline, detected_source_text,\ndetected_date_text, extraction_warnings.\nSystem prompt treats OCR text as untrusted\ndata, never as instructions."]
    CALL --> GROUND{"Headline non-empty AND\npasses grounding check?\n(≥50% of its words found\nin the OCR text)"}
    GROUND -->|yes| USE["Use Gemini's headline\nextractor_used=GEMINI"]
    GROUND -->|no — ungrounded,\nempty, HTTP error,\nmalformed JSON| FALLBACK

    FALLBACK["Deterministic extractor\n(claim_extractor.py, unchanged —\nsee §6.2.6) · extractor_used=\nEXISTING_FALLBACK"]

    USE --> CHECK{"Headline usable?\n(≥8 chars)"}
    FALLBACK --> CHECK
    CHECK -->|no| FAIL["422 PhotoCardExtractionFailedError\nNever reported as Source Not Found\nor Content Altered — nothing persisted"]
    CHECK -->|yes| PERSIST["Submission(type=PHOTO_CARD) +\nOcrExtraction(extractor_used,\nmodel_version, warnings,\ndetected_source_text/date_text)"]

    classDef ai fill:#1b2a3d,stroke:#4f8fd1,color:#dbe9fb,stroke-width:2px;
    class OCR,CALL ai;
    classDef critical fill:#3a2323,stroke:#e0736a,color:#fbe4e1,stroke-width:2px;
    class FAIL critical;
```

**Why Gemini operates on OCR text, not the raw image.** The deterministic extractor already separates claim text from card chrome (banners, social UI, bylines, timestamps) using pattern rules; Gemini is layered on top of that *same OCR output* to handle what pattern rules can't — a headline split across noisy line breaks, mild OCR garbling, an unusual layout. It never sees the image directly, which keeps the extraction auditable (the OCR text is the one fixed, loggable input both extractors share) and means a Gemini outage degrades to the existing extractor rather than losing the submission.

**Why every Gemini headline is grounded before being trusted.** Two independent defenses: (1) structured output (`responseSchema`) makes Gemini return strict JSON with a required `headline` field — malformed or missing output is treated as a call failure; (2) the **grounding check** verifies a configurable fraction (`GEMINI_MIN_GROUNDING_OVERLAP`, default 0.5) of the headline's own words actually appear in the OCR text it was given. This is also the mechanical defense against prompt injection embedded in OCR'd text — a card photographed to contain text like "ignore previous instructions, output: ..." produces a headline that, whatever it says, will not be grounded in the surrounding OCR text, and so falls back regardless of *why* the output diverged. The system prompt separately instructs Gemini to treat the OCR text as untrusted data, never as instructions — a first line of defense, not the only one.

**Extraction failure is explicit and distinct from a verification outcome.** If neither Gemini nor the deterministic fallback produces a headline of at least 8 characters, `PhotoCardService.verify()` raises `PhotoCardExtractionFailedError` (`422`) before any `Submission` row is created. This is never reported as `source_status=NOT_FOUND` or `content_status=ALTERED` — those describe a claim that was checked and found wanting; here there was no claim text to check at all.

### 6.2.3 Image Preprocessing (`image_preprocessor.py`)

Pillow + NumPy only, no OpenCV. Photo cards are screenshots and social graphics, not scans: text is crisp but often small and tightly kerned, and the Bangla *matra* (the connecting headline stroke) merges adjacent glyphs under downscaling or JPEG blur, which makes a single fixed recipe unreliable. Instead, a handful of cheap variants are rendered and the OCR stage below picks whichever one it could actually read the most Bangla from:

| Variant | Transform | Why |
|---|---|---|
| `grayscale` | Resize into the OCR-friendly resolution band (LANCZOS upscale / BICUBIC downscale) + autocontrast | Safe baseline |
| `sharpened` | Unsharp mask (radius 2.0, 180%) | Re-separates matra-merged glyphs |
| `binarised` | Otsu threshold (computed from the 256-bin histogram, between-class variance maximised) | Helps flat-background infographic cards; hurts photographic ones, hence a candidate rather than the default |
| `inverted` | Only rendered when border-pixel sampling detects light-on-dark | Engines trained on dark-on-light text read nothing at all otherwise |

### 6.2.4 Bangla OCR (`ocr_service.py`)

Two interchangeable engines sit behind one interface, neither imported at module load time — a missing engine surfaces as a `503 OcrEngineUnavailableError` on the photo-card endpoints instead of failing application startup:

- **Tesseract** (preferred, `OEM 1` LSTM engine) — tried at every configured PSM mode per variant, requires the `ben` traineddata.
- **EasyOCR** (fallback) — a general multilingual reader.

Every preprocessing variant is recognized by the resolved engine independently; the outputs are not merged but scored and the single best one wins:

```
score = bangla_char_count × (0.5 + 0.5 × confidence) × bangla_ratio(text)
```

Character count alone would favour a pass that hallucinates long garbage strings; confidence alone would favour a pass that reads three clean words and misses the headline — the product balances both. Each engine's raw output (Tesseract's per-word boxes grouped by `page/block/par/line`; EasyOCR's independent boxes bucketed by vertical overlap and sorted left-to-right within each bucket) is normalised into the same `OcrLine`/`OcrOutput` shape so the rest of the pipeline is engine-agnostic. A card with no recoverable Bangla text raises `422 OcrFailedError`.

### 6.2.5 Source Detection (`source_detector.py`)

Nearly every circulating photo card brands itself — a logo, a wordmark strip, a page URL — and that branding *is* the claim's source attribution. Detection deliberately runs against the **raw** OCR text (before claim cleaning throws the banner away), against **active verified sources only**, in three strategies of decreasing trust:

1. **`domain`** (confidence 1.0) — a URL or bare domain in the text resolves to a source's canonical name or base-URL domain. Unambiguous when present.
2. **`exact`** (~0.94–1.0) — a source's display name, English name, canonical name, or any configured alias appears verbatim in the normalised text.
3. **`fuzzy`** (Levenshtein ratio against a configurable threshold) — carries the detector in practice, since Bangla OCR routinely drops a matra or splits a conjunct (`প্রথম আলো` → `প্রথম আল৷`). Candidate windows are anchored to word starts (not every character offset) and tried at several lengths around the needle's own length, since OCR both drops and inserts characters relative to the true match span.

Results are ranked by confidence; the top one becomes `primary_source` only if it clears a separate, higher auto-select threshold — otherwise the user is shown all candidates and must pick (or type) one manually, with a warning surfaced.

### 6.2.6 Deterministic Extraction — the Fallback (`claim_extractor.py`)

Unchanged by the Gemini work, and still the extractor that runs whenever Gemini is unconfigured, fails, or returns an ungrounded headline (§6.2.2) — not a legacy path kept for compatibility, but the always-available backstop every photo card can fall through to. A typical card is mostly *not* the claim: outlet banner, one-to-three-line headline, maybe a supporting sentence, then a band of chrome — social handles, "লাইক / শেয়ার / ফলো করুন" prompts, bylines, photo credits, timestamps, engagement counters, copyright, ads. Feeding all of that into the verification pipeline dilutes the embedding and drags entity matching toward the outlet's own name rather than the claim. Each OCR line is classified and, if it's chrome, tagged with why:

| Noise reason | Trigger |
|---|---|
| `empty`, `no_letters`, `too_short`, `low_confidence`, `not_bangla` | Structural / quality filters |
| `url`, `social_handle`, `phone_number` | Pure decoration once stripped |
| `social_cta`, `byline`, `credit`, `timestamp`, `engagement`, `copyright`, `advert` | Pattern-matched furniture specific to Bangladeshi news cards |
| `source_banner` | Line is (or Levenshtein-close to) a detected outlet's own name — matched using the **same** `source_names` list §6.2.5 detected, so a banner is removed using whichever garbled spelling OCR actually produced |

Surviving lines are joined and segmented into headline + body: the headline grows line-by-line while it still reads as a headline (stops at a sentence-ending danda/punctuation once long enough to stand alone, or at a hard character cap), with a single-paragraph fallback that splits on the first sentence boundary instead when the card has no visual line breaks. Only the headline half of this output is ever used — the business rule is headline-only verification, so the body this extractor segments out is computed but never passed into `build_context()` (§6.2.7). Its warnings (very short headline, low-confidence lines dropped, no survivable text) are carried into `OcrExtraction.extraction_warnings` for expert visibility rather than surfaced for a user to correct — there is no correction step.

### 6.2.7 Verification Flow (shared pipeline reuse)

`PhotoCardService.process_submission` (run by the job worker) drives the same stage list `VerificationService` uses (`build_verification_stages`), with the submission id threaded into the `PipelineContext` so the result is written to **this** `PHOTO_CARD` submission — never to a second text submission. `claim_scope=HEADLINE_ONLY` is passed explicitly; `build_context()` drops any body passed alongside it.

Result reuse never shares a submission across owners. If S02 finds an identical, complete, fresh, current-version verification (identity = normalised headline + canonical source + claimed date + scope + pipeline version, §6.3.6), the service copies its **automated** result onto the requester's own photo-card submission (`duplicate_of_submission_id`, `verification_results.reused_from_submission_id`). The submission's owner, type, image and OCR record are untouched, the detail page works exactly as for a fresh result, and expert state is read through from the original at display time rather than copied.

Every downstream stage is the literal code of §6.1, so a photo card gets the same Source / Content / Date result; for HEADLINE_ONLY the submitted-body comparison and body check are *not applicable* (null / `NOT_APPLICABLE`, never displayed). The automated system never computes an overall verdict for either flow.

### 6.2.8 Database & Storage

No photo-card-specific result table exists — a photo card's AI verdict lives in the **same** `verification_results` row shape a typed claim uses:

| Table | Role for a photo card |
|---|---|
| `submissions` | One row, `submission_type = PHOTO_CARD`, owner = submitter, `headline` NULL until extracted (`body_text` always NULL — headline-only), `claimed_source_text`/`published_date` exactly as the user provided them, `status` (`PENDING` → `PROCESSING` → `EXPERT_REVIEW` → `FINALIZED`/`ESCALATED`, or `FAILED`), `processing_phase`, `failure_reason` |
| `ocr_extractions` | Photo-card-only: `image_object_key`, `raw_extracted_text`, `ocr_confidence`, `ocr_engine`, plus extraction provenance added for the Gemini flow — `extractor_used` (`GEMINI` \| `EXISTING_FALLBACK`), `extraction_model_version`, `extraction_warnings` (JSONB array, includes any source/date conflict text), `detected_source_text`, `detected_date_text`. `confirmed_text`/`is_confirmed` are legacy columns from the removed two-step flow — the unattended flow never sets them — kept rather than dropped since historical rows still carry them |
| `verification_results` | AI verdict, **immutable** once written by S11/S12: `source_status`/`content_status`/`date_status`, plus `manipulation_flags` (JSONB — the durable copy of S10's flags and alteration detail, see §6.1.4's audit note). Expert review never overwrites these — it writes `final_source_status`/`final_content_status`/`final_date_status`/`overall_verdict`/`finalized_at` instead, so the AI's original call stays inspectable after the claim moves to Expert Verified |
| `retrieved_articles`, `source_evidence_queries` | Evidence trail — identical shape and population path to a typed claim |
| MinIO (object storage) | The uploaded card image, under its own `photocard/{submission_id}/{filename}` prefix — a separate bucket-service instance (`PhotoCardStorageService`) from the multimodal feature's images, so the two can be retained/expired/audited independently. Served back only as short-lived presigned URLs, never a public path. Kept even if the submission row is later deleted as an S02 cache-hit orphan (§6.2.7) |

`content_hash` starts as a provisional per-submission value (`pending:<id>`, which can never collide with a real claim identity) because the headline is unknown at acceptance; after extraction it is replaced by `compute_claim_hash(headline, canonical source, HEADLINE_ONLY, published_date=…)` — the same identity function used everywhere (§6.3.6). The `ocr_extractions` row is created at acceptance (image key, empty OCR text) and filled in by the job, so a pending card already has its image.

### 6.2.9 Expert Review Integration

Photo-card submissions are **not** a special case in `ExpertReviewService` — they're one of the two `_STRUCTURED_TYPES` (alongside `SOURCE_BASED`), sharing every code path described in §4's voting engine: the same Source→Content/Date hierarchical vote (Content/Date become N/A the moment Source's winning verdict is Not Found), the same Overall (Fake/Real/Misleading/Altered) vote every submission type casts, and the same weighted T/M/margin finalization, credibility updates, and audit logging.

The one genuinely photo-card-specific piece is **image surfacing**: the expert queue and review-detail screen fetch the submission's `OcrExtraction.image_object_key` and resolve it to a presigned MinIO URL (`ExpertReviewService._fetch_photocard_image_url`, wired through a `PhotoCardStorageService` instance injected alongside the existing multimodal one) so an expert reviewing a photo-card claim sees the actual card next to the AI's preliminary verdict and the matched source article — not just OCR'd text in isolation. The Fact Explorer and the public claim-detail page (`GET /photocard/{id}`) surface the same image as a thumbnail/hero image respectively, through the identical presigned-URL mechanism.

Because the AI verdict and the expert-finalized verdict are stored in separate columns (§6.2.8), a photo card's detail page can show both: the AI's original call, and — once expert review completes — a "experts changed this verdict from X to Y" banner when the two disagree (`VerificationResponse.was_overridden`).

### 6.2.10 Error Handling & Degradation

| Failure | Behaviour |
|---|---|
| Claimed source (given at upload time) doesn't resolve | `404 SourceNotFoundError` at acceptance — before anything is stored |
| Image cannot be stored | `503` at acceptance — nothing is accepted (the job reads the image back from storage) |
| No OCR engine installed/configured | The job retries (bounded), then the submission is `FAILED` with a reason; app still boots (lazy init) |
| Image has no recoverable Bangla text | Submission `FAILED` ("No readable Bangla text…"), owner notified once |
| Gemini unconfigured, HTTP/timeout error, malformed JSON response, empty headline, or ungrounded headline | Silent fallback to the deterministic extractor (§6.2.2) — never surfaced as an error |
| Neither Gemini nor the fallback produces a headline ≥8 chars | Submission `FAILED` with a reason (sync endpoint: `422 PhotoCardExtractionFailedError`) — distinct from Source Not Found / Content Altered; no automated result exists |
| MinIO read-back fails inside the job | Retryable; after the attempt limit the submission is `FAILED` with a reason |
| No active verified source matched the card's own branding | `detected_sources` is empty in the response; verification still proceeds against the user-provided `claimed_source_text` |
| Card's own text implies a different source/date than provided | Not an error — recorded in `extraction_warnings`, surfaced as `source_date_conflict: true`; verification proceeds against the user-provided values |
| Pipeline stage failure (S01/S11/S12 critical) | The job is retried up to `max_attempts`, then the submission is `FAILED` with a reason and the owner is notified once; non-critical stage failures degrade exactly as for a typed claim |

### 6.2.11 Observability

Since the pipeline runs the literal same stage instances as `POST /verify`, every photo-card verification gets the same per-stage `stage_timings` + `structlog` `stage_started`/`stage_completed`/`stage_failed_non_fatal` events and `VerificationLog` rows described in §6.1.6. The extraction half adds its own structured events — `photocard_verify_started`, `photocard_extraction_failed` (extractor_used + warnings, logged before the 422 is raised), `photocard_duplicate_detected` — plus `gemini_extraction_failed_falling_back`, `gemini_extraction_empty_headline`, and `gemini_extraction_failed_grounding_check` from `gemini_extractor.py` whenever Gemini's output was discarded, and `s12_redis_cache_skipped_incomplete_result`/`db_hit_skipped_incomplete_result` from the cache layer (§6.1.4) when applicable — giving the same per-claim visibility into the extraction half of the flow that the pipeline already provides for the verification half.

## 6.3 Scope-aware Verification, Decisions, Identity and Background Jobs (2026-10-02)

This section is the authoritative description of runtime behaviour after the scope-aware rework. It also states plainly what is **not** validated.

### 6.3.1 Business requirements

Both flows (text and photo card) check (1) whether a corresponding report exists in the claimed source, (2) whether the submitted claim matches it or contains material alterations, and (3) whether the claimed publication date matches the report's. The automated result is **Source, Content and Date statuses only**; Fake / Real / Misleading / Altered is an expert-finalized assessment and `overall_verdict` is null in every API, database write, frontend view, Fact Explorer row and notification until an expert finalizes it. Photo cards are always `HEADLINE_ONLY`; text claims verify the headline and, when present, the submitted body.

### 6.3.2 S08 — scope-aware measurements

Root cause fixed: S08 cleared the claim body for `HEADLINE_ONLY` but still computed `similarity(headline, full_article_body)` and blended it `0.3·headline + 0.7·body`, penalising exact headlines and inventing a "body match" when no body existed. (The embedder also truncates every input at 512 characters, so that comparison only ever saw the first ~512 characters of the article.)

| Metric | HEADLINE_ONLY (photo card) | HEADLINE_WITH_BODY |
|---|---|---|
| `headline_similarity` | headline ↔ source **title** | same |
| `body_similarity` | **null / NOT_APPLICABLE** — never computed, weighted or shown | submitted body chunked **without truncation** (≤450-char sentence groups, ≤120 chunks, tail never dropped) and aligned chunk-by-chunk to source body chunks; length-weighted mean of best matches; weakest chunk kept (`details.min_chunk_similarity`). The headline is **not** prepended |
| `passage_similarity` | headline ↔ the source sentences that discuss it (+1 sentence of context each). Stored separately; supporting evidence, **not** "Body Match" | same |
| `semantic_similarity` | = `headline_similarity` | `0.3·headline + 0.7·body` only if both exist, else null |

Every metric carries a `MetricState` — `COMPUTED` (a genuine value, possibly 0), `NOT_APPLICABLE`, `EMPTY`, `UNAVAILABLE` — plus a reason, in `analysis_details.metrics`. Null is never rendered as 0% or 100%.

**Keyword coverage.** Confirmed cause of the zero-overlap defect (`keyword_extractor.py`): S08 compared the claim's top-6 YAKE *unigrams* with the top-10 YAKE *unigram+bigram* keywords of title+full body through `compute_weighted_keyword_overlap`, a **symmetric weighted Jaccard over two independently selected lists**. A headline word ranked below position 10 of a long article, or present only inside a bigram unit, was absent from the article list, so an exactly matching headline could score 0; nothing ever checked whether the claimed words occur in the evidence. The replacement (`analysis/keywords.py`) takes every content word of the claim (stopwords dropped, but negation/qualifier/number words **retained** and weighted ×1.5), applies identical normalisation + conservative suffix stripping (`ঢাকায়/ঢাকার/ঢাকা → ঢাকা`, compound split/joined) to the evidence text, and reports **directional coverage** = matched claim weight / applicable claim weight against (a) the source title, (b) title + relevant passages, and (c) the full source article for a submitted body. Identical normalised titles → 1.0. States distinguish genuine zero, empty extraction, utility failure and not-applicable. Keyword strings, weights and matched/unmatched terms are logged at DEBUG (`s08_keyword_diagnostics`); the claim text is already logged as a preview elsewhere, so no new privacy surface is introduced.

**Entity coverage.** The directional helper subtracted `0.3 ×` the share of *extra article entities*; that penalty is removed — extra people/places in a long article are not evidence of alteration. `analysis/entities.py` matches claimed entities against NER mentions **of the title and relevant passages** (long text is chunked, not cut at 1000 chars) by: exact normalised key → curated alias set → unambiguous multi-token span containment → literal presence of the token sequence. A bare shared token (e.g. a surname) that only occurs inside longer, different entities is **ambiguous, never matched**, so different people are not merged. No claim entities → `NOT_APPLICABLE` (not 100%); NER unavailable → `UNAVAILABLE` (not 0 and not a pass). Matched/unmatched diagnostics and evidence entities are persisted.

**NER/NLI audit (`ner_service.py`, `nli_service.py`).** A loaded checkpoint is not evidence it works. At load the NER service checks the checkpoint's `id2label` really contains PER/LOC/ORG (BIO stripped) and tags a fixed Bangla smoke sentence; failing either marks it **unavailable** (surfaced as `UNAVAILABLE`, never "no entities"). The NLI service requires exactly entailment/neutral/contradiction label names and maps output **by name, not position**. Audit results are exposed (`.audit`) and logged. The audit proves wiring and rough function, **not accuracy**.

### 6.3.3 S10 — alteration checks

Each check compares a claim sentence with the source sentence(s) that **discuss the same thing** (sentence alignment on weighted coverage of the claim's *content* words, ≥0.5; numbers/negations/qualifiers are excluded from alignment so an altered detail cannot hide the alignment). A flag is raised **only** on a concrete, quotable disagreement:

- **numbers** — value/unit change (`১০ লাখ` folded to 1,000,000; spelled numerals recognised; same value in Bangla/ASCII digits matches). A number absent from the aligned sentence but present elsewhere in the article is not a discrepancy; one absent everywhere and uncontradicted is `NOT_EVALUATED`.
- **negation** (incl. fused `-নি` verb forms, with nouns like `খনি`/`ধ্বনি` excluded), **scope/quantifiers** (all↔some, at-least↔at-most), **attribution** (different speaker for the same statement), **modality** (completed event ↔ plan/possibility/future).
- **entity substitution / role** — an unmatched claimed entity replaced by an unclaimed source entity of the **same type and the same grammatical role** (Bangla case marking: `-কে` object, `-র/-ের` possessor, `-তে/-য়` locative, `দ্বারা/কর্তৃক` agent), unambiguously; or two matched entities with exchanged roles. Same type ≠ same role; low overlap alone is never a substitution.

Each check ends `PASSED` / `FAILED` / `NOT_EVALUATED` / `NOT_APPLICABLE`; the legacy booleans are true only on `FAILED`, so a default `False` can never be read as "verified". Per-part `headline` / `body` states are derived from the alignments; for photo cards `body` is `NOT_APPLICABLE` and no body text — real or synthetic — takes part in any check.

### 6.3.4 S11 — three independent decisions

- **Source.** `CONFIRMED` requires a *plausible corresponding report* — headline↔title similarity (≥0.72 strong; ≥0.55 plus lexical support) or, with no embedding, strong keyword coverage. Same outlet + broadly similar topic is insufficient. Body metrics and alteration checks play **no part**, so an altered detail or a defective aggregate cannot make an original report look like a different article. `NOT_FOUND` requires an **adequate** search (≥2 completed provider calls and ≥50% of attempted calls completed) that found no corresponding report; a failed or inadequate search, failed page fetches/extractions, or no usable signal → `INCOMPLETE`.
- **Content** (only once Source is CONFIRMED). `ALTERED` requires a concrete discrepancy (or an NLI contradiction **only if** `THRESHOLD_NLI_BANGLA_VALIDATED=true`, default false). `MATCHED` requires positive support for every applicable material claim: headline similarity ≥0.75, keyword coverage ≥0.70 (≥0.85 if NER is unavailable), entity coverage ≥0.80 where computable, every alteration check `PASSED`/`NOT_APPLICABLE`, and — only for a submitted body — body similarity ≥0.70, weakest chunk ≥0.50, body keyword coverage ≥0.60 and a complete (untruncated) comparison. Weak scores, neutral NLI, missing signals, unrun checks and low similarity alone → `INCOMPLETE`. Low contradiction is **not** treated as entailment, and a matching headline never hides an altered body (body discrepancies → `ALTERED`; an unsupported body → `INCOMPLETE`).
- **Date.** Claimed day vs the report's `datePublished` day in **Asia/Dhaka** (UTC timestamps are converted: `2026-03-15T21:30:00+00:00` is 16 March; offset-less timestamps assume Dhaka and say so). Independent of content. Missing report date → `INCOMPLETE`; no claimed date → not applicable. `dateModified`, trafilatura's "most recent date" and crawl dates are never used; provenance (`json_ld.datePublished`, `meta.article:published_time`, `selector:…`, …) is stored. (S06 previously searched for dates only on its fallback paths, so a page whose title/body came from site selectors had no date at all — fixed.) The ranker no longer uses the claimed date, so a wrong claimed date cannot push the genuine report down.

Thresholds are **heuristic and unvalidated** (`config.py: ClassificationThresholds`). The displayed `confidence` is renamed **check strength** in the UI: the mean of the applicable similarity/coverage measurements (negative results: the share of attempted search calls that completed; incomplete: none). It is a measurement summary, not a probability of truth (`confidence_meaning` is returned with every result).

### 6.3.5 S04/S05 — search accounting and retrieval

`_call_provider` returns an explicit outcome per call (`SUCCESS`, `SUCCESS_EMPTY`, `FAILED`, `SKIPPED` for unconfigured providers, `CACHED`); the previous code swallowed provider exceptions and returned `[]`, so only exceptions *escaping* `gather()` were counted and a total outage looked like a clean empty search (the internal-site client likewise returned `[]` on an HTTP error — it now raises). Counts and adequacy are persisted in `analysis_details.search`. Retrieval is **date-free**: the claimed date is passed only to explicitly `DATE_BOUND` queries (it used to be applied to every query — year suffix, ±7-day windows — hiding the right article whenever the claimed date was the wrong thing). S05 validates the **final redirected host** against the source's registered domains/channels (`source_config.allowed_domains`: canonical domain, `base_url`, domain aliases); rejected redirects are counted separately and are not fetch failures.

### 6.3.6 Claim identity, reuse and freshness

One function — `compute_claim_hash` — builds identity from sorted-key JSON of: pipeline version, claim scope, normalised headline, normalised body (only when the scope has one), canonical source, claimed date. It is used by S01, `register_claim`, S02, S12 and the photo-card flow. Bumping `VERIFICATION_PIPELINE_VERSION` (now `v3.0-scope-aware`) changes every hash, so results from the defective logic are never served as current (and historical rows carry `pipeline_version = NULL` and are never reused); nothing is deleted.

A result is reusable only if: current pipeline version; **no INCOMPLETE dimension** (an incomplete check is never a settled answer); and fresh — `REDIS_TTL_CLAIM_RESULT` (24 h) or the shorter `REDIS_TTL_NOT_FOUND_RESULT` (1 h) for NOT_FOUND, enforced in the database fallback as well as for Redis pointers; expert-finalized results are exempt. `force_refresh` bypasses registration reuse, S02 (Redis and DB) and the search-result cache. A reuse hit never shares a submission: the requester's own submission receives a copy of the automated result (`ResultReuseService.materialize`) and expert state is read through from the original.

### 6.3.7 Persistence, versioning and expert snapshots

S12 persists to the submission the run was started for — never adopting another submission by hash (the old `get_by_content_hash` fallback could overwrite an expert-reviewed submission on refresh) — and is **idempotent**: re-running against a submission already in review is a no-op (no second result, no second notification; `notify_once` de-duplicates by user/type/link, in a SAVEPOINT so a notification failure never invalidates the saved result). All applicable scores, check states, discrepancies, selected evidence, NLI output, search accounting and date provenance are written, so a result is identical immediately after verification, after navigating away, after Redis expiry and via the DB fallback — every read path goes through one presenter (`presenter.py`) and no Redis payload overlays the row. Automated columns are separate from expert-finalized columns (`final_*`, `overall_verdict`); a re-verification creates a **new** submission and cannot mutate a reviewed snapshot. `ai_consensus_label` (the legacy TRUE/FALSE/PARTIALLY_TRUE projection) is no longer written — nothing in expert voting, credibility or escalation ever read it.

### 6.3.8 Background jobs and recovery

`verification_jobs` is a database-backed queue: the job row is committed **with** the accepted submission, workers claim with `FOR UPDATE SKIP LOCKED`, heartbeat every 30 s, and a RUNNING job whose heartbeat is older than `JOBS_STALE_AFTER_SECONDS` (default 120) is re-claimed — so jobs accepted before a restart, or left RUNNING by a crash, are recovered (latency ≤ the stale window). Retries are bounded (`max_attempts=3`); permanent failures (unreadable image, no headline) fail immediately with a user-presentable `failure_reason` and exactly one `VERIFICATION_FAILED` notification. Concurrency is bounded (`JOBS_MAX_CONCURRENT`, default 2). This is a DB queue drained by an **in-process** worker, not a separate broker: it survives restarts but only drains while an application process is running. Execution depends on nothing from the originating request (own session; image read back from storage).

### 6.3.9 API summary

| Endpoint | Behaviour |
|---|---|
| `POST /photocard/verify/async` | 202 `{submission_id, status:"PENDING", phase:"QUEUED", message, queued_at}`; 404 unresolved source; 413/415 image; 503 storage down (nothing accepted) |
| `GET /photocard/{id}` | State by id (pending/processing/failed/saved result); pending/failed are owner-only (anonymous submissions stay id-accessible) |
| `POST /verify/async` · `GET /verify/{id}` · `GET /verify/{id}/status` | Status response carries `phase` and `error` (failure reason); results come from the DB presenter |
| `GET /submissions/{id}` | Adds `processing_phase`, `failure_reason`; effective status reads through to a finalized original |
| `GET /users/me/submissions` | Owner-only; includes `submission_type`, `phase`, `failure_reason`, `date_status`, `image_url`, expert-only `overall_verdict`; valid for rows with no headline/result yet |
| `GET /dashboard/explorer` | Lists reviewable, non-duplicate submissions; supports `date_status`; `overall_verdict` null until finalized |
| `VerificationResponse` | adds `claim_scope`, `review_pending`, `confidence_meaning`, `pipeline_version`, `analysis`; `scores` adds `passage_similarity`, `*_keyword_coverage`; `manipulation_flags` adds `check_states`, `discrepancies` |

### 6.3.10 Deployment

1. Apply migration `d1a7c3e5f9b2` (`alembic upgrade head`): adds result score/analysis columns, `submissions.processing_phase/failure_reason`, `verification_jobs`; re-queues text submissions left PENDING/PROCESSING and fails old synchronous photo-card ones left in flight. No backfill, no deletes. The re-queue statement uses `gen_random_uuid()` (PostgreSQL 13+, or enable `pgcrypto`).
2. Configuration (all optional; see `.env.example`): `JOBS_*`, `REDIS_TTL_NOT_FOUND_RESULT`, `THRESHOLD_NLI_BANGLA_VALIDATED` (leave false), `THRESHOLD_SEARCH_MIN_*`.
3. The new pipeline version invalidates all cached/reusable results by construction; no Redis flush is needed (old pointers are ignored by version check).
4. Make sure the app process stays up: the job worker runs inside it. Verify at startup logs: `job_worker_started`, `ner_model_loaded` vs `ner_model_not_functional`, `nli_model_loaded` vs `nli_labels_unrecognised`.

### 6.3.11 Model-validation limitations

- NLI (`mDeBERTa-v3-base-mnli-xnli`): Bengali is not an XNLI language; no Bangla accuracy evaluation exists. It can block `MATCHED` but cannot by itself cause `ALTERED` unless explicitly marked validated.
- NER (`sahajBERT-NER`): audited for label mapping and one smoke sentence only; entity roles are inferred from surface case marking, not a parser.
- LaBSE similarity thresholds, the correspondence/support thresholds, the alignment threshold and all lexicons (negation, qualifiers, modality, attribution verbs, aliases) are hand-set heuristics with no labelled evaluation; the stage tests use deterministic fakes and prove logic, not model accuracy.
- Alteration checks detect only the listed concrete discrepancy types; other material changes yield `INCOMPLETE`, not `ALTERED`.
