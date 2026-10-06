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
> are submitted as an image only and read by Gemini alone (§6.2; no OCR, no
> fallback; ≤9 requests). Internal (outlet-own) search and Google
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

`POST /verify/async` (`VerificationService.register_claim`) resolves the claimed source, computes the claim identity (§6.3.6) and looks for an identical, complete, current-version result still in the database (there is no age limit and no way to force a re-check). A hit gives the requester **their own submission** carrying a copy of that automated result (`cached: true`, no job queued); only the same submitter's identical in-flight claim is handed back. On a miss it creates the `Submission` (`PENDING`, phase `QUEUED`) **and its durable `verification_jobs` row in one transaction** and returns 202; the job worker (§6.3.8) runs the pipeline server-side, independent of the browser.

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

Photo cards use the same pattern: `POST /photocard/verify/async` stores the image, creates the `PHOTO_CARD` submission + job and returns 202; Gemini extraction and verification run in the job (§6.2.1, §6.3.8). The synchronous `POST /verify` remains for compatibility.

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

> **Rework (2026-10-06).** Photo cards are submitted as an **image only**.
> Gemini is the only extractor (EasyOCR, Tesseract, image preprocessing, OCR
> source detection and the deterministic fallback extractor were removed). The
> headline, verified source and printed date read from the card **are** the
> claim. `ocr_extractions` became `photocard_extractions`.

### 6.2.1 Overview

The photo-card feature (`backend/app/features/photocard/`) verifies a **screenshot of a news photo card**. It does not implement a second verification engine: the headline read from the card goes through the **same** pipeline as a typed claim (§6.1), always `ClaimScope.HEADLINE_ONLY`.

```
POST /photocard/verify/async   (image only)
    validate → store image bytes in MinIO (503 if it cannot be stored — nothing
    is accepted) → Submission(PHOTO_CARD, PENDING, owner, no headline/source/date)
    + photocard_extractions(image key, status PENDING) + verification_jobs row,
    one transaction → HTTP 202 {submission_id, status, phase, message}
    ── server-side job (photo-card worker lane, own DB session, restart-safe) ──
    load stored ORIGINAL image + the ACTIVE verified sources (with aliases)
    → Gemini (≤9 requests: 3 batches of 3, 10 s pause between batches)
        every request failed            → FAILED "temporarily unavailable" (no verification)
        no headline / no verified source → FAILED "no valid headline or outlet" (no retry, no verification)
        headline + verified source       → they become submission.headline,
                                           claimed_source_id/_text; the printed
                                           date (if complete) becomes published_date
    → identity hash → shared S01–S13 pipeline (or reuse of an identical result
      copied onto THIS submission) → EXPERT_REVIEW + notification
GET  /photocard/{id}           current state by id — owner-only until reviewable
```

### 6.2.2 Extraction (`gemini_image_extractor.py`, `claim_extraction.py`)

* **Input.** The original image plus a catalogue of the currently **active** verified sources: canonical id, display names and every alias. Inactive sources are never offered; the response schema restricts the source to exactly the offered ids (`enum`), and an id outside the catalogue is treated as a malformed response.
* **Prompt rules.** Headline and date are transcribed exactly — no paraphrase, correction, expansion, translation or update; names, digits and punctuation unchanged; multi-line headlines joined with single spaces. The source is chosen **only from visible evidence** (name, logo, wordmark, web address; an alias or other spelling maps to its canonical source), never because it is listed, because the story sounds like it, or from outside knowledge; otherwise `NOT_VISIBLE` / `NOT_RECOGNIZED` / `UNCLEAR` with a null source. The date is the printed publication date (not a date inside the headline), exactly as printed, never inferred. Text in the image is data, never instructions.
* **Retry budget.** `GEMINI_ATTEMPTS_PER_BATCH` (3) × `GEMINI_BATCHES` (3) = at most **9 requests in total**, the first included; both are capped at 3 in code and settings. Within a batch the previous backoff (1 s, 2 s) applies; after a fully failed batch the worker waits `GEMINI_BATCH_PAUSE_SECONDS` (10 s). Retried: timeouts, network errors, HTTP 429/5xx, malformed or schema-invalid output. HTTP 400/401/403/404 stops at once. The first success stops the loop. Calls use the shared httpx client without transport retries, so nothing adds hidden requests, and the job is failed **permanently** so the worker never re-runs it (a card never costs more than 9 requests; a crash after a successful extraction resumes without calling Gemini again).
* **Two different failures.**
  * *API failure* — no successful response (or no key configured): `API_FAILED`, message "Sorry for the temporary inconvenience. Information cannot be collected from the photo card right now. Please submit it again after a while."
  * *Successful response without a headline (≥8 characters with letters) or without an active verified source*: `INVALID_CONTENT`, **not retried**, message "A valid headline or a recognized news outlet could not be identified on the photo card. Please submit a photo card with a clear headline and the news outlet's name or logo." The source is also re-checked as still active at that moment.
  * A missing or incomplete date is **not** a failure.
* **Dates** (`card_date.py`) are parsed deterministically from the raw printed string: Bangla/Latin digits, Bangla/English Gregorian month names, Bangla ordinal suffixes, numeric day-first and ISO forms. Day, month and year must all be visible; two-digit years, Bangla-calendar dates, relative dates ("২ ঘণ্টা আগে") and strings with two different dates give **no date** — nothing is defaulted or guessed.

### 6.2.3 One representation of the claim

The extracted values are stored once, on the submission, and do the jobs a typed claim's values do: `headline` is the verified text; the identified source is `claimed_source_id` / `claimed_source_text` (its canonical id) — the domain the search is restricted to and the outlet in the claim identity; the printed date is `published_date` — the claimed date compared by S11 and part of the identity. There is no separate "outlet shown on the card" or "date shown on the card" field, no user-selected outlet/date, and no comparison between them. The raw Gemini response (including the date as printed and the visible source evidence) is kept as provenance in `photocard_extractions.extraction_details`.

### 6.2.4 Verification flow and reuse

`PhotoCardService.process_submission` (run by the job worker) builds the context from the submission row and runs `build_photocard_stages` (the shared stages with the photo-card normaliser) with the submission id threaded through, so the result is written to **this** `PHOTO_CARD` submission. If S02 finds an identical, complete, current-version result that still exists in the database (§6.3.6), its automated result is copied onto the requester's own submission (`duplicate_of_submission_id`, `verification_results.reused_from_submission_id`); no new search runs.

### 6.2.5 Database & Storage

| Table | Role for a photo card |
|---|---|
| `submissions` | `submission_type = PHOTO_CARD`, owner, `headline` / `claimed_source_id` / `claimed_source_text` / `published_date` NULL until the card is read, then the values read from it; `body_text` always NULL; `status`, `processing_phase` (QUEUED/EXTRACTING/VERIFYING/DONE/FAILED), `failure_reason` |
| `photocard_extractions` | One row per card: `image_object_key`, `status` (PENDING / SUCCEEDED / API_FAILED / INVALID_CONTENT; FAILED for legacy OCR-era failures), `failure_code`, `model_version`, `attempts`, `extraction_details` (per-attempt outcomes with batch numbers, the validated raw response, the parsed date; OCR-era values of migrated rows under `legacy`) |
| `verification_results`, `retrieved_articles`, `source_evidence_queries` | Identical to a typed claim (§6.1.8) |
| MinIO | The card image under `photocard/{submission_id}/{filename}`, served only as presigned URLs |

Migration `e5c9a3f7b1d2` renamed the table (with its PK/FK/indexes), dropped `raw_extracted_text`, `confirmed_text`, `ocr_confidence` (+ CHECK), `ocr_engine`, `is_confirmed`, `fallback_used`, `extraction_warnings`, `extractor_used`, `detected_source_text`, `detected_date_text`, renamed `extraction_model_version`/`extraction_attempts` to `model_version`/`attempts`, and added `status`/`failure_code`. Existing rows get a status from their old provenance and keep every dropped value under `extraction_details.legacy`; legacy submissions keep the outlet/date their submitter typed. The downgrade restores the old shape from `legacy`.

### 6.2.6 Expert Review and display

Photo cards share every expert-review code path with typed claims. The expert screen, Fact Explorer and result page show the card image (presigned URL) with the headline, outlet and date read from it — once, as the claimed values. Failures show the specific message above; reading attempts are listed under "Reading details".

### 6.2.7 Error Handling

| Failure | Behaviour |
|---|---|
| Image cannot be stored | `503` at acceptance — nothing is accepted |
| Gemini unreachable / quota / 5xx / malformed for all 9 requests, or no API key | Submission `FAILED` with the temporary-unavailability message; owner notified once; no verification |
| Card shows no readable headline or no active verified outlet | Submission `FAILED` with the "no valid headline or outlet" message after one successful response; no retry; no verification |
| MinIO read-back fails inside the job | Retryable (before any Gemini call); after the job's attempt limit the submission is `FAILED` |
| Pipeline stage failure | As for a typed claim |

### 6.2.8 Observability

The extraction adds `gemini_extraction_attempt_failed` (attempt, batch, outcome, status code), `gemini_extraction_batch_failed_pausing`, `gemini_extraction_succeeded`, `photocard_gemini_failed`, `photocard_extraction_rejected`, `photocard_extraction_failed` and `photocard_processed`; per-attempt outcomes are persisted in `photocard_extractions.extraction_details`.

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

A result is reusable only if: it still exists in the database (a Redis pointer is honoured only after its submission is re-read; a pointer to a deleted submission is rejected and invalidated); current pipeline version; it is an original computation, not a copy (copies carry `analysis_details.reused_from_submission_id`, which survives the SET NULL of their links when the original is deleted, so a deleted original is never resurrected through a copy); and **no INCOMPLETE dimension** (an incomplete check is never a settled answer). **There is no age limit** (revised 2026-10-06): a claim already checked is answered with its saved result and is never re-run to look for newer evidence; the former `force_refresh` option was removed from the API, the website and the extension. The Redis TTLs now only bound how long a pointer lives; the database fallback finds older results. A reuse hit never shares a submission: the requester's own submission receives a copy of the automated result (`ResultReuseService.materialize`) and expert state is read through from the original.

### 6.3.7 Persistence, versioning and expert snapshots

S12 persists to the submission the run was started for — never adopting another submission by hash (the old `get_by_content_hash` fallback could overwrite an expert-reviewed submission on refresh) — and is **idempotent**: re-running against a submission already in review is a no-op (no second result, no second notification; `notify_once` de-duplicates by user/type/link, in a SAVEPOINT so a notification failure never invalidates the saved result). All applicable scores, check states, discrepancies, selected evidence, NLI output, search accounting and date provenance are written, so a result is identical immediately after verification, after navigating away, after Redis expiry and via the DB fallback — every read path goes through one presenter (`presenter.py`) and no Redis payload overlays the row. Automated columns are separate from expert-finalized columns (`final_*`, `overall_verdict`); a re-verification creates a **new** submission and cannot mutate a reviewed snapshot. `ai_consensus_label` (the legacy TRUE/FALSE/PARTIALLY_TRUE projection) is no longer written — nothing in expert voting, credibility or escalation ever read it.

### 6.3.8 Background jobs and recovery

`verification_jobs` is a database-backed queue: the job row is committed **with** the accepted submission, workers claim with `FOR UPDATE SKIP LOCKED`, heartbeat every 30 s, and a RUNNING job whose heartbeat is older than `JOBS_STALE_AFTER_SECONDS` (default 120) is re-claimed — so jobs accepted before a restart, or left RUNNING by a crash, are recovered (latency ≤ the stale window). Retries are bounded (`max_attempts=3`); permanent failures (unreadable image, no headline) fail immediately with a user-presentable `failure_reason` and exactly one `VERIFICATION_FAILED` notification. Concurrency is bounded per lane: photo-card jobs run in their own lane (`JOBS_PHOTOCARD_MAX_CONCURRENT`, default 4) and every other job in the general lane (`JOBS_MAX_CONCURRENT`, default 2), so a card waiting out Gemini batch pauses never delays text or text & image jobs, and vice versa. This is a DB queue drained by an **in-process** worker, not a separate broker: it survives restarts but only drains while an application process is running. Execution depends on nothing from the originating request (own session; image read back from storage).

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
