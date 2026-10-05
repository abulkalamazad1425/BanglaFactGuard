# 6. AI Engineering Design

> **Current runtime update (2026-10-05).** NER now uses
> [`arafatfahim/BanglaTag`](https://huggingface.co/arafatfahim/BanglaTag), a
> token-classification fine-tune of `csebuetnlp/banglabert`, replacing SahajBERT.
> Label and real Bangla smoke checks passed locally; accuracy remains unbenchmarked
> for this application. INST/POL labels map to ORG; DATE/TIME are excluded from
> entity matching. References to SahajBERT below describe the previous model.
>
> **Headline Alteration rework (2026-10-05) — authoritative.** S08–S12 were
> replaced by S08 source correspondence, S09 Headline Alteration (claim headline
> vs source TITLE only), S10 body similarity (four scores, never a verdict),
> S11 date verification, S12 result assembly and S13 persistence. Photo cards
> are read by Gemini from the original image first (≤3 attempts) with EasyOCR +
> the deterministic extractor as fallback. Internal (outlet-own) search and Google
> search run for every publisher. Pipeline
> version `v4.0-headline-title-body-scores`. The full design, decision rules and
> limitations are in [headline-alteration-and-body-similarity.md](headline-alteration-and-body-similarity.md);
> where an older paragraph below disagrees with it, that document wins.

## 6.1 AI Pipeline and Model Selection

### 6.1.1 Overview

The source-based verification feature (`backend/app/features/verification/`) is implemented as a **13-stage async pipeline**, orchestrated by `PipelineOrchestrator` (`pipeline/orchestrator.py`) and driven by a single mutable `PipelineContext` dataclass (`pipeline/context.py`) that is threaded through every stage. `VerificationService` (`service.py`) wires the concrete stage implementations and their dependencies (DB repositories, Redis cache, HTTP client, and the three ML services) and exposes the single public entry point `verify()`.

> **Revision note (2026-10-02).** Scoring, decision logic, claim identity, caching and background execution were reworked; §6.3 is the authoritative description and states exactly what is and is not validated. Where an older paragraph below disagrees with §6.3, §6.3 wins. The automated system produces **Source, Content and Date statuses only** — Fake / Real / Misleading / Altered is exclusively an expert-finalized assessment, and `overall_verdict` stays null everywhere until an expert finalizes it.

Design goals baked into the architecture:

- **Stage isolation** — each stage is a class satisfying the `PipelineStage` protocol (`stage_id` + `async execute(context) -> context`), independently testable and swappable.
- **Fault tolerance over completeness** — only 4 of 13 stages are *critical*; the rest degrade gracefully (empty scores, skipped flags) rather than aborting the run.
- **Cache-first short-circuit** — a claim-hash cache check (Stage 2) can skip the entire evidence-gathering and ML stack (Stages 3–13) entirely.
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

    S08["S08 · Source Correspondence 🔴 🤖\nheadline↔title LaBSE similarity + claim-keyword\ncoverage of title / passages → selects the source\narticle · CONFIRMED / NOT_FOUND / INCOMPLETE\n(topic/entity overlap alone never corresponds)"]
    S08 --> S09

    S09["S09 · Headline Alteration 🟡 🤖\nclaim headline vs source TITLE only ·\nexact match → MATCHED · else rules +\nNLI (both directions) + LaBSE → MATCHED /\nALTERED / no verdict (with status)"]
    S09 --> S10

    S10["S10 · Body Similarity 🟡 🤖\nclaim body vs source body (body claims only):\nTF-IDF cosine · Jaccard · normalized\nLevenshtein · LaBSE cosine — scores only"]
    S10 --> S11

    S11["S11 · Date Verification 🟡\nuser's claimed date vs datePublished\n(Asia/Dhaka calendar day)"]
    S11 --> S12

    S12["S12 · Result Assembly 🔴\nstrength, reasoning, analysis bookkeeping ·\nno overall verdict"]
    S12 --> S13

    S13["S13 · Persistence 🔴\nidempotent per submission · result row +\nanalysis_details · Redis pointer (complete\nresults only) · notify-once"]
    S13 --> RESP

    RESP --> OUT["VerificationResponse (read from the DB)\nsource · headline verdict + status · date ·\nbody similarity scores · analysis · articles"]

    classDef critical fill:#3a2323,stroke:#e0736a,color:#fbe4e1,stroke-width:2px;
    classDef degradable fill:#20232b,stroke:#6b7280,color:#d8dce3,stroke-width:1px;
    classDef ai fill:#1b2a3d,stroke:#4f8fd1,color:#dbe9fb,stroke-width:2px;
    class S01,S08,S12,S13 critical;
    class S02,S03,S04,S05,S06,S11 degradable;
    class S07,S09,S10 ai;
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
| S08 | Source Correspondence | **CRITICAL** | Unavailable measurements are null with a reason; without any measurement the source is `INCOMPLETE` | **LaBSE** |
| S09 | Headline Alteration | Non-critical | No verdict; `headline_check_status` = `MODEL_UNAVAILABLE` (never a guessed MATCHED/ALTERED) | **mDeBERTa-v3 NLI** + **LaBSE** + **BanglaTag NER** |
| S10 | Body Similarity | Non-critical | The failing metric is unavailable with a reason; the other scores are kept | **LaBSE** (semantic cosine only) |
| S11 | Date Verification | Non-critical | No date status | — |
| S12 | Result Assembly | **CRITICAL** | Without it there is no coherent result | — |
| S13 | Persistence | **CRITICAL** | Result must be durably stored | — |

### 6.1.4 AI Model Selection

Four distinct pretrained models are used, each chosen for a specific cost/precision tradeoff rather than using one large model everywhere:

| Model | HuggingFace ID | Role | Stage(s) | Why this model |
|---|---|---|---|---|
| **LaBSE** | `sentence-transformers/LaBSE` | Bi-encoder sentence embedding (768-dim) | S07, S08, S09, S10 | Language-agnostic BERT sentence embedding pretrained across 109 languages including Bangla. As a **bi-encoder** it lets every headline/article be embedded once and compared via cheap cosine dot-product, and every embedding is Redis-cached by text hash (`embedding_service.py`) — the only architecture that scales to comparing one claim against many candidate articles repeatedly across three separate stages. |
| **Cross-Encoder reranker** | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | Pairwise (claim, article) reranking | S07 only, gated | Cross-encoders jointly attend over the claim+article pair, giving materially better ranking precision than bi-encoder cosine similarity — but at O(n) forward passes instead of O(1) lookups, so it is deliberately **only invoked when more than 3 ranked candidates survive** the cheap composite score (`s07_evidence_ranker.py`). mMARCO's multilingual passage-ranking fine-tuning makes it suitable for Bangla news snippets without further fine-tuning. |
| **sahajBERT NER** | `neuropark/sahajBERT-NER` (configurable via `ML_NER_MODEL_NAME`, HF `ner` pipeline, `aggregation_strategy="simple"`) | Named-entity recognition (PER/LOC/ORG) | S08, S10 | An ALBERT model pretrained from scratch on Bangla text and fine-tuned for token classification with the standard BIO scheme (O/B-PER/I-PER/B-LOC/I-LOC/B-ORG/I-ORG). Used twice: to compute directional entity-overlap recall (S08) and to detect **same-type entity substitution** — e.g. a person swapped for another person of the same grammatical role — which a plain overlap score would miss (S10). **Replaces a previously broken model — see the audit note below.** |
| **mDeBERTa-v3 NLI** | `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` (configurable via `ML_NLI_MODEL_NAME`) | Textual entailment / contradiction (title ⇄ headline) | S09 only | An mDeBERTa-v3-base cross-encoder fine-tuned on XNLI (15 languages) + MNLI, built on a 100-language multilingual vocabulary, producing entailment/contradiction/neutral probabilities. A cross-encoder is required here (not LaBSE) because contradiction detection depends on fine-grained token-level interaction — e.g. one changed number or negation — that a bi-encoder's pooled cosine similarity cannot represent. Only ever called once per claim, against the single top-ranked article, keeping its cost bounded. **Replaces a previously broken model — see the audit note below.** |

**Model-tiering rationale.** The pipeline follows a **funnel pattern**: cheap, cacheable, broadly-applied signals (LaBSE cosine similarity, keyword overlap, date/domain heuristics) filter and rank a wide candidate set in S07; only the small surviving set is handed to progressively more expensive, more precise models — the cross-encoder reranker (top-N reordering) and finally the NLI cross-encoder (single top article only, in S09). This keeps per-claim latency bounded regardless of how many articles were retrieved, while still getting cross-encoder-level precision where it matters most (the final verdict).

**NLI use (2026-10-05).** The NLI model is applied only to the claim headline and the selected source title, in both directions, inside S09. There is no temperature scaling, no body premise and no title-only attenuation any more; those settings were removed with the former S09 contradiction detector.

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
| `verification_results` | The automated result, **immutable** once S13 writes it: `source_status`, `content_status` (Headline Alteration verdict: MATCHED / ALTERED / null), `headline_check_status`, `headline_exact_match`, `body_comparison_status`, `date_status`, the correspondence measurements (`headline_similarity`, `headline_keyword_coverage`, `passage_keyword_coverage`), `claim_scope`, `pipeline_version` and `analysis_details` (headline detail with differences and semantic scores, body similarity report, search accounting, date provenance, timings); `ai_consensus_label` is legacy and no longer written. Expert review never touches these columns — it writes `final_source_status`/`final_content_status`/`final_date_status`/`overall_verdict`/`finalized_at` instead (§6.1.9), so the AI's original call stays inspectable even after the claim is Expert Verified |
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

The photo-card feature (`backend/app/features/photocard/`) verifies a **screenshot of a news photo card** rather than typed text. It does not implement a second verification engine: after headline extraction the extracted headline goes through the **exact same 13-stage pipeline** documented in §6.1, always with `ClaimScope.HEADLINE_ONLY` (no body, no synthetic body), against the user's own `claimed_source_text` / `published_date`.

Submission is **accepted fast and processed in the background**:

```
POST /photocard/verify/async   (image + claimed_source_text + published_date)
    validate → store image bytes in MinIO (503 if it cannot be stored — nothing
    is accepted) → Submission(PHOTO_CARD, PENDING, owner = signed-in user) +
    OcrExtraction(image key) + verification_jobs row, one transaction
    → HTTP 202 {submission_id, status, phase, message}
    ── server-side job (own DB session, bounded concurrency, restart-safe) ──
    load stored ORIGINAL image → Gemini image extraction (≤3 attempts)
    → only if every attempt failed: EasyOCR → source detection → deterministic
      extractor → PermanentJobError if nothing usable (submission FAILED with a
      reason; never Source Not Found / a headline verdict — no check ran)
    → submission.headline + identity hash set → shared S01–S13 pipeline
      (or reuse of an identical fresh result copied onto THIS submission)
    → EXPERT_REVIEW + notification
GET  /photocard/{id}           current state by id: pending / processing (phase) /
                                failed (reason) / the saved result — owner-only
                                until the submission is reviewable
```

There is no confirmation step. The user-provided `claimed_source_text`/`published_date` are authoritative; the date/outlet read from the card are display-only metadata in `ocr_extractions` — never substituted and never compared. The former synchronous `POST /photocard/verify` endpoint was removed.

### 6.2.2 Extraction — Gemini on the Original Image First, EasyOCR Fallback

```
original image ─▶ Gemini image extraction (headline / date / source, structured JSON)
                   ├─ attempt 1 ok ─────────────────────────────▶ use it (EasyOCR NOT run)
                   ├─ fail → attempt 2 → fail → attempt 3 ─┐ (≤3 attempts in total,
                   │                                        │  backoff 1s, 2s)
                   └─ HTTP 400/401/403/404: stop at once ───┤
                                                            ▼
                     EasyOCR ─▶ source detection ─▶ deterministic extractor (§6.2.6)
                                                            │
                         nothing usable ─▶ submission FAILED with a reason (no claim invented)
```

* **Prompt.** Gemini is told to transcribe only: no paraphrase, summary, translation, spelling correction or rewrite; names, numbers, punctuation and quote marks unchanged; the date as printed; the outlet name as printed (never a guessed canonical name); `PRESENT` / `MISSING` / `UNREADABLE` status per field instead of inventing values; never mix other card text into the headline; and any text in the image is data, never an instruction.
* **Validation.** The response must parse into `GeminiPhotocardFields` (headline, date, source + their statuses). Raw values are stored unmodified (`ocr_extractions.extraction_details.gemini.raw`).
* **Retries.** Timeouts, network errors, HTTP 429/5xx, malformed/schema-invalid output and unusable extractions (headline missing/unreadable/shorter than 8 characters) are retried. A card without a printed date or outlet is not a failure. Calls use the shared httpx client, which has no transport retries, so no hidden SDK retries add to the three attempts.
* **Display-only metadata.** The date and outlet read from the card are shown in the UI when present and omitted when absent. They are never compared: verification always uses the user's selected source and claimed date.
* **Provenance.** `extractor_used` (`GEMINI_IMAGE` / `OCR_FALLBACK`), `extraction_attempts`, `fallback_used` and per-attempt diagnostics are persisted and shown to the submitter and experts.

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

### 6.2.6 Deterministic Extraction — the Fallback (`ocr_fallback_extractor.py`)

Runs only after every Gemini attempt failed (or Gemini is not configured), on EasyOCR output (§6.2.2). It also returns the first date-looking line exactly as OCR read it (display only). A typical card is mostly *not* the claim: outlet banner, one-to-three-line headline, maybe a supporting sentence, then a band of chrome — social handles, "লাইক / শেয়ার / ফলো করুন" prompts, bylines, photo credits, timestamps, engagement counters, copyright, ads. Feeding all of that into the verification pipeline dilutes the embedding and drags entity matching toward the outlet's own name rather than the claim. Each OCR line is classified and, if it's chrome, tagged with why:

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

Every downstream stage is the literal code of §6.1, so a photo card gets the same Source / Headline Alteration / Date result; for HEADLINE_ONLY the body similarity comparison is skipped. The automated system never computes an overall verdict for either flow.

### 6.2.8 Database & Storage

No photo-card-specific result table exists — a photo card's AI verdict lives in the **same** `verification_results` row shape a typed claim uses:

| Table | Role for a photo card |
|---|---|
| `submissions` | One row, `submission_type = PHOTO_CARD`, owner = submitter, `headline` NULL until extracted (`body_text` always NULL — headline-only), `claimed_source_text`/`published_date` exactly as the user provided them, `status` (`PENDING` → `PROCESSING` → `EXPERT_REVIEW` → `FINALIZED`/`ESCALATED`, or `FAILED`), `processing_phase`, `failure_reason` |
| `ocr_extractions` | Photo-card-only: `image_object_key`, `raw_extracted_text`, `ocr_confidence`, `ocr_engine`, plus extraction provenance added for the Gemini flow — `extractor_used` (`GEMINI` \| `EXISTING_FALLBACK`), `extraction_model_version`, `extraction_warnings` (JSONB array, includes any source/date conflict text), `detected_source_text`, `detected_date_text`. `confirmed_text`/`is_confirmed` are legacy columns from the removed two-step flow — the unattended flow never sets them — kept rather than dropped since historical rows still carry them |
| `verification_results` | AI result, **immutable** once written by S13 (same columns as §6.1.8). Expert review never overwrites these — it writes `final_source_status`/`final_content_status`/`final_date_status`/`overall_verdict`/`finalized_at` instead, so the AI's original call stays inspectable after the claim moves to Expert Verified |
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

Since the pipeline runs the literal same stage instances as `POST /verify`, every photo-card verification gets the same per-stage timings and `structlog` events described in §6.1.6. The extraction half adds `gemini_extraction_attempt_failed` (attempt, outcome, status code), `gemini_extraction_succeeded`, `photocard_gemini_failed_using_ocr_fallback`, `photocard_extraction_failed` and `photocard_processed` (extraction method), and the same per-attempt outcomes are persisted in `ocr_extractions.extraction_details`.

## 6.3 Scope-aware Verification, Decisions, Identity and Background Jobs (2026-10-02)

This section is the authoritative description of runtime behaviour after the scope-aware rework. It also states plainly what is **not** validated.

### 6.3.1 Business requirements

Both flows (text and photo card) check (1) whether a corresponding report exists in the claimed source, (2) whether the submitted claim matches it or contains material alterations, and (3) whether the claimed publication date matches the report's. The automated result is **Source, Content and Date statuses only**; Fake / Real / Misleading / Altered is an expert-finalized assessment and `overall_verdict` is null in every API, database write, frontend view, Fact Explorer row and notification until an expert finalizes it. Photo cards are always `HEADLINE_ONLY`; text claims verify the headline and, when present, the submitted body.

### 6.3.2–6.3.4 Superseded

The scope-aware S08 measurements, the S10 sentence-level alteration checks and the S11 three-way classifier described here on 2026-10-02 were replaced on 2026-10-05. See [headline-alteration-and-body-similarity.md](headline-alteration-and-body-similarity.md).

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
| `VerificationResponse` | `content_status` is the Headline Alteration verdict; adds `headline_check_status`, `claim_scope`, `review_pending`, `confidence_meaning`, `pipeline_version`, `legacy_result`, `analysis` (headline detail, body similarity report); `scores` and `manipulation_flags` were removed on 2026-10-05 |

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
