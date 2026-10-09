# Verified-source fallback ও search/UI উন্নয়নের পরিকল্পনা

তারিখ: ৮ অক্টোবর ২০২৬। অবস্থা: implementation plan; application code পরিবর্তন করা হয়নি।

## ১. লক্ষ্য ও অপরিবর্তিত আচরণ

Existing claimed-source verification বজায় রেখে source ছাড়া বা অচেনা/inactive source-সহ claim গ্রহণ করতে হবে। নতুন পথে Google দিয়ে article খোঁজা হবে এবং শুধু active verified publisher-এর article fetch ও compare করা হবে। Multimodal prediction, expert verdict, authorization এবং existing comparison thresholds অপরিবর্তিত থাকবে।

Duplicate বিষয়ে গৃহীত অর্থ: একই সম্পূর্ণ verification আবার চালানো যাবে না; পুনরায় submit করলে আগের result দেখাবে। এটি duplicate request গ্রহণ করা, নতুন করে verification করা নয়। Failed/incomplete কাজের recovery বিদ্যমান retry policy অনুযায়ী থাকবে; সেগুলোকে complete cached answer ধরা হবে না।

## ২. বর্তমান কোডে পাওয়া বিষয়

| অংশ | বর্তমান আচরণ / সংশ্লিষ্ট file |
|---|---|
| Text input | `backend/app/features/verification/schemas.py`-তে source required; `service.py` registration ও execution-এ unresolved source reject করে |
| Pipeline | `s01_normalizer.py` ও `s04_source_search.py` source ছাড়া এগোয় না; S04 internal-site ও Google provider ব্যবহার করে |
| Photocard | `photocard/claim_extraction.py` headline অথবা recognized source না পেলে reject করে; `photocard/service.py`-তেও source-dependent processing আছে |
| Identity | `shared/utils/hashing.py` headline, body, source, date, scope ও version দিয়ে identity তৈরি করে |
| Reuse | `verification/reuse.py` complete compatible result reuse করে; registration একই owner-এর পুরোনো result ফেরত দিতে পারে |
| Evidence | `verification/presenter.py` সর্বোচ্চ ৩টি article নেয়; UI `verification-report.component.html`-এ `slice(0, 1)` |
| Search | Fact Explorer, review queue/history-তে পুরো search string-এর `ILIKE` substring match আছে; keyword-wise ranking নেই |
| Layout | `main-layout`-এ navbar/footer আছে; `auth-layout`-এ নেই |

## ৩. দুটি explicit verification mode

| Input | Mode | Search | Fetch scope |
|---|---|---|---|
| User active verified source select করেছে | `CLAIMED_SOURCE` | Existing Google + configured internal search | শুধু selected source |
| User source select করেনি | `VERIFIED_SOURCES` | Google only | Active verified sources |
| Photocard headline ও active source পাওয়া গেছে | `CLAIMED_SOURCE` | Existing behavior | Detected source |
| Photocard headline আছে, source পাওয়া যায়নি | `VERIFIED_SOURCES` | Google only | Active verified sources |
| Photocard/source text পরিচিত active source-এর সঙ্গে মেলেনি | `VERIFIED_SOURCES` | Google only | Active verified sources |
| Headline পাওয়া যায়নি / extraction API ব্যর্থ | Existing failure handling | Verification চালানো যাবে না | প্রযোজ্য নয় |

Mode server নির্ধারণ করবে। Unknown source-কে কোনো verified publisher হিসেবে অনুমান করা যাবে না। Raw detected source text থাকলে provenance হিসেবে রাখা হবে; সেটি evidence scope অনুমোদন করবে না।

## ৪. Backend পরিবর্তন

### Input, storage ও photocard

- Request schema-তে source optional; missing/null/blank একইভাবে normalize করা হবে। Headline/body/date validation থাকবে।
- Submission/context/result-এ explicit `verification_mode`, `source_resolution_reason`, nullable resolved source এবং evidence-scope metadata যোগ হবে। Reason: selected/detected active source, not supplied, not detected, unrecognized বা inactive।
- Photocard extraction-এ usable headline থাকলে missing/unrecognized source আর failure হবে না। Gemini response/prompt/schema source uncertainty ও raw visible outlet text সংরক্ষণ করতে পারবে। Date আগের মতো optional এবং অনুমান করা হবে না।
- Extraction-success resume condition থেকে mandatory source dependency সরাতে হবে; source-null অবস্থায় crash/restart recovery-ও চলবে।
- Migration additive হবে; পুরোনো source-based result-কে claimed-source mode হিসেবে পড়া হবে। Multimodal row-তে অপ্রযোজ্য mode বসানো হবে না।

### S01–S06: scope, search, fetch ও extraction

- Shared source-resolution policy registration, photocard ও pipeline-এ ব্যবহার হবে; একই input ভিন্ন জায়গায় ভিন্ন mode পাবে না।
- `CLAIMED_SOURCE` path-এর query/provider behavior অপরিবর্তিত রাখা হবে।
- `VERIFIED_SOURCES`-এ provider list শুধু existing Google News client হবে। Internal-site client dispatch ও তার cached candidate reuse—দুটিই নিষিদ্ধ থাকবে। “Google only” নতুন paid provider যোগ করার দাবি নয়।
- Active source registry থেকে allowed domains ও publisher-specific extraction configuration তৈরি হবে। Empty registry unrestricted search/fetch অনুমোদন করবে না; result হবে incomplete with reason।
- Google query-তে bounded domain groups দিয়ে source restriction এবং প্রয়োজনে সীমিত expansion হবে। প্রতিটি source × প্রতিটি query চালিয়ে request সংখ্যা গুণ করা হবে না। Query-length/coverage behavior integration test-এ যাচাই করে group size নির্ধারণ করতে হবে।
- Search candidate fetch করার আগেই allowlist যাচাই হবে। Redirect destination, canonical evidence URL ও cached article-ও যাচাই হবে। Arbitrary off-source URL evidence হিসেবে গ্রহণ করা যাবে না। Existing Google link resolution প্রয়োজন হলে discovery ধাপেই destination resolve করতে হবে।
- Fetch-এর সময় publisher এখনও active কি না revalidate করতে হবে। Registry বদলে scope অসম্পূর্ণ হলে নীরবে confident negative দেওয়া যাবে না।
- প্রতিটি candidate-এ resolved publisher identity থাকবে। S06 একটিমাত্র claimed-source config-এর বদলে article-এর publisher অনুযায়ী title/body/date selectors ব্যবহার করবে।

### S07–S13: comparison ও persistence

- Existing relevance/correspondence এবং headline/date/body comparison reuse হবে; নতুন truth model বা threshold পরিবর্তন হবে না।
- Fallback ranking-এ claimed-domain bonus-এর বদলে eligible verified-domain handling স্পষ্ট করতে হবে, যাতে source-null হওয়ার কারণে ভালো article নিচে না নামে।
- S08 একই report-এর correspondence খুঁজবে। কেবল কয়েকটি topic keyword মেলা মানেই report found নয়।
- S08 যে primary article নির্বাচন করবে, headline, date ও body comparison একই article-এর বিরুদ্ধে চলবে। তিন article-এর সুবিধাজনক অংশ মিলিয়ে একটি verdict বানানো হবে না।
- সর্বোচ্চ ৩টি unique relevant article দেখানো হবে; কম পেলে কমই থাকবে। Primary comparison article প্রথমে, তারপর relevance order। Primary article rank-এর প্রথম ৩টির বাইরে থাকলেও response-এ অবশ্যই থাকবে; বর্তমান limit-before-primary-sort আচরণ ঠিক করতে হবে।
- Headline comparison title-only; body থাকলে existing চারটি similarity measurement; date থাকলে `MATCHED`/`MISMATCHED`/`INCOMPLETE`। Body scores-কে নতুন binary “data matched” verdict বানানো হবে না।
- Source status enum compatibility রাখা হবে: backend `CONFIRMED` → UI Found, `NOT_FOUND` → Not found; failure/insufficient coverage → `INCOMPLETE`।
- Fallback result original photocard publisher সত্যিই headline প্রকাশ করেছে—এমন দাবি করবে না। এটি selected verified article-এর সঙ্গে তুলনা।
- Mode, eligible source snapshot/revision, Google search accounting, primary article, evidence publishers ও fallback reason persist হবে; live, history এবং reused result একই presenter দিয়ে দেখাবে।

## ৫. Cache ও duplicate isolation

Verification identity-তে থাকবে normalized headline/body, claimed date, claim scope, verification mode, claimed-source identity অথবা verified-source scope fingerprint, এবং compatible pipeline-policy version।

- একই headline + source A, একই headline + source B এবং source ছাড়া headline তিনটি আলাদা verification context।
- Claim/result cache এবং search cache-এ mode, provider policy ও source scope আলাদা থাকবে। পুরোনো internal-search result fallback Google search হিসেবে ব্যবহার হবে না।
- Article content cache URL-ভিত্তিক share করা যেতে পারে, কিন্তু ব্যবহার করার আগে বর্তমান publisher eligibility যাচাই করতে হবে; raw content reuse ও verification-result reuse আলাদা বিষয়।
- Source activation/domain পরিবর্তনে verified-scope fingerprint বদলাবে। পুরোনো result historical snapshot হিসেবে থাকবে; নতুন scope-এর result হিসেবে mislabeled reuse হবে না। Scope পরিবর্তন একটি আলাদা verification context, একই submission reverify নয়।
- Existing completed submission GET/reopen করলে তার immutable result-ই দেখাবে; deployment বা Redis expiry সেটিকে rerun করবে না। অপরিবর্তিত claimed-source logic-এর existing compatible identities বজায় রাখতে legacy-compatible lookup লাগবে; global version bump দিয়ে অকারণে সব result invalidate করা যাবে না।
- Same-owner complete duplicate → existing result; processing duplicate → existing progress। Different owner → নিজস্ব authorized submission/reference, shared computation/result; অন্যের private metadata প্রকাশ নয়।
- Concurrent request-এর জন্য DB-backed atomic identity coordination ও uniqueness থাকবে; শুধু read-then-enqueue যথেষ্ট নয়। Worker retry/restart একই computation resume করবে। Notifications/expert queue-তে duplicate কাজ তৈরি হবে না।
- Photocard-এ exact image digest দিয়ে same-owner upload reuse করা যায়; ভিন্ন image কিন্তু extracted claim identity একই হলে extraction-এর পরে verification reuse হবে।
- Complete result থাকা duplicate-এর জন্য নতুন Google/internal search, article fetch বা model comparison হবে না। Incomplete/failed result complete cache-এ ঢুকবে না।

## ৬. UI পরিবর্তন

- Source dropdown label: `Claimed source (optional)`। Empty option: `Search verified sources`। Helper: `If no source is selected, we will look for related reports from active verified news sources.`
- Photocard-এ headline পাওয়া গেলে source missing/inactive হওয়ার ব্যাখ্যা এবং verified-source verification progress দেখাবে; source শনাক্ত না হওয়ার কারণে rejection নয়।
- Claimed mode label: `Relevant article from claimed source`। Fallback: `Relevant articles from verified sources`।
- Fallback messages: `Related reports found in verified sources.`, `No matching report was found in the verified sources searched.`, অথবা `Verification could not be completed.` সঙ্গে কারণ। Search failure-কে Not found হিসেবে দেখানো যাবে না।
- Article card-এ publisher, headline, link, publication date যখন পাওয়া যায়, এবং primary article marker থাকবে। সর্বোচ্চ তিনটি দেখাবে।
- Headline verdict-এর পাশে `Compared with the selected verified-source article` ধরনের context থাকবে; source attribution verified হয়েছে বলে বোঝাবে না।
- Duplicate message: `This claim was already verified. Showing the saved result.` In-flight হলে existing progress দেখাবে। No “Verify again” action for completed submission।
- Shared report component বদলে result page, photocard, expert review, history-তে একই semantics থাকবে। Fact Explorer/source filters-এ claimed source ও evidence publisher-এর পার্থক্য বজায় থাকবে।
- Extension-এ প্রয়োজনীয় optional-source validation, API types ও compact result wording মিলিয়ে compatibility নিশ্চিত করতে হবে।

## ৭. সব website page-এ navbar ও footer

- Shared outer shell reuse করে auth routes-সহ সব website route-এ একবার navbar/header এবং footer render হবে। Auth form-এর centered card layout থাকবে।
- Login, registration, forgot-password, 404, public এবং role-protected route audit করতে হবে। Guards ও redirect rules অপরিবর্তিত থাকবে।
- Mobile navigation, fixed-header spacing, keyboard skip link এবং footer placement যাচাই করতে হবে। Nested shell-এ double navbar/toast/footer হবে না।

## ৮. Keyword-based application search

এটি queue/history/Fact Explorer-এর database search; verification-এর Google evidence search থেকে আলাদা।

- Repository জুড়ে search control inventory করে queue, review history, Fact Explorer, submission history এবং অন্য searchable list-এ consistent policy প্রয়োগ করতে হবে। Local-only list-এর ক্ষেত্রে একই semantics; paginated list-এর search backend-এ হবে।
- Bangla/English Unicode ও whitespace normalize; query unique keyword-এ ভাগ; safe parameter binding এবং `%`/`_` escaping।
- Keywords-এর OR matching: তিনটি লিখলে যেকোনো meaningful keyword মেলা item eligible। সব শব্দ একই ক্রমে থাকা লাগবে না।
- Order: বেশি distinct keyword match আগে; সমান হলে full phrase match ও headline match অগ্রাধিকার; তারপর existing date/order ও stable ID tie-break। একই শব্দ বহুবার থাকলে score বাড়বে না।
- Filtering/ranking pagination-এর আগে হবে; count query একই condition ব্যবহার করবে। Existing role/ownership/status/date filters বজায় থাকবে। Empty query-তে existing ordering।
- UI debounce আনুমানিক 300 ms, previous request cancellation, search বদলালে প্রথম page, এবং clear/no-results state।
- Shared query helper দিয়ে ছোট bounded query implement করা হবে। Representative data-তে query plan/latency দেখে indexed normalized text ও প্রয়োজনে PostgreSQL trigram index যোগ হবে; Bangla matching পরীক্ষা ছাড়া English stemming ব্যবহার নয়।
- উদাহরণ: “ঢাকা বাস দুর্ঘটনা” → ৩ keyword match আগে, তারপর ২, তারপর ১; exact phrase থাকলে একই keyword-count group-এ এগিয়ে থাকবে।

## ৯. Performance সুরক্ষা

- একই fixture, source set এবং comparable load-এ current claimed-source baseline মাপতে হবে: p50/p95 latency, queue wait, provider calls, fetched articles, model calls, cache hit rate। Existing timing document ছোট historical sample; performance guarantee হিসেবে যথেষ্ট নয়।
- Fallback query count, candidate count, fetch concurrency, per-domain rate এবং total timeout bounded/configurable হবে। UI-তে ৩ article মানে মাত্র ৩ candidate search করা নয়।
- Shared model service reuse হবে; নতুন model load নয়। Repeated title/claim embedding reuse বা batch করা যাবে যেখানে equivalence বজায় থাকে।
- Fallback work-এর concurrency cap/worker admission limit থাকবে, যাতে claimed-source jobs অপেক্ষায় পড়ে না যায়।
- Search incomplete বা budget exhaustion হলে coverage accounting অনুযায়ী incomplete status; negative-result cache নয়।
- প্রস্তাবিত release gate: comparable controlled run-এ claimed-source p95 regression ৫%-এর বেশি নয় এবং existing fixture verdict অপরিবর্তিত। Measurement noise ও baseline দেখে gate finalize হবে; এখনই speed guarantee নয়।

## ১০. বাস্তবায়নের ক্রম

1. Baseline ও regression fixtures; modes, duplicate contract এবং response semantics স্থির করা।
2. Additive migration, centralized identity/source policy ও backward-compatible schema।
3. Feature flag-এর পেছনে Google-only fallback এবং per-publisher retrieval/extraction।
4. Photocard acceptance, persistent result/presenter এবং duplicate concurrency handling।
5. Optional-source form, mode-aware shared report, top-three evidence ও extension compatibility।
6. Shared navbar/footer এবং keyword-ranked application search আলাদা পরিবর্তন হিসেবে।
7. Integration/load checks, migration compatibility, সীমিত rollout; সমস্যা হলে নতুন fallback disable করে existing mode চালু রাখা। Accepted fallback jobs-কে ভুল করে claimed-source path-এ পাঠানো যাবে না।

## ১১. Acceptance checks

- Active claimed-source input-এ আগের provider calls, source restriction ও verdict fixtures অপরিবর্তিত।
- Missing/unrecognized/inactive source ও headline-present photocard accepted; fallback-এ internal provider call count ঠিক ০।
- Inactive/off-list publisher, deceptive hostname ও off-source redirect evidence হিসেবে rejected। সঠিক publisher selectors ব্যবহৃত।
- Google failure, no active sources, failed retrieval এবং inadequate coverage-এ incomplete; adequate empty search-এ not found।
- Source found না হলে headline verdict বানানো নয়; date/body missing হলে appropriate existing unavailable/not-applicable behavior।
- Mode/source/body/date/scope/version আলাদা হলে ভুল result reuse হয় না; Redis না থাকলেও durable reuse কাজ করে।
- Concurrent duplicate, worker restart, photocard duplicate, same/different owner এবং guest access tests; complete duplicate-এ নতুন verification work নেই।
- ০/১/২/৩ evidence, duplicate URL, primary article rank > 3 এবং refresh/history/reuse presentation consistent।
- তিন-keyword search-এ partial match আসে, বেশি match আগে, pagination/count stable এবং authorization filters অক্ষুণ্ণ।
- সব website route-এ একবার navbar/footer; mobile ও auth navigation ঠিক। Existing multimodal/expert-finalization tests pass।

## ১২. স্পষ্ট সীমারেখা

“Found” মানে active verified source-এ corresponding report পাওয়া গেছে; এটি স্বয়ংক্রিয় overall truth verdict নয়। “Not found” মানে searched scope-এ matching report পাওয়া যায়নি, claim মিথ্যা প্রমাণ নয়। Existing expert-finalized verdict আলাদাই থাকবে।

ব্যবহারকারীর “data matched/mismatched” বক্তব্যকে existing date matched/mismatched এবং body similarity behavior বজায় রাখার অর্থে ধরা হয়েছে; নতুন binary body-data verdict এই পরিকল্পনায় নেই।
