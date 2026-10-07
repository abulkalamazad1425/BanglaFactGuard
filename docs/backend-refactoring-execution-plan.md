# Backend Refactoring: যাচাই করা Execution Plan

> **তারিখ:** 2026-10-07
> **ভিত্তি:** [`backend-cleanup-and-refactoring-audit.md`](backend-cleanup-and-refactoring-audit.md) এবং সেটির উপর ChatGPT এর review। দুটোই codebase এর সাথে আবার মিলিয়ে দেখা হয়েছে।
> **এই document এর অবস্থান:** audit এর সাথে এই plan এর কোথাও অমিল হলে **এই plan টি মানুন**। audit কে একটি checklist হিসেবে দেখুন, আর এই document কে কাজের ক্রম হিসেবে।
> `app/features/verification/pipeline/source_registry.py` এ কোনো পরিবর্তন হবে না, এবং এটি delete list এও থাকবে না।

---

## 0. বাস্তবায়নের অবস্থা (2026-10-07 এ হালনাগাদ)

ধাপ 1 থেকে 7 বাস্তবায়িত হয়েছে, branch `refactor/backend-safe-cleanup` এ (এখনও commit হয়নি)। সংশোধিত plan অনুযায়ী দুটি পরিবর্তন হয়েছে: development চলাকালে `CORS_ORIGINS` এর default `["*"]` থাকবে (M3 ও "default `[]`" অংশ বাদ), এবং Bearer-token flow এর কারণে `allow_credentials=False`।

**আচরণ যে একই আছে, তার প্রমাণ**

| যাচাই | ফলাফল |
|---|---|
| Unit ও integration test, প্রতিটি test আলাদা করে baseline এর সাথে তুলনা | 410 passed, 2 skipped (opt-in real-model test); কোনো regression নেই |
| Golden hash (claim ও photo card এর identity) এবং API response snapshot | হুবহু একই |
| পুরোনো (HEAD) বনাম নতুন app, dev DB এর copy তে, আসল HTTP request | 1,783 টি GET request (৫ জন user, ৬৫টি submission, সব role), পার্থক্য 0 |
| পুরোনো বনাম নতুন function, আসল Postgres এ | dashboard stats, explorer, my-submissions, my-stats হুবহু একই |
| Job runner: পুরোনো বনাম নতুন `execute_job` | 36টি অবস্থা (৪ kind × সাফল্য/ব্যর্থতা × dependency), call এর ক্রম, commit/rollback ও error হুবহু একই |
| Gemini module ভাগ | prompt, response schema ও 429 এর হিসাব byte-for-byte একই; 60টি Gemini test pass |
| Multimodal আসল weight দিয়ে | probability এর পার্থক্য 0.0 |
| OpenAPI | শুধু ৫টি ইচ্ছাকৃত documentation বা example পরিবর্তন |
| আসল browser (Chromium) এ frontend, নতুন backend এর সাথে | ৩টি role এর ১৫টি page এ কোনো API error নেই; `localhost:4200` থেকে Bearer সহ CORS request এর উত্তর 200 |
| Fresh venv (`pip install -e ".[dev]"`, Chromium) | install ও `pip check` ঠিক আছে, test pass করে |

**Manual তালিকার অবস্থা**

| # | অবস্থা |
|---|---|
| M1 | আমি করেছি: নিরাপদ `AUTH_SECRET_KEY` তৈরি করে `backend/.env` এ বসানো হয়েছে (কোথাও প্রকাশ করা হয়নি), এবং field টি required। অন্য কোনো deployment থাকলে সেখানে আলাদা key দিতে হবে। |
| M2 | **আপনার কাজ:** পুরোনো `.env.example` এর SMTP app password git history তে আছে। Google Account থেকে revoke করে নতুনটি শুধু `.env` এ রাখুন। |
| M3 | বাদ দেওয়া হয়েছে (development এ `*`)। |
| M4 | **আপনার কাজ:** admin password বদলান (migration এ hash প্রকাশিত)। |
| M5 | আমি করেছি: code ও `.env` একসাথে LaBSE তে, পুরোনো hash অপরিবর্তিত (`nlp/model_identity.py`)। |
| M6 | Local অংশ আমি করেছি: git এ নেই এমন দুটি weight (`img_backbone.pt`, `text_backbone.pt`) এর copy আছে `C:\Users\Asus\bfg_model_backup` এ। সব model file এর SHA-256 manifest (৩৫টি file) সেখানেই রাখা, এবং copy গুলো manifest এর সাথে মিলিয়ে দেখা হয়েছে। **Remote copy (Drive বা অন্য কোথাও) আপনার account লাগবে।** `classifier.pt` untrack করা হয়নি। |
| M7 | আমি করেছি (fresh venv, Chromium)। |
| M8 | স্বয়ংক্রিয়ভাবে করা হয়েছে (উপরের A/B ও browser test)। একটি সীমাবদ্ধতা: free RAM মাত্র ~1.8 GB, তাই আসল model দিয়ে নতুন text claim এর পুরো pipeline A/B চালানো হয়নি। pipeline এর stage গুলো fake model দিয়ে test করা। |
| M9 | প্রযোজ্য নয় (কোনো script মোছা হয়নি)। |

**ধাপ 7 এ যা ইচ্ছাকৃতভাবে করা হয়নি**
- Model এর জায়গা বদল: `VerificationJob` আগে থেকেই `verification/models.py` এ, `jobs.py` এর পাশে আছে। `PhotocardExtraction`, `RetrievedArticle` ও `SourceEvidenceQuery` হলো `Submission` aggregate এর child (cascade delete ও `back_populates` relationship)। এগুলো সরালে model import এর cycle তৈরি হয়, এবং যে script শুধু `submissions.models` import করে সেখানে mapper ভেঙে যেতে পারে। ঝুঁকি আছে কিন্তু লাভ শুধু সাজানোর, তাই রাখা হয়েছে।
- Role ও job kind এর জন্য নতুন enum: ১০টির বেশি জায়গা বদলাতে হতো, লাভ কম, তাই পরে করা হবে।
- Section 5 এর সিদ্ধান্তগুলো (D1 থেকে D11) আগের মতোই আপনার সিদ্ধান্তের অপেক্ষায়।

---

## 1. সারকথা

ChatGPT এর review এর **প্রায় সব সংশোধন সঠিক।** আমি নিজে আবার যাচাই করেছি (code পড়ে, এবং যেখানে সম্ভব চালিয়ে দেখে)। audit এ কয়েকটি তথ্যগত ভুল ছিল, আর কয়েকটি প্রস্তাবকে যতটা নিরাপদ বলা হয়েছিল ততটা নিরাপদ নয়। এই plan সেগুলো ঠিক করে, এবং কাজকে ছোট ছোট ধাপে ভাগ করে। প্রতিটি ধাপের শেষে test চালানো হবে।

ChatGPT এর review এ আমি কোনো উল্লেখযোগ্য ভুল পাইনি। শুধু একটি সংখ্যায় পার্থক্য আছে: আমার machine এ dummy-hash এর পরীক্ষায় প্রায় ২০০ ms লেগেছে, ওর হিসাবে ~৪০০ ms। কিন্তু উপসংহার একই: **timing leak নেই।**

---

## 2. যাচাইয়ের ফলাফল

### 2.1 Audit এ যা ভুল ছিল (ChatGPT ঠিক বলেছে, আমি নিশ্চিত করেছি)

| Audit এর দাবি | আসল অবস্থা | কীভাবে যাচাই করেছি |
|---|---|---|
| 1.8: dummy bcrypt hash দিলে সঙ্গে সঙ্গে `ValueError` হয়, তাই timing leak আছে | **ভুল।** bcrypt 5.0.0 এ এটি `False` ফেরত দেয় এবং আসল hash এর মতোই সময় নেয় (~২০২ ms বনাম ~২১১ ms)। | স্থানীয়ভাবে চালিয়ে দেখেছি |
| 4.1: `AppSettings.classification` অব্যবহৃত | **ভুল।** S04 (`s04_source_search.py:265`) ও S08 এটি ব্যবহার করে। মুছে দিলে verification এ `AttributeError` হবে। এটা alias, কিন্তু চালু code এ ব্যবহৃত। | code পড়ে |
| 6.2: `_should_dispatch` সবসময় True দেয় | **ভুল।** domain না থাকলে False দেয়। শুধু `query_type` ও `query_text` parameter দুটি অব্যবহৃত। | code পড়ে |
| 6.4: `ai_preliminary_label` কেউ লেখে না | **আংশিক ভুল।** `upsert_result()` এটি লেখে (সাধারণত `None`)। | `repository.py:89,118` |
| 6.3: `PipelineContext.persisted` কেউ পড়ে না | app code পড়ে না, কিন্তু **test এ assert করা হয়** (৪টি জায়গায়) | grep |
| 6.1: `ExtractedContentSchema` এর কোনো reference নেই | এটি `ArticleExtractionResult` এর ভেতরে ব্যবহৃত। দুটোই একসাথে dead, তাই একসাথে সরাতে হবে। | code পড়ে |
| 6.1: `KeywordUnit.to_dict` আলাদাভাবে অব্যবহৃত | `KeywordCoverage.to_dict` এটি call করে। দুটো একসাথে সরাতে হবে। | code পড়ে |
| 1.6: `feedparser` সরানো যায় | **ভুল।** `pygooglenews` এর runtime dependency হিসেবে এটি লাগে। direct declaration বাদ দেওয়া যায়, কিন্তু package টি environment এ থাকতেই হবে। এছাড়া test এর `aiosqlite` ও কোথাও declare করা নেই। | `pip show pygooglenews` |
| 11.7: enum ব্যবহার করলে JSON ও DB এর মান একই থাকবে | **ভুল।** SQLAlchemy এর `Enum` সাধারণত enum এর **name** সংরক্ষণ করে। `UserRole.USER="user"` হলে DB তে `USER` লেখা হবে, ফলে পুরোনো `user` row পড়তে `LookupError` হবে। এই project এর বিদ্যমান Postgres enum গুলোও name রাখে (যেমন `'INTERNAL_SITE'`)। | স্থানীয়ভাবে চালিয়ে দেখেছি + migration file |
| 1.4: config এ LaBSE বসালেই সমস্যা মিটবে | **অসম্পূর্ণ।** `compute_photocard_hash()` এ config এর model name ঢোকে। নাম বদলালে সব photo card এর identity hash বদলে যাবে, এবং পুরোনো ফলাফল আর reuse হবে না। | `photocard/verification_stages.py:22` |
| 1.1: যে কেউ admin token বানাতে পারবে | **অতিরঞ্জিত।** backend token থেকে user ID নিয়ে DB থেকে user ও role পড়ে, তাই admin সাজতে admin এর UUID জানতে হবে। তবুও জানা secret দিয়ে কোনো user কে impersonate করা যায়, তাই ঝুঁকি গুরুতর। | `security.py:88` |
| 1.1 / 14: secret বদলালে সবাইকে আবার login করতে হবে | **ভুল।** refresh token DB তে যাচাই হয়, আর frontend এর interceptor 401 পেলে নিজে থেকেই `refresh()` call করে। ব্যবহারকারী সাধারণত টেরই পাবেন না। | `auth.interceptor.ts:26` |
| 2B / 10: দুটি MinIO service এর পার্থক্য শুধু prefix | **ভুল।** photocard এর service ব্যর্থ হলে `False`/`None` ফেরত দেয়, আর multimodal এর service exception দেয়। ব্যর্থতার এই আচরণ দুই রকম রাখতে হবে। | code পড়ে |
| 10: claim scope এর হিসাব তিন জায়গায় একই | **ভুল।** presenter photo card এর ক্ষেত্রে override করে এবং সংরক্ষিত scope কে অগ্রাধিকার দেয়। শুধু body দেখে হিসাব করা function দিয়ে এটা বদলানো যাবে না। | `presenter.py:29` |
| 11.2: material difference এর rule ক্রম রাখলেই একই ফল | **অসম্পূর্ণ।** negation, modality ও scope একটি `if/elif` chain এ আছে (একটির বেশি finding আসে না)। এদের আলাদা rule বানালে finding এর সংখ্যা বেড়ে যাবে। | `material_differences.py:409-420` |
| 9.1: dashboard এ ১০টি COUNT query | **১১টি COUNT এবং ১টি AVG।** | code পড়ে |
| 4.1: "চার জায়গায় তিন রকম version" | **দুই রকম:** `1.0.0` ও `0.1.0`। | code পড়ে |
| 2C: migration "মোট ২৮টি" | **২৭টি revision**, আর `__init__.py` সহ মোট ২৮টি file। | `ls` |
| 2A: `reset_operational_data.py` আর কখনো চালানো সম্ভব নয় | **অতিরঞ্জিত।** পুরোনো revision এর DB restore করে rehearsal এ চালানো যায়। তবে দৈনন্দিন কাজে এর আর প্রয়োজন নেই। | code পড়ে |
| 11.4: `AuthService` এ DI নেই | **আংশিক ভুল।** এটি ইতিমধ্যে optional `email_service` inject করতে পারে। | `service.py:64` |
| 7: "Previously…" ধরনের comment সব সরান | **অতিরিক্ত।** যে comment কোনো regression ঠেকায়, সেগুলো রাখা উচিত, শুধু ছোট করা যায় (NLI কেন multilingual, `dateModified` কেন নেওয়া হয় না, NER কেন text কাটে না)। | — |
| 7: Playwright "সব source এর জন্য চলে" | **ভুল।** শুধু প্রয়োজন হলে fallback হিসেবে চলে (block হলে, JS shell বা bot-wall পেলে)। | `s05` |
| 12: import এর সময় thread ও DB connection তৈরি হয় | **অতিরঞ্জিত।** import এর সময় শুধু executor ও engine object তৈরি হয়। thread ও connection তৈরি হয় প্রথমবার ব্যবহারের সময়। তবে shutdown এর সময় এগুলো বন্ধ না হওয়ার সমস্যাটি সত্য। | — |
| 12: দুইবার commit হয়, তাই service এর commit মুছে ফেলুন | **বিপজ্জনক।** response পাঠানোর আগে submission ও job commit করা জরুরি, কারণ worker আর client এর polling তখনই এগুলো দেখতে পায় (`verification/service.py:249`)। | code পড়ে |

### 2.2 Audit এর যে অংশ ঠিক আছে (নিশ্চিত করা হয়েছে)

JWT এর default secret, `.env.example` এ credential, CORS এর wildcard, embedding model এর অমিল, `classifier.pt` git এ tracked থাকা, অসম্পূর্ণ dependency declaration, `retry.py` এর মতো dead code, অব্যবহৃত exception ও settings, N+1 query, multimodal এ backbone দুইবার চালানো, `MultimodalModelLoader` এর class ও instance state এর bug, `list_predictions` এর `total` bug, presenter এর hardcoded provider, `_raw_html_cache` এর অঘোষিত field, এবং stale comment গুলো (OCR, S11 এর photo card date, 12-stage)।

### 2.3 বর্তমান test baseline (refactor শুরুর আগে)

```
.venv/Scripts/python -m pytest -q --no-cov -p no:cacheprovider
→ 363 passed, 1 skipped, 4 failed, 5 errors
```

এই ব্যর্থতাগুলো refactor এর আগেই ছিল, এবং কোনোটিই production code এর bug নয়:

| Test | কারণ |
|---|---|
| `integration/test_api_endpoints.py` (৫টি error) | `conftest.py:170` এ `httpx.AsyncClient(app=app)` লেখা। httpx 0.28 এ `app=` argument সরিয়ে দেওয়া হয়েছে, এখন `ASGITransport` লাগে। |
| `integration/test_verification_pipeline.py` (২টি fail) | integration fixture SQLite এ চলে না (environment এর সমস্যা) |
| `unit/test_normalizer.py::test_resolve_source_via_db` | SQLite JSONB render করতে পারে না (জানা সমস্যা) |
| `unit/test_multimodal_embedding_extractor.py::test_different_image_breaks_cache_hit` | test এর ভেতরে local import থেকে `UnboundLocalError` (জানা সমস্যা) |

**নিয়ম:** প্রতিটি ধাপের পরে passed এর সংখ্যা ৩৬৩ এর কম হবে না, এবং নতুন কোনো failure আসবে না। ধাপ 1 এ test infrastructure ঠিক হলে baseline বাড়বে।

---

## 3. আমি code এ যা পরিবর্তন করব (ধাপে ধাপে)

প্রতিটি ধাপ আলাদা commit বা PR এ হবে, এবং প্রতিটি ধাপের পরে test চালানো হবে। কোনো ধাপ API এর response, DB data বা verification এর ফলাফল বদলাবে না। যে কাজে আচরণ বদলায়, সেগুলো section 5 এ আলাদা রাখা হয়েছে এবং আপনার অনুমতি ছাড়া করা হবে না।

### ধাপ 1: Safety net (কোনো production code বদলাবে না)
- `conftest.py` এ `ASGITransport` ব্যবহার করে integration fixture ঠিক করা।
- `test_multimodal_embedding_extractor` এর local import এর bug ঠিক করা।
- **Golden test:** কিছু নির্দিষ্ট input দিয়ে `compute_claim_hash`, `compute_photocard_hash`, `compute_url_hash`, `compute_search_query_hash` এর বর্তমান মান test এ আটকে রাখা। এতে পরে কোনো ধাপে ভুলবশত hash বদলালে test ধরে ফেলবে।
- **Response snapshot test** (SQLite helper দিয়ে): `/verify/{id}`, `/photocard/{id}`, `/users/me/submissions`, `/dashboard/explorer`, `/expert/queue`।
- Behaviour test: reuse করা copy তে expert এর রায় দেখায় কিনা, owner ছাড়া অন্য কেউ PENDING submission দেখতে পায় কিনা, একই vote দুইবার দেওয়া যায় কিনা, notification একবারই যায় কিনা। এর বেশিরভাগ আগে থেকেই আছে, যা নেই শুধু সেগুলো যোগ হবে।

### ধাপ 2: নিরাপদ security ও config সংশোধন (আচরণ একই থাকবে)
- `AuthSettings.secret_key` কে **এখনো required করা হবে না।** শুধু startup এ default secret ধরা পড়লে একটি জোরালো warning log হবে। আপনি deployment এ secret দেওয়ার পরে (section 4, M1) সেটা required করা হবে (ধাপ 2b)।
- `pyproject.toml` ও `requirements.txt` এ অনুপস্থিত dependency যোগ করা হবে: `python-jose`, `bcrypt`, `email-validator`, `psycopg2-binary`, `playwright`, `minio`, `timm`, `torchvision`, `Pillow`, `numpy`; dev এর জন্য `aiosqlite`। `feedparser` থাকবে। version এর সীমা হবে এখন installed version অনুযায়ী।
- `.env.example`: duplicate key সরানো, `AUTH_SECRET_KEY`, `CORS_ORIGINS`, `JOBS_*`, `GEMINI_BASE_URL`, `PHOTOCARD_MAX_IMAGE_BYTES` placeholder সহ যোগ করা, `SEARCH_TOP_K_CANDIDATES=15` (code এর default এর সাথে মিলিয়ে), SMTP password খালি করা। এটা declared default থেকে তৈরি হবে, live settings থেকে নয়।
- **Embedding model এর অমিল, hash অপরিবর্তিত রেখে:**
  - `EmbeddingService` setting থেকে model এর নাম নেবে, default হবে `sentence-transformers/LaBSE`।
  - `compute_photocard_hash()` এ model tag এর জন্য এখন যে string যায় সেটা একটি constant এ আটকে দেওয়া হবে (`paraphrase-multilingual-mpnet-base-v2:…`)। ফলে photo card এর hash একই থাকবে।
  - golden test (ধাপ 1) এটা নিশ্চিত করবে।
  - এরপর `.env` এ `ML_EMBEDDING_MODEL_NAME` এর মান LaBSE করা নিরাপদ হবে (section 4, M5)।
- CORS: code এর default এখন বদলানো হবে না। `.env` এ নির্দিষ্ট origin দেওয়ার পরে (M3) default `[]` করা হবে।

### ধাপ 3: Dead code ও generated file পরিষ্কার করা
- Delete করা হবে: `shared/utils/retry.py`, `features/feedback/`, অব্যবহৃত constant (`ClaimStatus`, `LogLevel`, `MAX_CONCURRENT_FETCHES`, `MAX_EVIDENCE_CANDIDATES`, `MIN_KEYWORD_OVERLAP`), `_KEY_EMBEDDING`, `_EMBEDDING_DIM`, অব্যবহৃত ১০টি exception, cache এর `get_article`/`set_article` ও `_KEY_ARTICLE`, `ArticleExtractionResult` ও `ExtractedContentSchema` (একসাথে), `VerificationResultSummary`, `AuthService.get_me`, অব্যবহৃত repository method, `BaseRepository.get_by_field`/`exists`, `logging.get_logger`/`clear_context`, `text_cleaner.extract_first_n_sentences`, `OVERALL_LABELS`, `KeywordCoverage.to_dict` ও `KeywordUnit.to_dict` (একসাথে), `Passage.to_dict`, `EntityMention.to_dict`, `EntityMatch.to_dict`, `QUALIFIER_WORDS` এর re-export।
- S06 এর dead date path: `_parse_date`, `_DATE_FORMATS`, `_BANGLA_MONTHS`, `_BANGLA_TO_ARABIC`, এবং `_extract_bs4`/trafilatura এর ফেলে দেওয়া date return value। এখন যে publication date finder টি আসলে কাজ করে (`_find_publication`), সেটি যেমন আছে তেমনই থাকবে।
- অব্যবহৃত parameter: admin এর `admin_id`, `_validate_tier(weight)`, `_should_dispatch` এর `query_type` ও `query_text` (domain এর guard থাকবে), `_adapt_query(query_type)`, `_score_article(claim_date)`, `get_my_profile(session)`।
- অব্যবহৃত setting field: `api_key_header`, `AppSettings.secret_key`, `request_timeout_seconds`, `max_headline_length`, `max_body_length`, `debug`, `decode_responses`, `ttl_embedding`/`ttl_nli_output`/`ttl_source_lookup`/`ttl_article_content`, `ml.device`/`use_fp16`/`cache_dir`, `pygooglenews_timeout_seconds`, `initial_expert_credibility`, `min_expert_votes_to_finalize`। এগুলো চালু করা হবে না, শুধু সরানো হবে। **`classification` থাকবে।**
- **যা রাখা হবে:** `ExpertVerdict`, legacy `SearchProvider`/`QueryType` member, `MetricState.NOT_APPLICABLE` (DB বা JSON এ পুরোনো মান থাকতে পারে), `reset_key_pools`, `PredictionResult.raw_logits`, `persisted`/`result_id`, `delete_expired`, `JobPhase`, `REDIS_KEY_PREFIX` (পরের ধাপে কাজে লাগবে)।
- git থেকে untrack করা হবে: ৯টি `.pyc`, `coverage.xml`। disk থেকে orphan `__pycache__` মুছে ফেলা হবে।

### ধাপ 4: Comment ও documentation সংশোধন (runtime এ কোনো প্রভাব নেই)
- Stale comment ঠিক করা হবে: photocard storage এর OCR docstring, S11 এর photo card date, S02 ও reuse এর "OCR record", multimodal model এর "MultimodalPrediction above", "12-stage", `PhotoCardService.verify`, `js_rendered` (প্রয়োজনে Playwright fallback), এবং `final_*` column এর comment।
- S02 এর docstring ছোট করা হবে, কিন্তু তিনটি invariant থাকবে।
- ইতিহাসের গল্প বলা comment ছোট করা হবে, তবে "কেন এটা এভাবে করা" অংশটুকু রাখা হবে। শুধু file path header ও "Migrated from" জাতীয় লাইন সরানো হবে।
- `json_schema_extra`: internal DTO গুলো থেকে সরানো হবে। public schema এর example গুলো ঠিক করা হবে (`google_rss` এর জায়গায় `internal_site`)। OpenAPI ছাড়া অন্য কোথাও কিছু বদলাবে না।

### ধাপ 5: Correctness fix (আচরণ একই থাকবে বা bug ঠিক হবে)
- `MultimodalModelLoader`: loaded এর অবস্থা ও weight একই instance এ রাখা হবে। lifespan এ একটি instance তৈরি হবে এবং সেটাই সবখানে ব্যবহার হবে।
- `list_predictions` এর `total` আসল গণনা দেবে (bug fix, frontend এটি ব্যবহার করে না)।
- `_raw_html_cache` কে `PipelineContext` এ `field(default_factory=dict)` হিসেবে ঘোষণা করা হবে। S05 ও S06 এর আচরণ একই থাকবে।
- `lifespan` এর shutdown এ `close_engine()` যোগ হবে। executor গুলো `shutdown(wait=False)` দিয়ে বন্ধ হবে, যাতে event loop আটকে না যায়।

### ধাপ 6: Performance (output একই থাকবে, প্রমাণসহ)
- **N+1 query:** `/dashboard/explorer` ও `/users/me/submissions` এ `MultimodalAnalysis`, `VerificationResult`, `PhotocardExtraction` এবং মূল submission এর status, পুরো page এর জন্য একবারে `IN (...)` দিয়ে আনা হবে। filter, visibility ও pagination একই থাকবে। ধাপ 1 এর snapshot test দিয়ে মিলিয়ে দেখা হবে।
- `/dashboard/stats`: ১১টি COUNT কে conditional aggregation দিয়ে ২–৩টি query তে আনা হবে, ফলাফল একই থাকবে।
- **Multimodal backbone একবার চালানো:** extractor থেকে পাওয়া আলাদা আলাদা raw image ও text feature (combined normalized vector নয়) tensor এ রূপান্তর করে classifier এ দেওয়া হবে। একই device, dtype ও `eval()` mode বজায় থাকবে। আগে একটি parity test লেখা হবে, যেখানে আসল weight দিয়ে পুরোনো আর নতুন পথের logits ও probability তুলনা করা হবে (tolerance ~1e-5)। parity প্রমাণ না হলে এই পরিবর্তন merge হবে না। শুধু fresh inference এর পথে সুবিধা হবে, duplicate পাওয়া গেলে inference এমনিতেই চলে না।

### ধাপ 7: ছোট ছোট structural refactor (প্রতিটি আলাদা commit)
- Fat router থেকে query ও mapping কে service বা repository তে সরানো হবে: dashboard, users, notifications, `expert/credibility`। health এর জন্য আলাদা file লাগবে না, শুধু ঘোষিত helper ব্যবহার করা হবে। error response এর আকার (`{"detail": …}`) **বদলাবে না**।
- Encapsulation: `ExpertReviewService.reevaluate()` public method যোগ হবে, যাতে escalation আর private member call না করে। locking এর শর্ত একই থাকবে। `PasswordPolicy` ও `to_me_response` public করা হবে। router এর জন্য service এ `get_visible_result()` যোগ হবে।
- Duplicate code: `sha256_hex`, image mean/std, digit map, upload validation (MIME, সীমা ও প্রতিটি feature এর error একই থাকবে), browser header, `UserRepository.increment_submission_count()`, reuse notification, credibility হিসাবের function (rounding ও threshold একই থাকবে)। tracking param, stopword ও negation এর তালিকা **এক করা হবে না**, শুধু তাদের মান যেমন আছে রেখে এক file এ আনা হবে।
- Model এর জায়গা বদল: `PhotocardExtraction` যাবে photocard এ, `RetrievedArticle`/`SourceEvidenceQuery` যাবে `verification/evidence` এ, `VerificationJob` যাবে `verification/jobs` এ। table এর নাম, `Base`, `models_registry` ও relationship string একই থাকবে, migration লাগবে না। প্রতিটি পরিবর্তনের পরে `alembic check` চালিয়ে নিশ্চিত হওয়া হবে যে কোনো schema diff তৈরি হয়নি।
- Enum: শুধু Python এর ভেতরে magic string এর জায়গায় `str, Enum` ব্যবহার হবে। যেখানে DB তে String column আছে, সেখানে column এর type **বদলাবে না** (আগের মতোই `.value` লেখা হবে)। নতুন কোনো `sa.Enum` mapping যোগ হবে না।
- Job handler registry (তিনটি handler, কোনো বড় framework ছাড়া)। retry, lock ও notification এর timing একই থাকবে।
- Gemini module ভাগ করা হবে (prompt, schema, key pool, client)। public function `extract_with_gemini` এর signature ও আচরণ একই থাকবে।

**এখন যা করা হবে না:** S06 এর extractor chain ভাঙা, material difference এর rule ভাঙা, MinIO এর দুটি service এক করা, transaction বা Unit of Work redesign, DI container, এবং পুরো package tree নতুন করে সাজানো। এগুলোতে ঝুঁকি বেশি, তাই আপনার আলাদা সিদ্ধান্ত লাগবে (section 5)।

---

## 4. আপনাকে নিজে যা করতে হবে (Manual)

| # | কখন | কাজ | কেন code দিয়ে হয় না |
|---|---|---|---|
| **M1** | ধাপ 2b এর আগে | একটি শক্তিশালী secret তৈরি করুন (`python -c "import secrets;print(secrets.token_urlsafe(48))"`) এবং `backend/.env` এ ও **সব deployment environment এ** `AUTH_SECRET_KEY=<মান>` যোগ করুন। তারপর আমাকে জানান, আমি তখন field টি required করব। | secret repo তে রাখা যাবে না। live environment আমি দেখতে পারি না। |
| **M2** | যত দ্রুত সম্ভব | `.env.example` এ যে SMTP app password ছিল, Google Account → Security → App passwords থেকে সেটি **revoke** করুন। নতুন app password তৈরি করে শুধু `.env` এ রাখুন। একই password `.env` এ থাকলে সেখানেও নতুনটা বসান, নাহলে OTP ও result email বন্ধ হয়ে যাবে। | Google account আপনার। |
| **M3** | ধাপ 2 এর পরে | `.env` এ `CORS_ORIGINS` দিন, JSON list আকারে: frontend এর URL (যেমন `http://localhost:4200` ও production domain) এবং extension এর origin (`chrome-extension://<extension-id>`)। প্রতিটি deployment এর জন্য আলাদা। | কোন origin অনুমোদিত হবে, সেটা deployment এর সিদ্ধান্ত। |
| **M4** | যেকোনো সময় | Admin account এর password বদলান (UI তে login করে "Change password")। migration এ hash প্রকাশিত, password দুর্বল হলে অনুমান করা যেতে পারে। | DB তে কী আছে, সেটা আপনার জানা। |
| **M5** | ধাপ 2 merge হওয়ার পরে | `.env` এ `ML_EMBEDDING_MODEL_NAME=sentence-transformers/LaBSE` বসান। (ধাপ 2 এর আগে এটা করবেন **না**, তাহলে photo card এর hash বদলে যাবে।) | `.env` git এ রাখা হয় না। |
| **M6** | ধাপ 3 এর আগে | Model weight এর একটি নিরাপদ copy রাখুন: `multimodal_model/` folder টি (৩টি `.pt` ও `tokenizer/`) Drive, release asset বা Git LFS এ upload করুন এবং link আমাকে দিন। আমি README তে download এর ধাপ লিখে `classifier.pt` untrack করব। মনে রাখুন, untrack করলে git history থেকে file টি মোছে না। repo এর আকার কমাতে চাইলে history rewrite (`git filter-repo`) লাগবে, এবং সেটা আলাদা সিদ্ধান্ত, যাতে collaborator দের আবার clone করতে হবে। | upload করার জায়গা ও account আপনার। |
| **M7** | ধাপ 2 এর পরে | নতুন dependency এর তালিকা দিয়ে নতুন venv বানিয়ে test করুন: `pip install -e .[dev]` তারপর `playwright install chromium`। | browser binary download করার কাজটা machine এ হয়। |
| **M8** | প্রতিটি ধাপের পরে | আমি unit test চালাব। আপনি নিজে UI তে একবার smoke test করুন: text claim জমা দিন, photo card দিন, multimodal দিন, expert হিসেবে vote দিন, admin হিসেবে dashboard দেখুন। (Real Postgres, MinIO ও Gemini quota এর উপর নির্ভরশীল বলে আমি পুরো E2E নিশ্চিতভাবে চালাতে পারি না।) | environment ও account এর প্রয়োজন |
| **M9** | ঐচ্ছিক | `docs/database-cleanup-2026-10-03.md` এ লিখে দিন যে `reset_operational_data.py` git history তে আছে (ধাপ 3 এ script টি সরালে)। | documentation এর সিদ্ধান্ত |

---

## 5. আপনার সিদ্ধান্ত লাগবে (এগুলো আচরণ, API বা data বদলায়)

এগুলো pure refactor নয়। আপনি "হ্যাঁ" না বলা পর্যন্ত আমি এগুলো করব না।

| # | বিষয় | প্রভাব | আমার পরামর্শ |
|---|---|---|---|
| D1 | `fix_source_configs.py` delete | DB তে নয়, শুধু repo তে | delete করুন। এর মান বর্তমান data এর সাথে মেলে না। |
| D2 | `reset_operational_data.py` delete | পুরোনো DB restore করে rehearsal আর করা যাবে না | delete করুন (git history তে থাকবে) |
| D3 | `seed_verified_sources.py` | — | রাখুন, তবে নাম বদলান এবং table খালি না হলে script যেন চলতে অস্বীকার করে (একটি guard যোগ হবে) |
| D4 | Sync endpoint `POST /verify`, `POST /multimodal/predict`, এবং অব্যবহৃত GET endpoint (`/multimodal/predict/{id}`, `/multimodal/predictions`, `/dashboard/stats`, `/dashboard/top-sources`, `/admin/stats`, `/expert/credibility`) | public API contract। এখন frontend বা extension এগুলো call করে না। | বাইরের কোনো consumer (যেমন thesis demo, Postman collection) না থাকলে সরান। এই মুহূর্তে রেখে দেওয়াই নিরাপদ। |
| D5 | `confidence_meaning`, `was_overridden` response field সরানো | API contract বদলায় | frontend এর type ও template থেকে সরানোর পরেই করুন। আমি দুই দিকেই একসাথে করতে পারি। |
| D6 | অব্যবহৃত DB column ও table সরানো (`is_published`, `view_count`, `credential_notes`, `expert_profiles.is_active`, `final_*`, `ai_consensus_label`, `ai_preliminary_label`, `source_evidence_queries`) | data সংরক্ষণের সিদ্ধান্ত, migration লাগবে | আপাতত রাখুন। thesis শেষ হওয়ার পরে backup নিয়ে সিদ্ধান্ত নিন। |
| D7 | Source resolution শুধু DB থেকে (`KNOWN_SOURCE_ALIASES` সরানো) | DB তে নেই এমন outlet (bdnews24, dhakatribune ইত্যাদি) এর claim আর গ্রহণ হবে না। deactivate করা source ও আর resolve হবে না। URL বা domain সরাসরি দিলে কী হবে, সেটাও ঠিক করতে হবে। | যদি এই আচরণটাই চান, তবে এটি আলাদা feature change হিসেবে করুন |
| D8 | Presenter এর hardcoded `INTERNAL_SITE` provider ঠিক করা | `RetrievedArticle` এ নতুন column লাগবে (migration), অথবা API তে `search_provider` কে nullable করতে হবে (frontend বদলাতে হবে) | এটা মিথ্যা data, তাই ঠিক করা উচিত। আমার পছন্দ: migration দিয়ে column যোগ করা, পুরোনো row এ `NULL` থাকবে। |
| D9 | `SubmissionSummary.submission_type` এর default ও history তে `SOURCE_BASED` fallback সরানো | response এ `null` আসতে পারে (শুধু যদি submission মুছে ফেলা হয়ে থাকে) | frontend এ nullable handling যোগ করার পরে করুন |
| D10 | DB ও MinIO credential required করা | dev setup এ `.env` বাধ্যতামূলক হবে | production এর জন্য হ্যাঁ, `MULTIMODAL_MODEL_DIR` এর জন্য না (multimodal বন্ধ থাকলেও app চালু হওয়া উচিত) |
| D11 | বড় redesign: Unit of Work বা transaction, DI container, S06 extractor chain, material difference rule class, MinIO adapter একীকরণ, পুরো package tree নতুন করে সাজানো | job হারিয়ে যাওয়া, duplicate processing, finding এর সংখ্যা বা verdict বদলে যাওয়ার ঝুঁকি | thesis এর deadline এর আগে **না**। প্রয়োজন হলে পরে, একটি একটি করে করুন। |

---

## 6. সংক্ষেপে কাজের ক্রম

1. **এখনই (আপনি):** M2 (SMTP revoke), M1 (`AUTH_SECRET_KEY`), M4 (admin password)।
2. **আমি:** ধাপ 1 (test safety net), তারপর ধাপ 2 (dependency, config, embedding এর নাম hash অপরিবর্তিত রেখে)।
3. **আপনি:** M3 (CORS origin), M5 (`.env` এ model এর নাম), M7 (নতুন venv)। এরপর আমি ধাপ 2b করব (secret required, CORS এর default `[]`)।
4. **আমি:** ধাপ 3, তারপর ধাপ 4, তারপর ধাপ 5 (M6 শেষ হলে `classifier.pt` untrack)।
5. **আমি:** ধাপ 6 (N+1, stats, multimodal parity)। **আপনি:** M8 smoke test।
6. **আমি:** ধাপ 7 এর ছোট ছোট refactor, প্রতিটির পরে test ও M8।
7. **আপনার সিদ্ধান্ত অনুযায়ী:** section 5 এর কাজগুলো।

প্রতিটি ধাপ শেষ হলে আমি জানাব: কোন file বদলেছে, test এর ফলাফল (baseline এর সাথে তুলনা করে), এবং কিছু অনিশ্চিত থাকলে সেটা কী।
