# Backend file/function/schema/route reference

প্রস্তুত: ৯ অক্টোবর ২০২৬। আগে [বাংলা study guide](<E:/8th Sem/SPL3/Main/BanglaFactGuard/docs/backend-study-guide-bn.md>) পড়বে। এখানে **backend-এর সব project Python file**-এর index আছে; third-party `.venv`, caches, generated coverage ও secret `.env` content অন্তর্ভুক্ত নয়। Non-Python support/model artifacts শেষে আলাদা inventory আছে।

প্রতিটি file-এর feature/location, দায়িত্ব, declared classes/functions এবং schema/model fields দেওয়া হয়েছে। বাংলা notes-এর সঙ্গে প্রয়োজনমতো original English docstring রাখা হয়েছে। Docstring/route description historical হতে পারে; বিশেষত photocard-এ source না-পেলে current enabled fallback এবং image থেকে claim নেওয়ার behavior মূল guide-এ ব্যাখ্যা করা হয়েছে।

আরেকটি current-code distinction: NOT_FOUND-এর Redis pointer-এর expiry কম হলেও database result reuse-তে age limit নেই। Config/source docstring-এর freshness দাবি actual reusable-result function-এর অতিরিক্ত শর্ত হিসেবে ধরে নেবে না।

এটি static source inspection; live endpoint/model/database পরীক্ষা বা test execution-এর দাবি নয়। Function source links exact declaration line-এ যায়। `__init__` dependency wiring; underscore-prefixed functions internal helpers। Inherited CRUD methods BaseRepository section-এ।

## সম্পূর্ণ API route index

Base prefix `app/api/v1/router.py` থেকে `/api/v1`; feature prefix এবং decorator path সরাসরি AST থেকে নেওয়া। Dependency names access guard চিনতে সাহায্য করে; কিছু additional authorization service-এর ভেতরে আছে।

| Method | Full path | Handler / source | Response | Dependency / input |
|---|---|---|---|---|
| POST | `/api/v1/admin/experts` | [create_expert](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:51>) | ExpertResponse | body: CreateExpertRequest, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service) |
| GET | `/api/v1/admin/experts` | [list_experts](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:64>) | list[ExpertResponse] | limit: int=Query(default=50, ge=1, le=200), offset: int=Query(default=0, ge=0), q: str \| None=Query(default=None, max_length=200, description='Search name, email or expertise'), _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service) |
| GET | `/api/v1/admin/experts/{expert_id}` | [get_expert](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:79>) | ExpertResponse | expert_id: uuid.UUID, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service) |
| PUT | `/api/v1/admin/experts/{expert_id}` | [update_expert](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:92>) | ExpertResponse | expert_id: uuid.UUID, body: UpdateExpertRequest, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service) |
| POST | `/api/v1/admin/experts/{expert_id}/reset-password` | [reset_expert_password](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:105>) | explicit response / inferred | expert_id: uuid.UUID, body: ResetExpertPasswordRequest, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service) |
| POST | `/api/v1/admin/experts/{expert_id}/deactivate` | [deactivate_expert](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:119>) | ExpertResponse | expert_id: uuid.UUID, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service) |
| POST | `/api/v1/admin/experts/{expert_id}/activate` | [activate_expert](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:132>) | ExpertResponse | expert_id: uuid.UUID, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service) |
| GET | `/api/v1/admin/stats` | [get_platform_stats](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:145>) | AdminStatsResponse | _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service) |
| GET | `/api/v1/admin/dashboard` | [get_dashboard](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:157>) | AdminDashboardResponse | _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service) |
| GET | `/api/v1/admin/credibility-tiers` | [list_credibility_tiers](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:174>) | list[CredibilityWeightTierResponse] | _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service) |
| POST | `/api/v1/admin/credibility-tiers` | [create_credibility_tier](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:187>) | CredibilityWeightTierResponse | body: CredibilityWeightTierRequest, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service) |
| PUT | `/api/v1/admin/credibility-tiers/{tier_id}` | [update_credibility_tier](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:200>) | CredibilityWeightTierResponse | tier_id: uuid.UUID, body: CredibilityWeightTierUpdateRequest, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service) |
| DELETE | `/api/v1/admin/credibility-tiers/{tier_id}` | [delete_credibility_tier](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:214>) | explicit response / inferred | tier_id: uuid.UUID, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service) |
| GET | `/api/v1/admin/voting-config` | [get_voting_config](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:231>) | VotingConfigResponse | _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service) |
| PUT | `/api/v1/admin/voting-config` | [update_voting_config](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:243>) | VotingConfigResponse | body: VotingConfigUpdateRequest, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service) |
| POST | `/api/v1/auth/register` | [register](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:45>) | UserMeResponse | body: RegisterRequest, svc: AuthService=Depends(_get_auth_service) |
| POST | `/api/v1/auth/login` | [login](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:70>) | TokenResponse | body: LoginRequest, svc: AuthService=Depends(_get_auth_service) |
| POST | `/api/v1/auth/refresh` | [refresh_token](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:83>) | TokenResponse | body: RefreshRequest, svc: AuthService=Depends(_get_auth_service) |
| POST | `/api/v1/auth/logout` | [logout](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:95>) | explicit response / inferred | body: RefreshRequest, svc: AuthService=Depends(_get_auth_service) |
| GET | `/api/v1/auth/me` | [me](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:107>) | UserMeResponse | current_user: User=Depends(get_current_user) |
| POST | `/api/v1/auth/password-reset/request` | [request_password_reset](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:118>) | explicit response / inferred | body: PasswordResetRequest, svc: AuthService=Depends(_get_auth_service) |
| POST | `/api/v1/auth/password-reset/confirm` | [confirm_password_reset](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:131>) | explicit response / inferred | body: PasswordResetConfirm, svc: AuthService=Depends(_get_auth_service) |
| POST | `/api/v1/auth/change-password` | [change_password](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:148>) | explicit response / inferred | body: ChangePasswordRequest, current_user: User=Depends(get_current_user), svc: AuthService=Depends(_get_auth_service) |
| GET | `/api/v1/dashboard/stats` | [get_public_stats](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/router.py:41>) | PublicStatsResponse | svc: DashboardService=Depends(_service) |
| GET | `/api/v1/dashboard/top-sources` | [get_top_sources](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/router.py:52>) | list[TopSourceItem] | limit: int=Query(default=10, ge=1, le=50), svc: DashboardService=Depends(_service) |
| GET | `/api/v1/dashboard/explorer` | [search_explorer](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/router.py:72>) | ExplorerSearchResponse | keyword: str \| None=Query(default=None, max_length=255), source_status: SourceStatus \| None=Query(default=None), content_status: ContentStatus \| None=Query(default=None), date_status: DateStatus \| None=Query(default=None), overall_verdict: OverallVerdict \| None=Query(default=None, description='Matches only expert-finalized claims — spans every submission type, unlike source/content/date_status which only apply to SOURCE_BASED/PHOTO_CARD.'), method: SubmissionType \| None=Query(default=None), date_from: date \| None=Query(default=None), date_to: date \| None=Query(default=None), source_id: uuid.UUID \| None=Query(default=None), review_state: Literal['finalized', 'review'] \| None=Query(default=None), limit: int=Query(default=20, ge=1, le=100), offset: int=Query(default=0, ge=0), svc: DashboardService=Depends(_service) |
| GET | `/api/v1/expert/queue` | [get_queue](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/router.py:68>) | list[ExpertQueueItemResponse] | limit: int=Query(default=20, ge=1, le=100), offset: int=Query(default=0, ge=0), q: str=Query(default='', max_length=200), state: Literal['all', 'escalated', 'review']=Query(default='all', description='Admin queue only: all \| escalated (awaiting an admin decision) \| review (open, view-only).'), current_user: User=Depends(_EXPERT_OR_ADMIN), svc: ExpertReviewService=Depends(_get_service) |
| GET | `/api/v1/expert/queue/{submission_id}` | [get_queue_item](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/router.py:89>) | ExpertQueueItemResponse | submission_id: uuid.UUID, current_user: User=Depends(_EXPERT_OR_ADMIN), svc: ExpertReviewService=Depends(_get_service) |
| POST | `/api/v1/expert/queue/{submission_id}/vote` | [submit_vote](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/router.py:111>) | ExpertReviewResponse | submission_id: uuid.UUID, body: ExpertVoteRequest, current_user: User=Depends(_EXPERT_OR_ADMIN), svc: ExpertReviewService=Depends(_get_service) |
| PUT | `/api/v1/expert/reviews/{review_id}` | [edit_vote](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/router.py:134>) | ExpertReviewResponse | review_id: uuid.UUID, body: ExpertVoteUpdateRequest, current_user: User=Depends(_EXPERT_ONLY), svc: ExpertReviewService=Depends(_get_service) |
| GET | `/api/v1/expert/history` | [get_history](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/router.py:156>) | list[ExpertHistoryItemResponse] | limit: int=Query(default=50, ge=1, le=200), offset: int=Query(default=0, ge=0), q: str=Query(default='', max_length=200), current_user: User=Depends(_EXPERT_OR_ADMIN), svc: ExpertReviewService=Depends(_get_service) |
| GET | `/api/v1/expert/stats` | [get_stats](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/router.py:171>) | ExpertStatsResponse | current_user: User=Depends(_EXPERT_OR_ADMIN), svc: ExpertReviewService=Depends(_get_service) |
| GET | `/api/v1/expert/credibility` | [get_credibility](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/router.py:183>) | CredibilityScoreResponse | current_user: User=Depends(_EXPERT_OR_ADMIN), svc: ExpertReviewService=Depends(_get_service) |
| GET | `/api/v1/health` | [liveness](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/health/router.py:30>) | HealthResponse |  |
| GET | `/api/v1/health/ready` | [readiness](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/health/router.py:40>) | ReadinessResponse | cache: CacheService=Depends(get_cache_service) |
| POST | `/api/v1/multimodal/predict/async` | [predict_async](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/router.py:46>) | explicit response / inferred | request: Request, headline: str=Form(..., min_length=1, max_length=2000), body_text: str=Form(..., min_length=10, max_length=50000), image: UploadFile=File(...), db: AsyncSession=Depends(get_async_session), current_user: User \| None=Depends(get_current_user_optional) |
| POST | `/api/v1/multimodal/predict` | [predict](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/router.py:145>) | MultimodalPredictionResponse | request: Request, headline: str=Form(..., min_length=1, max_length=2000, description='News headline (stored for display; not used by the model)'), body_text: str=Form(..., min_length=10, max_length=50000, description='Article body text — the text input to the BanglaBERT backbone'), image: UploadFile=File(..., description='News article image (JPEG/PNG/WebP, max 10 MB)'), db: AsyncSession=Depends(get_async_session), current_user: User \| None=Depends(get_current_user_optional) |
| GET | `/api/v1/multimodal/predict/{prediction_id}` | [get_prediction](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/router.py:221>) | MultimodalPredictionDetail | prediction_id: uuid.UUID, request: Request, db: AsyncSession=Depends(get_async_session) |
| GET | `/api/v1/multimodal/by-submission/{submission_id}` | [get_prediction_by_submission](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/router.py:252>) | MultimodalPredictionDetail | submission_id: uuid.UUID, request: Request, db: AsyncSession=Depends(get_async_session) |
| GET | `/api/v1/multimodal/predictions` | [list_predictions](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/router.py:277>) | PredictionListResponse | request: Request, limit: int=Query(default=20, ge=1, le=100, description='Number of results to return'), offset: int=Query(default=0, ge=0, description='Pagination offset'), db: AsyncSession=Depends(get_async_session) |
| GET | `/api/v1/notifications` | [list_notifications](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/router.py:22>) | list[NotificationResponse] | limit: int=Query(default=30, ge=1, le=100), offset: int=Query(default=0, ge=0), unread_only: bool=Query(default=False), current_user: User=Depends(get_current_user), repo: NotificationRepository=Depends(_repo) |
| GET | `/api/v1/notifications/count` | [get_unread_count](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/router.py:47>) | UnreadCountResponse | current_user: User=Depends(get_current_user), repo: NotificationRepository=Depends(_repo) |
| POST | `/api/v1/notifications/{notification_id}/read` | [mark_read](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/router.py:59>) | explicit response / inferred | notification_id: uuid.UUID, current_user: User=Depends(get_current_user), repo: NotificationRepository=Depends(_repo) |
| POST | `/api/v1/notifications/read-all` | [mark_all_read](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/router.py:72>) | explicit response / inferred | current_user: User=Depends(get_current_user), repo: NotificationRepository=Depends(_repo) |
| POST | `/api/v1/photocard/verify/async` | [verify_photocard_async](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/router.py:77>) | PhotoCardAcceptedResponse | http_request: Request, image: UploadFile=File(..., description='Photo card or screenshot (JPEG/PNG/WebP/GIF, max 10 MB)'), service: PhotoCardService=Depends(get_photocard_service), current_user: User \| None=Depends(get_current_user_optional) |
| GET | `/api/v1/photocard/{submission_id}` | [get_photocard_result](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/router.py:111>) | PhotoCardResultResponse | submission_id: uuid.UUID, service: PhotoCardService=Depends(get_photocard_service), current_user: User \| None=Depends(get_current_user_optional) |
| GET | `/api/v1/sources` | [list_sources](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/router.py:28>) | SourceListSchema | language: str \| None=Query(None, description="Filter by language code (e.g. 'bn', 'en')"), page: int=Query(1, ge=1, description='Page number (1-indexed)'), size: int=Query(20, ge=1, le=100, description='Results per page'), include_inactive: bool=Query(False, description='Include deactivated sources (admin management use). Public callers — e.g. the claimed-source dropdown — should omit this so only active sources are returned.'), q: str \| None=Query(None, max_length=200, description='Search name, domain, URL or aliases'), service: SourceService=Depends(get_source_service) |
| POST | `/api/v1/sources` | [create_source](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/router.py:58>) | SourceResponseSchema | payload: SourceCreateSchema, _: User=Depends(_ADMIN_ONLY), service: SourceService=Depends(get_source_service) |
| GET | `/api/v1/sources/{source_id}` | [get_source](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/router.py:77>) | SourceResponseSchema | source_id: uuid.UUID, service: SourceService=Depends(get_source_service) |
| PUT | `/api/v1/sources/{source_id}` | [update_source](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/router.py:95>) | SourceResponseSchema | source_id: uuid.UUID, payload: SourceUpdateSchema, _: User=Depends(_ADMIN_ONLY), service: SourceService=Depends(get_source_service) |
| DELETE | `/api/v1/sources/{source_id}` | [delete_source](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/router.py:115>) | explicit response / inferred | source_id: uuid.UUID, _: User=Depends(_ADMIN_ONLY), service: SourceService=Depends(get_source_service) |
| GET | `/api/v1/submissions/{submission_id}` | [get_submission](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/router.py:32>) | SubmissionLookupResponse | submission_id: uuid.UUID, session: AsyncSession=Depends(get_async_session), current_user: User \| None=Depends(get_current_user_optional) |
| GET | `/api/v1/submissions/{submission_id}/voting-details` | [get_voting_details](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/router.py:86>) | PublicVotingDetails | submission_id: uuid.UUID, session: AsyncSession=Depends(get_async_session) |
| GET | `/api/v1/users/me/submissions` | [get_my_submissions](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/router.py:32>) | list[SubmissionSummary] | limit: int=Query(default=20, ge=1, le=100), offset: int=Query(default=0, ge=0), q: str \| None=Query(default=None, max_length=200, description='Keyword search over headline, text and outlet'), state: Literal['in_progress', 'review', 'final', 'failed'] \| None=Query(default=None), submission_type: SubmissionType \| None=Query(default=None, alias='type'), current_user: User=Depends(get_current_user), svc: UserAccountService=Depends(_service) |
| GET | `/api/v1/users/me/submissions/stats` | [get_my_submission_stats](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/router.py:47>) | SubmissionStatsResponse | current_user: User=Depends(get_current_user), svc: UserAccountService=Depends(_service) |
| GET | `/api/v1/users/me/profile` | [get_my_profile](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/router.py:55>) | ProfileResponse | current_user: User=Depends(get_current_user), svc: UserAccountService=Depends(_service) |
| PUT | `/api/v1/users/me/profile` | [update_my_profile](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/router.py:63>) | ProfileResponse | body: UpdateProfileRequest, current_user: User=Depends(get_current_user), svc: UserAccountService=Depends(_service) |
| POST | `/api/v1/verify` | [verify_claim](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/router.py:47>) | VerificationResponse | request: VerificationRequest, service: VerificationService=Depends(get_verification_service), current_user: User \| None=Depends(get_current_user_optional) |
| POST | `/api/v1/verify/async` | [verify_claim_async](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/router.py:94>) | VerificationQueuedResponse | request: VerificationRequest, http_request: Request, service: VerificationService=Depends(get_verification_service), current_user: User \| None=Depends(get_current_user_optional) |
| GET | `/api/v1/verify/{submission_id}` | [get_verification_result](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/router.py:138>) | VerificationResponse | submission_id: uuid.UUID, service: VerificationService=Depends(get_verification_service), current_user: User \| None=Depends(get_current_user_optional) |
| GET | `/api/v1/verify/{submission_id}/status` | [get_verification_status](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/router.py:162>) | VerificationStatusResponse | submission_id: uuid.UUID, submission_repo: SubmissionRepository=Depends(get_submission_repo), service: VerificationService=Depends(get_verification_service), current_user: User \| None=Depends(get_current_user_optional) |

## Runtime files: feature অনুযায়ী বিস্তারিত

### backend/app/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/__init__.py>) · 0 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/api/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/api/__init__.py>) · 0 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/api/exception_handlers.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/api/exception_handlers.py>) · 52 lines

Domain exception ও unexpected exception-কে HTTP error response-এ রূপান্তর করে।

- [register_exception_handlers()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/api/exception_handlers.py:12>) — FastAPI app-এ domain ও unexpected exception handlers register করে।
  - Signature: `register_exception_handlers(app: FastAPI) -> None`

- [register_exception_handlers.domain_error_handler()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/api/exception_handlers.py:15>) — Application domain error থেকে তার HTTP status/details অনুযায়ী response বানায়।
  - Signature: `async domain_error_handler(request: Request, exc: BanglaFactGuardError) -> JSONResponse`

- [register_exception_handlers.unhandled_error_handler()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/api/exception_handlers.py:38>) — Unexpected exception log করে generic server-error response দেয়।
  - Signature: `async unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse`

### backend/app/api/middleware.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/api/middleware.py>) · 29 lines

প্রতিটি request-এর correlation ID এবং processing time যোগ করে।

**Class [CorrelationIDMiddleware](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/api/middleware.py:11>)** · inherits `BaseHTTPMiddleware`

- [CorrelationIDMiddleware.dispatch()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/api/middleware.py:13>) — Request-এর correlation ID attach করে।
  - Signature: `async dispatch(self, request: Request, call_next) -> Response`

**Class [ProcessTimeMiddleware](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/api/middleware.py:22>)** · inherits `BaseHTTPMiddleware`

- [ProcessTimeMiddleware.dispatch()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/api/middleware.py:24>) — Request processing duration মেপে response header-এ যোগ করে।
  - Signature: `async dispatch(self, request: Request, call_next) -> Response`

### backend/app/api/v1/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/api/v1/__init__.py>) · 0 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/api/v1/router.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/api/v1/router.py>) · 31 lines

একটি /api/v1 APIRouter-এ সব feature router যুক্ত করে; এখানে route aggregation, business logic নয়।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/core/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/__init__.py>) · 0 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/core/config.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py>) · 575 lines

Pydantic settings: database, Redis, model, search, thresholds, auth, email, Gemini, storage ও worker configuration। get_settings() cached configuration object দেয়; এখানে default মান, live .env values নয়।

**Class [DatabaseSettings](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:15>)** · inherits `BaseSettings`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `host` | `str` | Field(default='localhost', description='PostgreSQL host') |
| `port` | `int` | Field(default=5432, description='PostgreSQL port') |
| `name` | `str` | Field(default='bangla_fact_guard', description='Database name') |
| `user` | `str` | Field(default='postgres', description='Database user') |
| `password` | `str` | Field(default='postgres', description='Database password') |
| `pool_size` | `int` | Field(default=10, description='SQLAlchemy connection pool size') |
| `max_overflow` | `int` | Field(default=20, description='SQLAlchemy max overflow connections') |
| `pool_timeout` | `int` | Field(default=30, description='Connection pool checkout timeout (s)') |
| `echo_sql` | `bool` | Field(default=False, description='Log all SQL statements (dev only)') |

- [DatabaseSettings.async_url()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:36>) — Configured connection parameters দিয়ে উপযুক্ত connection URL বানায়।
  - Signature: `async_url(self) -> str`

- [DatabaseSettings.sync_url()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:43>) — Configured connection parameters দিয়ে উপযুক্ত connection URL বানায়।
  - Signature: `sync_url(self) -> str`

**Class [RedisSettings](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:50>)** · inherits `BaseSettings`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `host` | `str` | Field(default='localhost') |
| `port` | `int` | Field(default=6379) |
| `db` | `int` | Field(default=0) |
| `password` | `str \| None` | Field(default=None) |
| `max_connections` | `int` | Field(default=50) |
| `ttl_claim_result` | `int` | Field(default=86400, description='24 h — Redis pointer to the submission holding a complete result') |
| `ttl_not_found_result` | `int` | Field(default=3600, description='1 h — freshness of a Source NOT_FOUND result. Shorter than ttl_claim_result because an outlet can publish (or index) the story after the first check. Enforced in Redis AND in the database fallback.') |
| `ttl_search_result` | `int` | Field(default=21600, description='6 h — raw search URL lists') |

- [RedisSettings.url()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:77>) — Configured connection parameters দিয়ে উপযুক্ত connection URL বানায়।
  - Signature: `url(self) -> str`

**Class [MLSettings](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:82>)** · inherits `BaseSettings`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `embedding_model_name` | `str` | Field(default='sentence-transformers/LaBSE', description="Sentence-embedding model (similarity, ranking, body scores). The legacy value 'paraphrase-multilingual-mpnet-base-v2' is read as LaBSE, which always ran; see app/features/nlp/model_identity.py.") |
| `embedding_batch_size` | `int` | Field(default=32) |
| `embedding_max_seq_length` | `int` | Field(default=512) |
| `embedding_thread_workers` | `int` | Field(default=4, description='Thread pool workers for embedding encoding') |
| `nli_model_name` | `str` | Field(default='MoritzLaurer/mDeBERTa-v3-base-mnli-xnli', description='HuggingFace model name for NLI-based contradiction detection. Must be a genuinely multilingual NLI model — cross-encoder/nli-deberta-v3-* is English-only (MNLI/SNLI/FEVER fine-tuned on an English-only DeBERTa-v3 vocabulary) and fragments Bangla input into near-single-character tokens, making its scores meaningless for Bangla claims. See docs/06-ai-engineering-design.md S09 for the tokenization evidence.') |
| `nli_thread_workers` | `int` | Field(default=2, description='Thread pool workers for NLI prediction') |
| `ner_model_name` | `str` | Field(default='arafatfahim/BanglaTag', description='BanglaBERT (csebuetnlp/banglabert) fine-tuned for NER. Use a trained token-classification checkpoint with PER/LOC/ORG labels, not the base ELECTRA pretraining model.') |
| `ner_thread_workers` | `int` | Field(default=2, description='Thread pool workers for NER extraction') |
| `max_ranked_articles` | `int` | Field(default=5, description='Maximum number of ranked evidence articles to keep') |
| `min_rank_score` | `float` | Field(default=0.05, description='Minimum composite rank score required to keep an article') |
| `load_models_on_startup` | `bool` | Field(default=True, description='Whether to load ML models into memory on application startup') |

- [MLSettings.max_text_chars_for_embedding()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:143>) — Embedding input-এর character budget configuration থেকে নির্ধারণ করে।
  - Signature: `max_text_chars_for_embedding(self) -> int`

**Class [MultimodalSettings](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:147>)** · inherits `BaseSettings`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `model_dir` | `str` | Field(default=os.path.join(os.path.expanduser('~'), '.cache', 'bangla_fact_guard', 'multimodal_model'), description='Directory containing img_backbone.pt, text_backbone.pt, classifier.pt, and tokenizer/') |
| `text_model_name` | `str` | Field(default='csebuetnlp/banglabert', description='HuggingFace model ID used as BanglaBERT backbone') |
| `image_model_name` | `str` | Field(default='efficientnet_b4', description='timm model name for the EfficientNet backbone') |
| `max_seq_length` | `int` | Field(default=128, description='Max tokenizer length; must match training max_seq_length') |
| `img_size` | `int` | Field(default=380, description='Image resize target; must match training img_size') |
| `num_classes` | `int` | Field(default=2) |
| `dropout` | `float` | Field(default=0.4) |
| `device` | `str` | Field(default='cpu', description="Compute device for inference: 'cpu' or 'cuda'") |
| `load_on_startup` | `bool` | Field(default=True, description='Load model weights during FastAPI lifespan startup') |
| `inference_thread_workers` | `int` | Field(default=2, description='ThreadPoolExecutor workers for CPU-bound inference calls') |
| `model_version` | `str` | Field(default='banglabert_efficientnetb4_v1', description='Version tag stored with each prediction for traceability') |
| `text_sim_threshold` | `float` | Field(default=0.92, description='Min BanglaBERT [CLS] cosine similarity to consider texts identical') |
| `image_sim_threshold` | `float` | Field(default=0.85, description='Min EfficientNet feature cosine similarity to consider images identical') |
| `combined_sim_threshold` | `float` | Field(default=0.9, description='Min combined-embedding cosine similarity (primary pre-filter)') |
| `dedup_candidate_limit` | `int` | Field(default=100, description='Max recent predictions to fetch from DB for similarity search') |

**Class [PhotocardSettings](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:214>)** · inherits `BaseSettings`

দায়িত্ব/contract: Photo-card upload limits. The card is read by Gemini only (see GeminiSettings); there is no OCR engine.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `max_image_bytes` | `int` | Field(default=10 * 1024 * 1024) |

**Class [MinioSettings](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:223>)** · inherits `BaseSettings`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `endpoint` | `str` | Field(default='localhost:9000', description='MinIO server host:port (no http/https prefix)') |
| `access_key` | `str` | Field(default='minioadmin', description='MinIO access key (root user)') |
| `secret_key` | `str` | Field(default='minioadmin', description='MinIO secret key (root password)') |
| `bucket_name` | `str` | Field(default='bangla-fact-guard', description='Bucket where multimodal submission images are stored') |
| `secure` | `bool` | Field(default=False, description='Use HTTPS when connecting to MinIO') |
| `presigned_url_expiry_seconds` | `int` | Field(default=3600, description='Pre-signed URL validity period in seconds (default: 1 hour)') |

**Class [SearchSettings](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:253>)** · inherits `BaseSettings`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `pygooglenews_max_results` | `int` | Field(default=10) |
| `top_k_candidates` | `int` | Field(default=15, description='Maximum number of candidate article URLs to fetch per claim (increased for parallel search)') |
| `min_body_length_chars` | `int` | Field(default=100, description='Minimum extracted body length to consider an article valid') |
| `verified_source_fallback_enabled` | `bool` | Field(default=True, description='Verify claims with no (or an unrecognised/inactive) source against the active verified sources. When false, such claims are rejected as before.') |
| `fallback_domain_group_size` | `int` | Field(default=5, ge=1, le=20, description='Verified-source domains combined into one Google query (site:a OR site:b ...).') |
| `fallback_max_queries` | `int` | Field(default=3, ge=1, le=6, description='Search phrasings used in verified-sources mode (each runs once per domain group).') |

**Class [ClassificationThresholds](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:285>)** · inherits `BaseSettings`

দায়িত্ব/contract: Source-correspondence and search-adequacy thresholds. The Headline Alteration verdict has its own documented constants in `analysis/headline_comparison.py`; body similarity has no thresholds at all (it produces measurements only, never a verdict).

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `corr_headline_sim_alone` | `float` | Field(default=0.85, description='Headline/source-title similarity at/above which the report corresponds without further lexical support (near-identical wording).') |
| `corr_headline_sim_strong` | `float` | Field(default=0.72, description="Headline/title similarity that corresponds strongly when the claim's keywords also appear in the title.") |
| `corr_headline_sim_plausible` | `float` | Field(default=0.55, description='Minimum headline/title similarity for a plausible correspondence (needs lexical support).') |
| `corr_keyword_title_plausible` | `float` | Field(default=0.5, description='Claim-keyword coverage of the source title that counts as lexical support.') |
| `corr_keyword_passage_plausible` | `float` | Field(default=0.6, description='Claim-keyword coverage of the source passages discussing the claim that counts as lexical support.') |
| `corr_keyword_only_title` | `float` | Field(default=0.7, description='Title keyword coverage required when no embedding similarity is available.') |
| `search_min_successful_calls` | `int` | Field(default=2, description='Minimum completed provider calls (success or successful-empty) for a search to count as adequate.') |
| `search_min_success_ratio` | `float` | Field(default=0.5, description='Minimum share of attempted provider calls that must complete for adequacy.') |

**Class [AuthSettings](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:331>)** · inherits `BaseSettings`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `secret_key` | `str` | Field(..., min_length=32, description='HS256 signing key for JWT tokens (env AUTH_SECRET_KEY). Required: the app refuses to start without one rather than signing with a publicly known default.') |
| `algorithm` | `str` | Field(default='HS256', description='JWT signing algorithm') |
| `access_token_ttl_seconds` | `int` | Field(default=900, description='Access token time-to-live in seconds') |
| `refresh_token_ttl_seconds` | `int` | Field(default=31536000, description='Refresh token time-to-live in seconds (default 365 days). Every refresh issues a new token with a fresh lifetime, so a session lasts until the user logs out (or is inactive for this long).') |
| `refresh_rotation_grace_seconds` | `int` | Field(default=120, ge=0, description='How long a just-rotated refresh token stays usable. Covers a refresh response that never reached the client (network drop, sleeping tab) so the user is not logged out. Logout still revokes immediately.') |
| `bcrypt_rounds` | `int` | Field(default=12, description='bcrypt work factor (cost). Higher = slower but more secure.') |

**Class [EmailSettings](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:373>)** · inherits `BaseSettings`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `smtp_host` | `str` | Field(default='', description='SMTP server host. Empty disables real email sending — OTPs are logged to the console instead (local/dev fallback).') |
| `smtp_port` | `int` | Field(default=587) |
| `smtp_user` | `str` | Field(default='') |
| `smtp_password` | `str` | Field(default='') |
| `use_tls` | `bool` | Field(default=True) |
| `from_address` | `str` | Field(default='no-reply@banglafactguard.local') |
| `from_name` | `str` | Field(default='BanglaFactGuard') |
| `website_url` | `str` | Field(default='http://localhost:4200', pattern='^https?://[^\\s]+$') |
| `otp_length` | `int` | Field(default=6) |
| `otp_ttl_minutes` | `int` | Field(default=10) |

- [EmailSettings.is_configured()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:394>) — এই service চালানোর প্রয়োজনীয় configuration দেওয়া আছে কি না জানায়।
  - Signature: `is_configured(self) -> bool`

**Class [GeminiSettings](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:398>)** · inherits `BaseSettings`

দায়িত্ব/contract: Gemini is the ONLY photo-card extractor: it reads the headline, the claimed news outlet (matched against the active verified sources) and the published date from the ORIGINAL image. There is no OCR fallback. Attempts are made in batches: ``attempts_per_batch`` requests, then a ``batch_pause_seconds`` pause, up to ``batches`` batches. With the defaults that is at most 3 x 3 = 9 requests in total, the first request included; the first success stops the loop.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `api_key` | `str` | Field(default='', description='Gemini API key for photo-card extraction. Without any key photo cards cannot be processed.') |
| `api_keys` | `list[str]` | Field(default_factory=lambda: _numbered_gemini_keys(), description='Further keys, rotated when one reaches its limit. Read from GEMINI_API_KEY1, GEMINI_API_KEY2, ... (any number, in numeric order).') |
| `model_name` | `str` | Field(default='gemini-2.0-flash', description='Gemini model id used for photo-card image extraction only.') |
| `base_url` | `str` | Field(default='https://generativelanguage.googleapis.com/v1beta', description='Gemini REST API base URL.') |
| `timeout_seconds` | `int` | Field(default=20, description='HTTP timeout for ONE Gemini extraction attempt.') |
| `attempts_per_batch` | `int` | Field(default=3, ge=1, le=3, description='Requests per batch (never more than 3).') |
| `batches` | `int` | Field(default=3, ge=1, le=3, description='Batches per card (never more than 3): at most 9 requests in total.') |
| `batch_pause_seconds` | `float` | Field(default=10.0, ge=0.0, description='Pause after a batch in which every attempt failed, before the next batch.') |
| `retry_base_delay_seconds` | `float` | Field(default=1.0, ge=0.0, description='Exponential backoff base between attempts inside one batch (1s, 2s).') |

- [GeminiSettings.max_requests()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:458>) — Gemini per-batch attempt ও batch count থেকে মোট request budget দেয়।
  - Signature: `max_requests(self) -> int`

- [GeminiSettings.all_api_keys()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:462>) — Code-এর দায়িত্ব-বর্ণনা: GEMINI_API_KEY first, then the numbered keys; blanks, placeholders and duplicates removed. This is the rotation order.
  - Signature: `all_api_keys(self) -> list[str]`

- [GeminiSettings.is_configured()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:473>) — এই service চালানোর প্রয়োজনীয় configuration দেওয়া আছে কি না জানায়।
  - Signature: `is_configured(self) -> bool`

- [_numbered_gemini_keys()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:480>) — Numbered Gemini environment keys সংগ্রহ করে rotation configuration বানায়।
  - Signature: `_numbered_gemini_keys() -> list[str]`

**Class [JobSettings](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:489>)** · inherits `BaseSettings`

দায়িত্ব/contract: Background verification worker (see app/features/verification/jobs.py).

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `enabled` | `bool` | Field(default=True, description='Run the in-process job worker.') |
| `max_concurrent` | `int` | Field(default=2, ge=1, description='Bound on simultaneously running verification jobs (the pipeline has CPU-bound stretches that share the API event loop).') |
| `photocard_max_concurrent` | `int` | Field(default=4, ge=1, description='Separate bound for photo-card jobs. They run in their own lane so a card waiting out Gemini retries never delays text or text & image jobs.') |
| `poll_interval_seconds` | `float` | Field(default=5.0, gt=0) |
| `stale_after_seconds` | `float` | Field(default=120.0, gt=0, description='A RUNNING job with no heartbeat for this long is reclaimed (restart recovery latency).') |
| `heartbeat_interval_seconds` | `float` | Field(default=30.0, gt=0) |

**Class [AppSettings](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:517>)** · inherits `BaseSettings`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `app_name` | `str` | Field(default='BanglaFactGuard') |
| `app_version` | `str` | Field(default='0.1.0') |
| `environment` | `Literal['development', 'staging', 'production']` | Field(default='development', description='Deployment environment') |
| `api_v1_prefix` | `str` | Field(default='/api/v1') |
| `cors_origins` | `list[str]` | Field(default=['*'], description='List of origins allowed to make CORS requests') |
| `log_level` | `str` | Field(default='INFO', description='Root log level') |
| `log_format` | `Literal['json', 'console']` | Field(default='json', description="'json' for production, 'console' for local dev") |
| `db` | `DatabaseSettings` | Field(default_factory=DatabaseSettings) |
| `redis` | `RedisSettings` | Field(default_factory=RedisSettings) |
| `ml` | `MLSettings` | Field(default_factory=MLSettings) |
| `search` | `SearchSettings` | Field(default_factory=SearchSettings) |
| `thresholds` | `ClassificationThresholds` | Field(default_factory=ClassificationThresholds) |
| `multimodal` | `MultimodalSettings` | Field(default_factory=MultimodalSettings) |
| `photocard` | `PhotocardSettings` | Field(default_factory=PhotocardSettings) |
| `minio` | `MinioSettings` | Field(default_factory=MinioSettings) |
| `auth` | `AuthSettings` | Field(default_factory=AuthSettings) |
| `email` | `EmailSettings` | Field(default_factory=EmailSettings) |
| `gemini` | `GeminiSettings` | Field(default_factory=GeminiSettings) |
| `jobs` | `JobSettings` | Field(default_factory=JobSettings) |

- [AppSettings.classification()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:560>) — Classification threshold settings-এর compatibility access দেয়।
  - Signature: `classification(self) -> ClassificationThresholds`

- [AppSettings._validate_log_level()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:565>) — Configured logging level valid format-এ আছে কি না পরীক্ষা করে।
  - Signature: `_validate_log_level(cls, v: str) -> str`

- [get_settings()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/config.py:574>) — Cached validated application settings ফেরত দেয়।
  - Signature: `get_settings() -> AppSettings`

### backend/app/core/constants.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py>) · 350 lines

Status enums, submission types, pipeline stage IDs/version, source aliases ও shared constants। Historical enum value থাকা মানেই সেই provider/behavior live নয়।

**Enum `SourceStatus`:** CONFIRMED = 'CONFIRMED'; NOT_FOUND = 'NOT_FOUND'; INCOMPLETE = 'INCOMPLETE'

**Enum `ContentStatus`:** MATCHED = 'MATCHED'; ALTERED = 'ALTERED'

**Enum `HeadlineAlterationStatus`:** EXACT_MATCHED = 'EXACT_MATCHED'; MEANING_PRESERVED = 'MEANING_PRESERVED'; ALTERED = 'ALTERED'

**Enum `HeadlineCheckStatus`:** COMPLETED = 'COMPLETED'; SOURCE_NOT_FOUND = 'SOURCE_NOT_FOUND'; SOURCE_CHECK_INCOMPLETE = 'SOURCE_CHECK_INCOMPLETE'; SOURCE_TITLE_MISSING = 'SOURCE_TITLE_MISSING'; MODEL_UNAVAILABLE = 'MODEL_UNAVAILABLE'; UNDETERMINED = 'UNDETERMINED'

**Enum `BodyComparisonStatus`:** COMPUTED = 'COMPUTED'; SKIPPED = 'SKIPPED'; UNAVAILABLE = 'UNAVAILABLE'

**Enum `DateStatus`:** MATCHED = 'MATCHED'; MISMATCHED = 'MISMATCHED'; INCOMPLETE = 'INCOMPLETE'

**Enum `OverallVerdict`:** FAKE = 'FAKE'; REAL = 'REAL'; MISLEADING = 'MISLEADING'; ALTERED = 'ALTERED'

**Enum `ExpertVerdict`:** TRUE = 'TRUE'; FALSE = 'FALSE'; PARTIALLY_TRUE = 'PARTIALLY_TRUE'; NOT_FOUND_IN_CLAIMED_SOURCE = 'NOT_FOUND_IN_CLAIMED_SOURCE'

**Enum `SearchProvider`:** INTERNAL_SITE = 'internal_site'; NEWSDATA = 'newsdata'; GOOGLE_CUSTOM_SEARCH = 'google_custom_search'; PY_GOOGLE_NEWS = 'py_google_news'; SEARXNG = 'searxng'; GOOGLE_RSS = 'google_rss'; DDG = 'ddg'; BRAVE = 'brave'

**Enum `QueryType`:** HEADLINE = 'headline'; KEYWORDS = 'keywords'; ENTITIES = 'entities'; DATE_BOUND = 'date_bound'; BODY_SUMMARY = 'body_summary'; SITE_RESTRICTED = 'site_restricted'

**Enum `ExtractionMethod`:** JSON_LD = 'json_ld'; OPENGRAPH = 'opengraph'; SOURCE_SPECIFIC = 'source_specific'; TRAFILATURA = 'trafilatura'; READABILITY = 'readability'; BEAUTIFULSOUP = 'beautifulsoup'

**Enum `SubmissionType`:** MULTIMODAL = 'MULTIMODAL'; SOURCE_BASED = 'SOURCE_BASED'; PHOTO_CARD = 'PHOTO_CARD'

**Enum `ClaimScope`:** HEADLINE_ONLY = 'HEADLINE_ONLY'; HEADLINE_WITH_BODY = 'HEADLINE_WITH_BODY'

**Enum `SubmissionStatus`:** PENDING = 'PENDING'; PROCESSING = 'PROCESSING'; EXPERT_REVIEW = 'EXPERT_REVIEW'; FINALIZED = 'FINALIZED'; FAILED = 'FAILED'; ESCALATED = 'ESCALATED'

**Enum `MultimodalPredictionLabel`:** FAKE = 'FAKE'; NON_FAKE = 'NON_FAKE'

**Enum `MetricState`:** COMPUTED = 'COMPUTED'; NOT_APPLICABLE = 'NOT_APPLICABLE'; EMPTY = 'EMPTY'; UNAVAILABLE = 'UNAVAILABLE'

**Enum `SearchCallOutcome`:** SUCCESS = 'SUCCESS'; SUCCESS_EMPTY = 'SUCCESS_EMPTY'; FAILED = 'FAILED'; SKIPPED = 'SKIPPED'; CACHED = 'CACHED'

**Enum `JobPhase`:** QUEUED = 'QUEUED'; EXTRACTING = 'EXTRACTING'; VERIFYING = 'VERIFYING'; DONE = 'DONE'; FAILED = 'FAILED'

**Enum `PipelineStageID`:** S01_NORMALIZER = 's01_normalizer'; S02_CACHE_LOOKUP = 's02_cache_lookup'; S03_QUERY_GENERATOR = 's03_query_generator'; S04_SOURCE_SEARCH = 's04_source_search'; S05_EVIDENCE_RETRIEVAL = 's05_evidence_retrieval'; S06_ARTICLE_EXTRACTOR = 's06_article_extractor'; S07_EVIDENCE_RANKER = 's07_evidence_ranker'; S08_SOURCE_CORRESPONDENCE = 's08_source_correspondence'; S09_HEADLINE_ALTERATION = 's09_headline_alteration'; S10_BODY_SIMILARITY = 's10_body_similarity'; S11_DATE_VERIFICATION = 's11_date_verification'; S12_RESULT_ASSEMBLY = 's12_result_assembly'; S13_RESULT_PERSISTENCE = 's13_result_persistence'

**Class [SourceStatus](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:6>)** · inherits `str, Enum`

দায়িত্ব/contract: Does the claimed source actually carry this story at all? Checked first, independently of content or date: a story the source never published is NOT_FOUND regardless of what the claim says, and a story it did publish is CONFIRMED regardless of how the claim words it. INCOMPLETE is distinct from NOT_FOUND: NOT_FOUND means an adequate search actually ran and came up empty; INCOMPLETE means the search or retrieval itself failed (every provider errored, every fetch failed) and no conclusion could be reached either way. A failed check must never be reported as a confident negative — see s08_source_correspondence.py.

**Class [ContentStatus](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:25>)** · inherits `str, Enum`

দায়িত্ব/contract: Headline Alteration verdict — the claim headline compared with the selected source article's TITLE only (never its body). Only two verdicts exist. MATCHED needs positive evidence (an exact match, or a semantic equivalence established by the comparator); ALTERED needs a material difference (names, numbers, dates, negation, attribution, subject-object roles or the main point). When neither can be established there is NO verdict (NULL) and `HeadlineCheckStatus` says why — a missing verdict is never written as MATCHED, ALTERED or a third "incomplete" verdict.

**Class [HeadlineAlterationStatus](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:42>)** · inherits `str, Enum`

দায়িত্ব/contract: Display-level Headline Alteration status, derived from the stored verdict (`ContentStatus`) without re-running any comparison. EXACT_MATCHED verdict MATCHED and the claim headline equals the source title under `exact_match_key` (NFC, zero-width characters removed, whitespace collapsed, one trailing ।.!? removed — nothing else). MEANING_PRESERVED verdict MATCHED by any other basis (identical word sequence modulo punctuation, or established semantic equivalence). Semantic similarity is never an exact match. Also used for an old MATCHED row whose exactness cannot be proven from stored text. ALTERED verdict ALTERED — unchanged existing determination.

**Class [HeadlineCheckStatus](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:63>)** · inherits `str, Enum`

দায়িত্ব/contract: Processing/availability status of the Headline Alteration check — separate from the verdict itself (`ContentStatus`). COMPLETED a verdict (MATCHED / ALTERED) was reached. SOURCE_NOT_FOUND an adequate search found no corresponding report. SOURCE_CHECK_INCOMPLETE the search/retrieval itself failed or was inadequate — never presented as SOURCE_NOT_FOUND. SOURCE_TITLE_MISSING a source report was found but has no title. MODEL_UNAVAILABLE the semantic model needed for a non-exact comparison was unavailable. UNDETERMINED the comparison ran but established neither equivalence nor a material difference.

**Class [BodyComparisonStatus](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:86>)** · inherits `str, Enum`

দায়িত্ব/contract: Whether the claim-body vs source-body similarity scores were computed. COMPUTED at least one of the four metrics produced a value. SKIPPED the claim has no body (headline-only text or a photo card). UNAVAILABLE the claim has a body but there is nothing to compare it with (no corresponding source, no extracted source body) or every metric failed. Never reported as a score of 0.

**Class [DateStatus](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:101>)** · inherits `str, Enum`

দায়িত্ব/contract: Does the claimed publication date match the source's actual date? Only meaningful when source_status is CONFIRMED. A mismatch here is informational, not a verdict on the content — a claim can be MISMATCHED on date while its content is still MATCHED (e.g. a screenshot circulated years after original publication). INCOMPLETE means the source's actual publication date could not be determined (missing or ambiguous datePublished) — this is not the same as MISMATCHED, and must never be reported as one.

**Class [OverallVerdict](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:118>)** · inherits `str, Enum`

দায়িত্ব/contract: The headline editorial verdict experts vote on for EVERY submission type (source-based, photo card, and multimodal alike) — distinct from, and voted on independently of, the (Source, Content, Date) structured vote that additionally exists for source-based/photo-card claims. An expert may, for example, judge Source=CONFIRMED/Content=ALTERED but still cast ALTERED here rather than mechanically deriving it — this is the expert's own editorial call, not a projection of the other fields.

**Class [ExpertVerdict](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:135>)** · inherits `str, Enum`

দায়িত্ব/contract: A human expert's own single-category judgment call on a claim. Deliberately separate from the AI pipeline's (SourceStatus, ContentStatus, DateStatus) triple: expert review is a credibility-weighted consensus vote that predates and is independent of this task's 3-dimensional verdict model, and collapsing three experts' votes across three independent axes into one weighted consensus is a distinct, unspecified design problem. This enum keeps that existing voting/credibility-scoring subsystem working unchanged. It is never returned as "the verdict" from the verification pipeline itself — see VerificationResponse.

**Class [SearchProvider](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:154>)** · inherits `str, Enum`

**Class [QueryType](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:167>)** · inherits `str, Enum`

**Class [ExtractionMethod](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:177>)** · inherits `str, Enum`

**Class [SubmissionType](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:187>)** · inherits `str, Enum`

**Class [ClaimScope](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:194>)** · inherits `str, Enum`

দায়িত্ব/contract: What the pipeline is allowed to use as "the claim" when comparing against source evidence. PHOTO_CARD submissions are always HEADLINE_ONLY: the business rule is that a photo card is verified against its extracted headline alone — no body/caption text is checked, and nothing is synthesised to stand in for one. SOURCE_BASED text claims are HEADLINE_WITH_BODY whenever the user supplied body text, HEADLINE_ONLY otherwise. This is part of claim identity: it is folded into the content hash (`hashing.compute_claim_hash`) so a HEADLINE_ONLY run and a HEADLINE_WITH_BODY run of the same headline+source never collide in the cache and silently serve each other a score computed over different input.

**Class [SubmissionStatus](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:213>)** · inherits `str, Enum`

দায়িত্ব/contract: SUBMITTED/AI_PROCESSING/AI_PRELIMINARY/UNDER_REVIEW/EXPERT_VERIFIED in the SRS state-machine map to PENDING/PROCESSING/EXPERT_REVIEW/FINALIZED here — same lifecycle, pre-existing names kept rather than renamed across the whole codebase. ESCALATED is the one genuinely new terminal state: a claim that hit its configured review window/vote cap without reaching consensus, now awaiting an admin's manual resolution instead of further expert votes.

**Class [MultimodalPredictionLabel](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:231>)** · inherits `str, Enum`

**Class [MetricState](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:237>)** · inherits `str, Enum`

দায়িত্ব/contract: Why a score is (or is not) a number. COMPUTED — a real measurement; the value may legitimately be 0.0. NOT_APPLICABLE — the metric has no meaning for this claim (photo-card body similarity, entity coverage with no claim entities). EMPTY — the claim side produced nothing to measure (keyword extraction returned no applicable units). UNAVAILABLE — the utility/model/evidence needed was missing or failed.

**Class [SearchCallOutcome](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:254>)** · inherits `str, Enum`

দায়িত্ব/contract: Per provider-call accounting for S04 — the only honest basis for deciding whether a search was adequate.

**Class [JobPhase](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:265>)** · inherits `str, Enum`

দায়িত্ব/contract: Fine-grained progress inside the public PENDING/PROCESSING lifecycle.

**Class [PipelineStageID](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/constants.py:281>)** · inherits `str, Enum`

### backend/app/core/exceptions.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py>) · 260 lines

Common BanglaFactGuardError ও feature-specific errors; প্রতিটির error code/message/details/HTTP mapping।

**Class [BanglaFactGuardError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:6>)** · inherits `Exception`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `http_status_code` | `int` | 500 |

- [BanglaFactGuardError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:10>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, message: str='An unexpected error occurred.', details: dict[str, Any] \| None=None) -> None`

- [BanglaFactGuardError.__repr__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:19>) — Debugging-এর জন্য object-এর সংক্ষিপ্ত text representation দেয়।
  - Signature: `__repr__(self) -> str`

**Class [DomainValidationError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:23>)** · inherits `BanglaFactGuardError`

**Class [SourceNotFoundError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:28>)** · inherits `BanglaFactGuardError`

- [SourceNotFoundError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:32>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, claimed_source: str) -> None`

**Class [ImageStorageUnavailableError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:40>)** · inherits `BanglaFactGuardError`

দায়িত্ব/contract: The card image could not be stored. A photo-card submission is only acknowledged once its image bytes are durably stored (the background job reads them back), so this is a 503 rather than an accepted submission.

- [ImageStorageUnavailableError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:47>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self) -> None`

**Class [PermanentJobError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:53>)** · inherits `BanglaFactGuardError`

দায়িত্ব/contract: A background job failed in a way retrying cannot fix (unreadable image, unresolvable source, ...). Carries a user-presentable reason that is stored on the submission and shown on its result page.

- [PermanentJobError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:60>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, reason: str, details: dict[str, Any] \| None=None) -> None`

**Class [PipelineError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:65>)** · inherits `BanglaFactGuardError`

**Class [StageError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:70>)** · inherits `PipelineError`

- [StageError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:72>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, stage_id: str, message: str, details: dict[str, Any] \| None=None) -> None`

**Class [NormalizationError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:82>)** · inherits `StageError`

**Class [QueryGenerationError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:86>)** · inherits `StageError`

**Class [ClassificationError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:90>)** · inherits `StageError`

**Class [PersistenceError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:94>)** · inherits `StageError`

**Class [RepositoryError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:98>)** · inherits `BanglaFactGuardError`

**Class [RecordNotFoundError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:103>)** · inherits `RepositoryError`

- [RecordNotFoundError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:107>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, model: str, identifier: str) -> None`

**Class [DuplicateRecordError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:116>)** · inherits `RepositoryError`

- [DuplicateRecordError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:120>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, model: str, field: str, value: str) -> None`

**Class [ExternalAPIError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:127>)** · inherits `BanglaFactGuardError`

- [ExternalAPIError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:131>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, provider: str, message: str, status_code: int \| None=None, details: dict[str, Any] \| None=None) -> None`

**Class [PyGoogleNewsError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:146>)** · inherits `ExternalAPIError`

- [PyGoogleNewsError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:148>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, message: str, status_code: int \| None=None) -> None`

**Class [MLModelError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:154>)** · inherits `BanglaFactGuardError`

**Class [ModelNotLoadedError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:159>)** · inherits `MLModelError`

- [ModelNotLoadedError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:161>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, model_name: str) -> None`

**Class [InferenceError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:170>)** · inherits `MLModelError`

- [InferenceError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:172>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, model_name: str, cause: str) -> None`

**Class [AuthError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:180>)** · inherits `BanglaFactGuardError`

**Class [InvalidCredentialsError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:185>)** · inherits `AuthError`

- [InvalidCredentialsError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:187>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self) -> None`

**Class [TokenExpiredError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:194>)** · inherits `AuthError`

- [TokenExpiredError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:196>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self) -> None`

**Class [TokenInvalidError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:200>)** · inherits `AuthError`

- [TokenInvalidError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:202>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self) -> None`

**Class [OtpInvalidError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:206>)** · inherits `AuthError`

- [OtpInvalidError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:208>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self) -> None`

**Class [OtpGenerationError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:212>)** · inherits `BanglaFactGuardError`

- [OtpGenerationError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:216>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self) -> None`

**Class [EmailDeliveryError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:222>)** · inherits `BanglaFactGuardError`

- [EmailDeliveryError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:226>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self) -> None`

**Class [InactiveAccountError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:233>)** · inherits `AuthError`

- [InactiveAccountError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:237>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self) -> None`

**Class [PermissionDeniedError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:241>)** · inherits `BanglaFactGuardError`

- [PermissionDeniedError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:245>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, required_role: str \| None=None) -> None`

**Class [WeakPasswordError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:252>)** · inherits `BanglaFactGuardError`

- [WeakPasswordError.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/exceptions.py:256>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, reason: str) -> None`

### backend/app/core/lifespan.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/lifespan.py>) · 155 lines

Startup-এ shared clients/models/storage/workers তৈরি; shutdown-এ পরিষ্কারভাবে বন্ধ।

- [lifespan()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/lifespan.py:26>) — Startup resources/workers তৈরি এবং shutdown cleanup চালায়।
  - Signature: `async lifespan(app: FastAPI) -> AsyncGenerator[None, None]`

### backend/app/core/logging.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/logging.py>) · 78 lines

structlog configuration ও pipeline logging context binding।

- [setup_logging()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/logging.py:34>) — Log level/format ও structlog processors configure করে।
  - Signature: `setup_logging(settings: AppSettings \| None=None) -> None`

- [bind_pipeline_context()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/core/logging.py:66>) — পরের log entries-তে submission/pipeline পরিচয় যুক্ত করে।
  - Signature: `bind_pipeline_context(claim_id: str, *, stage_id: str \| None=None, normalized_source: str \| None=None) -> None`

### backend/app/db/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/__init__.py>) · 0 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/db/engine.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/engine.py>) · 67 lines

Async SQLAlchemy engine, session factory, request session commit/rollback এবং pool close।

- [get_engine()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/engine.py:43>) — Shared SQLAlchemy async engine ফেরত দেয়।
  - Signature: `get_engine() -> AsyncEngine`

- [get_async_session()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/engine.py:47>) — Request database session দেয়; সফল হলে commit, exception হলে rollback; shared wrapper-এ মূল provider-এ delegate করে।
  - Signature: `async get_async_session() -> AsyncGenerator[AsyncSession, None]`

- [close_engine()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/engine.py:65>) — Database engine-এর connection pool dispose করে।
  - Signature: `async close_engine() -> None`

### backend/app/features/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/__init__.py>) · 1 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/admin/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/__init__.py>) · 1 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/admin/dashboard.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/dashboard.py>) · 162 lines

Admin home-এর pending/escalated claims, recent decisions/activity ও expert activity aggregations।

- [_review_count()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/dashboard.py:25>) — সংশ্লিষ্ট submission-এর review count expression তৈরি করে।
  - Signature: `_review_count(admin: bool)`

- [_count()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/dashboard.py:35>) — সংশ্লিষ্ট records-এর total count বের করে।
  - Signature: `async _count(session: AsyncSession, *conditions) -> int`

- [build_admin_dashboard()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/dashboard.py:39>) — Admin action queue, recent activity/decisions ও expert overview assemble করে।
  - Signature: `async build_admin_dashboard(session: AsyncSession) -> AdminDashboardResponse`

- [build_admin_dashboard.claims()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/dashboard.py:59>) — Admin dashboard-এর নির্দিষ্ট filter-যুক্ত claim/expert collection তৈরি করে।
  - Signature: `async claims(stmt) -> list[DashboardClaim]`

- [build_admin_dashboard.experts_with()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/dashboard.py:102>) — Admin dashboard-এর নির্দিষ্ট filter-যুক্ত claim/expert collection তৈরি করে।
  - Signature: `async experts_with(active: bool) -> int`

### backend/app/features/admin/router.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py>) · 248 lines

Feature `admin`। এই feature-এর HTTP paths, request/response schema, dependencies ও permission guard define করে; handler সংশ্লিষ্ট service/repository-তে কাজ পাঠায়।

- [_get_service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:35>) — FastAPI dependency হিসেবে এই feature-এর service প্রয়োজনীয় repository/shared resources দিয়ে তৈরি করে।
  - Signature: `_get_service(session: AsyncSession=Depends(get_async_session)) -> AdminService`

- [create_expert()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:51>) — Admin-authorized expert account ও expert profile তৈরি করে।
  - Signature: `async create_expert(body: CreateExpertRequest, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service)) -> ExpertResponse`

- [list_experts()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:64>) — Expert account list অথবা নির্দিষ্ট expert-এর detail আনে।
  - Signature: `async list_experts(limit: int=Query(default=50, ge=1, le=200), offset: int=Query(default=0, ge=0), q: str \| None=Query(default=None, max_length=200, description='Search name, email or expertise'), _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service)) -> list[ExpertResponse]`

- [get_expert()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:79>) — Expert account list অথবা নির্দিষ্ট expert-এর detail আনে।
  - Signature: `async get_expert(expert_id: uuid.UUID, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service)) -> ExpertResponse`

- [update_expert()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:92>) — Expert-এর allowed account/profile fields update করে।
  - Signature: `async update_expert(expert_id: uuid.UUID, body: UpdateExpertRequest, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service)) -> ExpertResponse`

- [reset_expert_password()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:105>) — Admin-authorized expert password reset করে।
  - Signature: `async reset_expert_password(expert_id: uuid.UUID, body: ResetExpertPasswordRequest, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service)) -> dict`

- [deactivate_expert()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:119>) — Expert account-এর active status বদলায়।
  - Signature: `async deactivate_expert(expert_id: uuid.UUID, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service)) -> ExpertResponse`

- [activate_expert()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:132>) — Expert account-এর active status বদলায়।
  - Signature: `async activate_expert(expert_id: uuid.UUID, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service)) -> ExpertResponse`

- [get_platform_stats()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:145>) — Platform submissions/reviews/experts ও processing statistics aggregate করে।
  - Signature: `async get_platform_stats(_: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service)) -> AdminStatsResponse`

- [get_dashboard()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:157>) — Admin action queue, recent activity/decisions ও expert overview assemble করে।
  - Signature: `async get_dashboard(_: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service)) -> AdminDashboardResponse`

- [list_credibility_tiers()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:174>) — Configured credibility weight tiers query করে।
  - Signature: `async list_credibility_tiers(_: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service)) -> list[CredibilityWeightTierResponse]`

- [create_credibility_tier()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:187>) — Admin-এর credibility tier create/update/delete operation চালায়।
  - Signature: `async create_credibility_tier(body: CredibilityWeightTierRequest, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service)) -> CredibilityWeightTierResponse`

- [update_credibility_tier()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:200>) — Admin-এর credibility tier create/update/delete operation চালায়।
  - Signature: `async update_credibility_tier(tier_id: uuid.UUID, body: CredibilityWeightTierUpdateRequest, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service)) -> CredibilityWeightTierResponse`

- [delete_credibility_tier()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:214>) — Admin-এর credibility tier create/update/delete operation চালায়।
  - Signature: `async delete_credibility_tier(tier_id: uuid.UUID, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service)) -> None`

- [get_voting_config()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:231>) — Current database-backed expert voting configuration ফেরত দেয়।
  - Signature: `async get_voting_config(_: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service)) -> VotingConfigResponse`

- [update_voting_config()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/router.py:243>) — Provided voting thresholds/limits validate করে config update করে।
  - Signature: `async update_voting_config(body: VotingConfigUpdateRequest, _: User=Depends(_ADMIN_ONLY), svc: AdminService=Depends(_get_service)) -> VotingConfigResponse`

### backend/app/features/admin/schemas.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py>) · 202 lines

Feature `admin`। এই feature-এর Pydantic request/response structures ও validation define করে; এগুলো database table নয়।

**Class [CreateExpertRequest](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py:9>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `full_name` | `str` | Field(..., max_length=255) |
| `email` | `EmailStr` | required / instance-assigned |
| `password` | `str` | Field(..., min_length=8, max_length=128, description='Initial password set by admin. Expert can change it later.') |
| `expertise_area` | `str \| None` | Field(default=None, max_length=255) |

**Class [UpdateExpertRequest](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py:21>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `full_name` | `str \| None` | Field(default=None, max_length=255) |
| `email` | `EmailStr \| None` | None |
| `expertise_area` | `str \| None` | Field(default=None, max_length=255) |
| `is_active` | `bool \| None` | None |

**Class [ResetExpertPasswordRequest](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py:28>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `new_password` | `str` | Field(..., min_length=8, max_length=128) |

**Class [ExpertResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py:32>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `id` | `str` | required / instance-assigned |
| `full_name` | `str \| None` | required / instance-assigned |
| `email` | `str` | required / instance-assigned |
| `role` | `str` | required / instance-assigned |
| `is_active` | `bool` | required / instance-assigned |
| `expertise_area` | `str \| None` | required / instance-assigned |
| `credibility_score` | `float \| None` | required / instance-assigned |
| `total_votes` | `int` | required / instance-assigned |

**Class [AdminStatsResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py:45>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `total_submissions` | `int` | required / instance-assigned |
| `submissions_last_30_days` | `int` | required / instance-assigned |
| `pending_expert_reviews` | `int` | Field(description='Claims currently open for expert voting.') |
| `escalated_claims` | `int` | Field(default=0, description='Claims awaiting an admin decision.') |
| `total_experts` | `int` | required / instance-assigned |
| `active_experts` | `int` | required / instance-assigned |
| `avg_verification_time_seconds` | `float \| None` | required / instance-assigned |

**Class [CredibilityWeightTierRequest](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py:55>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `label` | `str` | Field(..., max_length=100) |
| `min_accuracy_pct` | `float` | Field(..., ge=0.0, le=100.0) |
| `max_accuracy_pct` | `float` | Field(..., ge=0.0, le=100.0) |
| `weight` | `float` | Field(..., gt=0.0) |
| `is_active` | `bool` | Field(default=True) |

**Class [CredibilityWeightTierItem](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py:63>)** · inherits `CredibilityWeightTierRequest`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `id` | `uuid.UUID \| None` | Field(default=None, description='An existing tier to update; omit to create a new tier.') |

**Class [CredibilityWeightTierSetRequest](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py:69>)** · inherits `BaseModel`

দায়িত্ব/contract: The complete tier configuration. Saved in one transaction: existing tiers listed by id are updated, tiers without an id are created, tiers left out are deleted. Only the final set is validated, so tiers can be split, merged or re-bounded in one save.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `tiers` | `list[CredibilityWeightTierItem]` | Field(..., max_length=50) |

**Class [CredibilityWeightTierUpdateRequest](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py:78>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `label` | `str \| None` | Field(default=None, max_length=100) |
| `min_accuracy_pct` | `float \| None` | Field(default=None, ge=0.0, le=100.0) |
| `max_accuracy_pct` | `float \| None` | Field(default=None, ge=0.0, le=100.0) |
| `weight` | `float \| None` | Field(default=None, gt=0.0) |
| `is_active` | `bool \| None` | None |

**Class [CredibilityWeightTierResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py:86>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `id` | `str` | required / instance-assigned |
| `label` | `str` | required / instance-assigned |
| `min_accuracy_pct` | `float` | required / instance-assigned |
| `max_accuracy_pct` | `float` | required / instance-assigned |
| `weight` | `float` | required / instance-assigned |
| `is_active` | `bool` | required / instance-assigned |

**Class [VotingConfigUpdateRequest](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py:97>)** · inherits `BaseModel`

দায়িত্ব/contract: All fields optional — PUT applies only the ones provided, leaving the rest at their current value (partial update).

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `min_expert_votes` | `int \| None` | Field(default=None, ge=1, le=50, description='M — minimum votes before a claim can finalize') |
| `activation_threshold_votes` | `int \| None` | Field(default=None, ge=0, le=1000, description='N — votes on claims whose final decision is complete that an expert needs before their accuracy-based tier weight applies') |
| `verified_threshold` | `float \| None` | Field(default=None, gt=0, description='T — weighted score the leading verdict must reach') |
| `lead_margin` | `float \| None` | Field(default=None, ge=0, description="Leader's score must exceed the runner-up's by this much") |
| `max_review_votes` | `int \| None` | Field(default=None, ge=1, description='Escalate to admin once this many votes are cast without a final decision (null = not configured). Either limit being exceeded escalates.') |
| `max_review_hours` | `int \| None` | Field(default=None, ge=1, description='Escalate to admin once this many hours have passed since submission without a final decision (null = not configured). Enforced by a background sweep, independent of new votes or page visits.') |

**Class [VotingConfigResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py:140>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `id` | `str` | required / instance-assigned |
| `min_expert_votes` | `int` | required / instance-assigned |
| `activation_threshold_votes` | `int` | required / instance-assigned |
| `verified_threshold` | `float` | required / instance-assigned |
| `lead_margin` | `float` | required / instance-assigned |
| `max_review_votes` | `int \| None` | required / instance-assigned |
| `max_review_hours` | `int \| None` | required / instance-assigned |
| `updated_at` | `datetime` | required / instance-assigned |

**Class [DashboardClaim](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py:154>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `str` | required / instance-assigned |
| `headline` | `str \| None` | required / instance-assigned |
| `submission_type` | `str` | required / instance-assigned |
| `status` | `str` | required / instance-assigned |
| `vote_count` | `int` | 0 |
| `submitted_at` | `datetime` | required / instance-assigned |
| `escalated_at` | `datetime \| None` | None |
| `final_verdict` | `str \| None` | None |
| `decided_by_admin` | `bool` | False |
| `finalized_at` | `datetime \| None` | None |

**Class [DashboardExpert](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py:167>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `id` | `str` | required / instance-assigned |
| `full_name` | `str \| None` | required / instance-assigned |
| `is_active` | `bool` | required / instance-assigned |
| `total_votes` | `int` | required / instance-assigned |
| `last_vote_at` | `datetime \| None` | None |

**Class [DashboardActivity](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py:175>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `kind` | `str` | Field(description='VOTE \| ADMIN_DECISION') |
| `actor` | `str` | required / instance-assigned |
| `submission_id` | `str` | required / instance-assigned |
| `headline` | `str \| None` | required / instance-assigned |
| `overall_vote` | `str` | required / instance-assigned |
| `at` | `datetime` | required / instance-assigned |

**Class [AdminDashboardResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/schemas.py:184>)** · inherits `BaseModel`

দায়িত্ব/contract: Everything the admin home page needs in one call: what needs action (escalated claims, open reviews), what changed recently and who is active.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `escalated_count` | `int` | required / instance-assigned |
| `pending_review_count` | `int` | required / instance-assigned |
| `processing_count` | `int` | required / instance-assigned |
| `failed_last_7_days` | `int` | required / instance-assigned |
| `submissions_last_7_days` | `int` | required / instance-assigned |
| `finalized_last_7_days` | `int` | required / instance-assigned |
| `total_submissions` | `int` | required / instance-assigned |
| `active_experts` | `int` | required / instance-assigned |
| `inactive_experts` | `int` | required / instance-assigned |
| `escalated_claims` | `list[DashboardClaim]` | required / instance-assigned |
| `oldest_pending_reviews` | `list[DashboardClaim]` | required / instance-assigned |
| `recent_submissions` | `list[DashboardClaim]` | required / instance-assigned |
| `recent_decisions` | `list[DashboardClaim]` | required / instance-assigned |
| `experts` | `list[DashboardExpert]` | required / instance-assigned |
| `recent_activity` | `list[DashboardActivity]` | required / instance-assigned |

### backend/app/features/admin/service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py>) · 388 lines

Expert account lifecycle, platform statistics, credibility tiers ও voting config-এর business rules।

**Class [AdminService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:46>)** · inherits `plain class`

- [AdminService.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:48>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, session: AsyncSession, user_repo: UserRepository, profile_repo: ExpertProfileRepository, tier_repo: CredibilityWeightTierRepository, token_repo: RefreshTokenRepository) -> None`

- [AdminService.create_expert()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:62>) — Admin-authorized expert account ও expert profile তৈরি করে।
  - Signature: `async create_expert(self, req: CreateExpertRequest) -> ExpertResponse`

- [AdminService.list_experts()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:87>) — Expert account list অথবা নির্দিষ্ট expert-এর detail আনে।
  - Signature: `async list_experts(self, *, limit: int=50, offset: int=0, q: str \| None=None) -> list[ExpertResponse]`
  - Source contract: Expert accounts, newest first. `q` searches name, email and expertise area (best matches first) before pagination.

- [AdminService.get_expert()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:121>) — Expert account list অথবা নির্দিষ্ট expert-এর detail আনে।
  - Signature: `async get_expert(self, user_id: uuid.UUID) -> ExpertResponse`

- [AdminService.update_expert()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:133>) — Expert-এর allowed account/profile fields update করে।
  - Signature: `async update_expert(self, user_id: uuid.UUID, req: UpdateExpertRequest) -> ExpertResponse`

- [AdminService.reset_expert_password()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:162>) — Admin-authorized expert password reset করে।
  - Signature: `async reset_expert_password(self, user_id: uuid.UUID, req: ResetExpertPasswordRequest) -> dict`

- [AdminService.deactivate_expert()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:176>) — Expert account-এর active status বদলায়।
  - Signature: `async deactivate_expert(self, user_id: uuid.UUID) -> ExpertResponse`

- [AdminService.activate_expert()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:183>) — Expert account-এর active status বদলায়।
  - Signature: `async activate_expert(self, user_id: uuid.UUID) -> ExpertResponse`

- [AdminService.get_platform_stats()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:187>) — Platform submissions/reviews/experts ও processing statistics aggregate করে।
  - Signature: `async get_platform_stats(self) -> AdminStatsResponse`

- [AdminService.get_platform_stats.count()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:190>) — সংশ্লিষ্ট records-এর total count বের করে।
  - Signature: `async count(*conditions) -> int`

- [AdminService.get_dashboard()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:219>) — Admin action queue, recent activity/decisions ও expert overview assemble করে।
  - Signature: `async get_dashboard(self) -> AdminDashboardResponse`

- [AdminService.list_credibility_tiers()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:224>) — Configured credibility weight tiers query করে।
  - Signature: `async list_credibility_tiers(self) -> list[CredibilityWeightTierResponse]`

- [AdminService._validate_tier()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:231>) — Accuracy interval/weight ও existing tiers-এর সঙ্গে compatibility যাচাই করে।
  - Signature: `async _validate_tier(self, *, tier_id: uuid.UUID \| None, min_pct: float, max_pct: float, is_active: bool) -> None`

- [AdminService.create_credibility_tier()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:271>) — Admin-এর credibility tier create/update/delete operation চালায়।
  - Signature: `async create_credibility_tier(self, req: CredibilityWeightTierRequest) -> CredibilityWeightTierResponse`

- [AdminService.update_credibility_tier()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:293>) — Admin-এর credibility tier create/update/delete operation চালায়।
  - Signature: `async update_credibility_tier(self, tier_id: uuid.UUID, req: CredibilityWeightTierUpdateRequest) -> CredibilityWeightTierResponse`

- [AdminService.delete_credibility_tier()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:316>) — Admin-এর credibility tier create/update/delete operation চালায়।
  - Signature: `async delete_credibility_tier(self, tier_id: uuid.UUID) -> None`

- [AdminService.get_voting_config()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:325>) — Current database-backed expert voting configuration ফেরত দেয়।
  - Signature: `async get_voting_config(self) -> VotingConfigResponse`

- [AdminService.update_voting_config()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:329>) — Provided voting thresholds/limits validate করে config update করে।
  - Signature: `async update_voting_config(self, req: VotingConfigUpdateRequest) -> VotingConfigResponse`

- [_voting_config_to_response()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:349>) — Stored model/data-কে নির্দিষ্ট public response schema-তে রূপ দেয়।
  - Signature: `_voting_config_to_response(row: VotingConfig) -> VotingConfigResponse`

- [_tier_to_response()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:362>) — Stored model/data-কে নির্দিষ্ট public response schema-তে রূপ দেয়।
  - Signature: `_tier_to_response(t: CredibilityWeightTier) -> CredibilityWeightTierResponse`

- [_expert_to_response()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/admin/service.py:373>) — Stored model/data-কে নির্দিষ্ট public response schema-তে রূপ দেয়।
  - Signature: `_expert_to_response(user: User, expertise_area: str \| None, credibility_score: float \| None, total_votes: int) -> ExpertResponse`

### backend/app/features/articles/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/articles/__init__.py>) · 1 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/articles/schemas.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/articles/schemas.py>) · 86 lines

Feature `articles`। এই feature-এর Pydantic request/response structures ও validation define করে; এগুলো database table নয়।

**Class [CandidateArticleSchema](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/articles/schemas.py:13>)** · inherits `BaseModel`

দায়িত্ব/contract: A candidate article URL returned by a search provider (Stage 5 output).

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `url` | `str` | Field(..., description='Full URL of the candidate article') |
| `title_snippet` | `str \| None` | Field(default=None) |
| `search_provider` | `SearchProvider` | required / instance-assigned |
| `query_type` | `str` | required / instance-assigned |
| `position` | `int` | Field(default=1, ge=1) |

**Class [RankedArticleSchema](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/articles/schemas.py:23>)** · inherits `BaseModel`

দায়িত্ব/contract: A candidate article that has been extracted (Stage 6) and ranked (Stage 7).

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `url` | `str` | Field(..., description='Source URL of the article') |
| `title` | `str \| None` | Field(default=None) |
| `title_variants` | `list[str]` | Field(default_factory=list, exclude=True, description='Other headline lines printed with the title (e.g. a kicker above it), alone and joined to the title. A claim may quote any of them.') |
| `body` | `str \| None` | Field(default=None) |
| `author` | `str \| None` | Field(default=None) |
| `published_date` | `date \| None` | Field(default=None) |
| `published_at` | `datetime \| None` | Field(default=None, description='datePublished with time, tz-aware (Asia/Dhaka), when the page carried one.') |
| `published_date_source` | `str \| None` | Field(default=None, description='Provenance of published_date (json_ld.datePublished, meta.article:published_time, selector, ...). Never dateModified or a crawl date.') |
| `published_tz_assumed` | `bool` | Field(default=False, description="True when the page's timestamp had no UTC offset and Asia/Dhaka was assumed.") |
| `publisher` | `str \| None` | Field(default=None, description='Canonical name of the verified publisher this article belongs to.') |
| `is_primary` | `bool` | Field(default=False, description='True for the article the headline/date/body comparisons used.') |
| `rank_score` | `float` | Field(default=0.0, ge=0.0, le=1.0, description='Retrieval relevance (is this the report the claim is about?). NOT a content-match score.') |
| `search_provider` | `SearchProvider` | required / instance-assigned |
| `extraction_method` | `ExtractionMethod \| None` | Field(default=None) |

- [RankedArticleSchema.has_body()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/articles/schemas.py:69>) — Applicable nonempty body text আছে কি না জানায়।
  - Signature: `has_body(self) -> bool`

### backend/app/features/auth/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/__init__.py>) · 1 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/auth/models.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/models.py>) · 136 lines

Feature `auth`। SQLAlchemy ORM entities: নিচে exact table, fields ও foreign-key/constraint declarations দেওয়া আছে।

**Class [User](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/models.py:22>)** · inherits `UUIDMixin, TimestampMixin, ReprMixin, Base` · table `users`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `email` | `Mapped[str]` | mapped_column(String(255), unique=True, nullable=False, index=True, comment='User email address — primary login credential') |
| `hashed_password` | `Mapped[str \| None]` | mapped_column(String(255), nullable=True, comment='Bcrypt-hashed password') |
| `full_name` | `Mapped[str \| None]` | mapped_column(String(255), nullable=True) |
| `role` | `Mapped[str]` | mapped_column(String(50), nullable=False, default='user', index=True, comment='RBAC role: user \| expert \| admin') |
| `is_active` | `Mapped[bool]` | mapped_column(Boolean, nullable=False, default=True, index=True) |
| `total_submissions` | `Mapped[int]` | mapped_column(Integer, nullable=False, default=0, comment='DatabaseDescription.pdf Table 4.1 — cached submission counter') |
| `refresh_tokens` | `Mapped[list['RefreshToken']]` | relationship('RefreshToken', back_populates='user', lazy='select', cascade='all, delete-orphan') |

Database constraints/indexes: `__table_args__ = (CheckConstraint("role IN ('user', 'expert', 'admin')", name='ck_users_role_valid'),)`

**Class [RefreshToken](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/models.py:77>)** · inherits `UUIDMixin, Base` · table `refresh_tokens`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `user_id` | `Mapped[uuid.UUID]` | mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True) |
| `token_hash` | `Mapped[str]` | mapped_column(String(64), unique=True, nullable=False, comment='SHA-256 hash of the refresh token') |
| `expires_at` | `Mapped[datetime]` | mapped_column(DateTime(timezone=True), nullable=False) |
| `revoked` | `Mapped[bool]` | mapped_column(Boolean, nullable=False, default=False, index=True) |
| `created_at` | `Mapped[datetime]` | mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False) |
| `user` | `Mapped['User']` | relationship('User', back_populates='refresh_tokens') |

**Class [PasswordResetToken](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/models.py:112>)** · inherits `UUIDMixin, Base` · table `password_reset_tokens`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `user_id` | `Mapped[uuid.UUID]` | mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True) |
| `token_hash` | `Mapped[str]` | mapped_column(String(64), unique=True, nullable=False) |
| `expires_at` | `Mapped[datetime]` | mapped_column(DateTime(timezone=True), nullable=False) |
| `used` | `Mapped[bool]` | mapped_column(Boolean, nullable=False, default=False) |
| `created_at` | `Mapped[datetime]` | mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False) |

### backend/app/features/auth/repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/repository.py>) · 141 lines

Feature `auth`। এই feature-এর database queries ও persistence operations; যেখানে BaseRepository inherit করেছে সেখানে common CRUD inherited।

**Class [UserRepository](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/repository.py:13>)** · inherits `BaseRepository[User]`

- [UserRepository.get_by_email()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/repository.py:17>) — Email দিয়ে user lookup বা email registration existence পরীক্ষা করে।
  - Signature: `async get_by_email(self, email: str) -> User \| None`

- [UserRepository.increment_submission_count()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/repository.py:22>) — Code-এর দায়িত্ব-বর্ণনা: `users.total_submissions` is a cached counter, bumped atomically.
  - Signature: `async increment_submission_count(self, user_id: uuid.UUID) -> None`

- [UserRepository.email_exists()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/repository.py:29>) — Email দিয়ে user lookup বা email registration existence পরীক্ষা করে।
  - Signature: `async email_exists(self, email: str) -> bool`

- [UserRepository.list_by_role()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/repository.py:32>) — নির্দিষ্ট role-এর account list/count query করে।
  - Signature: `async list_by_role(self, role: str, *, limit: int=50, offset: int=0) -> list[User]`

- [UserRepository.count_by_role()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/repository.py:45>) — নির্দিষ্ট role-এর account list/count query করে।
  - Signature: `async count_by_role(self, role: str) -> int`

**Class [RefreshTokenRepository](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/repository.py:53>)** · inherits `BaseRepository[RefreshToken]`

- [RefreshTokenRepository.get_valid_by_raw_token()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/repository.py:57>) — Raw token-এর hash মিলিয়ে non-expired/non-revoked বা unused token record খোঁজে।
  - Signature: `async get_valid_by_raw_token(self, raw_token: str) -> RefreshToken \| None`

- [RefreshTokenRepository.revoke_by_raw_token()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/repository.py:72>) — একটি token অথবা user-এর সব refresh tokens revoke করে।
  - Signature: `async revoke_by_raw_token(self, raw_token: str) -> bool`

- [RefreshTokenRepository.revoke_all_for_user()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/repository.py:91>) — একটি token অথবা user-এর সব refresh tokens revoke করে।
  - Signature: `async revoke_all_for_user(self, user_id: uuid.UUID) -> int`

- [RefreshTokenRepository.delete_expired()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/repository.py:104>) — Expired refresh token records সরায়।
  - Signature: `async delete_expired(self) -> int`

**Class [PasswordResetTokenRepository](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/repository.py:113>)** · inherits `BaseRepository[PasswordResetToken]`

- [PasswordResetTokenRepository.get_valid_by_raw_token()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/repository.py:117>) — Raw token-এর hash মিলিয়ে non-expired/non-revoked বা unused token record খোঁজে।
  - Signature: `async get_valid_by_raw_token(self, raw_token: str) -> PasswordResetToken \| None`

- [PasswordResetTokenRepository.hash_in_use()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/repository.py:132>) — Code-এর দায়িত্ব-বর্ণনা: True if any row (used or unused, expired or not) already has this hash — token_hash carries a DB-level unique constraint, so this must be checked before inserting a newly generated OTP to avoid a collision on the (rare) matching digit string.
  - Signature: `async hash_in_use(self, token_hash: str) -> bool`

### backend/app/features/auth/router.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py>) · 158 lines

Feature `auth`। এই feature-এর HTTP paths, request/response schema, dependencies ও permission guard define করে; handler সংশ্লিষ্ট service/repository-তে কাজ পাঠায়।

- [_get_auth_service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:29>) — FastAPI dependency হিসেবে এই feature-এর service প্রয়োজনীয় repository/shared resources দিয়ে তৈরি করে।
  - Signature: `_get_auth_service(session: AsyncSession=Depends(get_async_session)) -> AuthService`

- [register()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:45>) — Validated account data দিয়ে regular user register করে এবং registration response দেয়।
  - Signature: `async register(body: RegisterRequest, svc: AuthService=Depends(_get_auth_service)) -> UserMeResponse`

- [login()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:70>) — Email/password যাচাই করে access ও refresh token pair দেয়।
  - Signature: `async login(body: LoginRequest, svc: AuthService=Depends(_get_auth_service)) -> TokenResponse`

- [refresh_token()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:83>) — Valid refresh token যাচাই করে token rotation ও নতুন pair তৈরি করে।
  - Signature: `async refresh_token(body: RefreshRequest, svc: AuthService=Depends(_get_auth_service)) -> TokenResponse`

- [logout()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:95>) — প্রদত্ত refresh token revoke করে session logout সম্পন্ন করে।
  - Signature: `async logout(body: RefreshRequest, svc: AuthService=Depends(_get_auth_service)) -> None`

- [me()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:107>) — Current user-এর public account fields দিয়ে profile response বানায়।
  - Signature: `async me(current_user: User=Depends(get_current_user)) -> UserMeResponse`

- [request_password_reset()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:118>) — Account-এর জন্য expiring numeric OTP তৈরি/সংরক্ষণ করে email পাঠানোর ব্যবস্থা করে।
  - Signature: `async request_password_reset(body: PasswordResetRequest, svc: AuthService=Depends(_get_auth_service)) -> dict`

- [confirm_password_reset()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:131>) — Email/OTP যাচাই করে নতুন password hash লেখে এবং reset token ব্যবহৃত হিসেবে চিহ্নিত করে।
  - Signature: `async confirm_password_reset(body: PasswordResetConfirm, svc: AuthService=Depends(_get_auth_service)) -> dict`

- [change_password()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/router.py:148>) — Authenticated user-এর current password যাচাই করে নতুন password স্থাপন করে।
  - Signature: `async change_password(body: ChangePasswordRequest, current_user: User=Depends(get_current_user), svc: AuthService=Depends(_get_auth_service)) -> dict`

### backend/app/features/auth/schemas.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/schemas.py>) · 55 lines

Feature `auth`। এই feature-এর Pydantic request/response structures ও validation define করে; এগুলো database table নয়।

**Class [RegisterRequest](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/schemas.py:6>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `email` | `EmailStr` | required / instance-assigned |
| `password` | `str` | Field(..., min_length=8, max_length=128) |
| `full_name` | `str \| None` | Field(default=None, max_length=255) |

**Class [LoginRequest](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/schemas.py:12>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `email` | `EmailStr` | required / instance-assigned |
| `password` | `str` | required / instance-assigned |

**Class [TokenResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/schemas.py:17>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `access_token` | `str` | required / instance-assigned |
| `refresh_token` | `str` | required / instance-assigned |
| `token_type` | `str` | 'bearer' |
| `expires_in` | `int` | Field(..., description='Access token TTL in seconds') |

**Class [RefreshRequest](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/schemas.py:24>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `refresh_token` | `str` | required / instance-assigned |

**Class [PasswordResetRequest](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/schemas.py:28>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `email` | `EmailStr` | required / instance-assigned |

**Class [PasswordResetConfirm](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/schemas.py:32>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `email` | `EmailStr` | required / instance-assigned |
| `otp` | `str` | Field(..., min_length=4, max_length=10, description='OTP emailed to the user') |
| `new_password` | `str` | Field(..., min_length=8, max_length=128) |

**Class [ChangePasswordRequest](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/schemas.py:38>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `current_password` | `str` | required / instance-assigned |
| `new_password` | `str` | Field(..., min_length=8, max_length=128) |

**Class [UserMeResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/schemas.py:43>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `id` | `str` | required / instance-assigned |
| `email` | `str` | required / instance-assigned |
| `full_name` | `str \| None` | required / instance-assigned |
| `role` | `str` | required / instance-assigned |
| `is_active` | `bool` | required / instance-assigned |
| `access_token` | `str \| None` | None |
| `refresh_token` | `str \| None` | None |
| `token_type` | `str \| None` | None |
| `expires_in` | `int \| None` | None |

### backend/app/features/auth/security.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/security.py>) · 135 lines

bcrypt hashing, JWT access tokens, random refresh token, current-user dependency ও role guards।

- [hash_password()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/security.py:29>) — Password bcrypt hash-এ রূপান্তর করে।
  - Signature: `hash_password(plain: str) -> str`

- [verify_password()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/security.py:37>) — Submitted password stored bcrypt hash-এর সঙ্গে মেলে কি না পরীক্ষা করে।
  - Signature: `verify_password(plain: str, hashed: str) -> bool`

- [create_access_token()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/security.py:45>) — User identity/role ও expiry-সহ signed JWT বানায়।
  - Signature: `create_access_token(user_id: uuid.UUID, role: str) -> tuple[str, int]`

- [create_refresh_token()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/security.py:60>) — Random refresh token, stored hash ও expiry-সংশ্লিষ্ট data তৈরি করে।
  - Signature: `create_refresh_token() -> tuple[str, str, datetime]`

- [decode_access_token()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/security.py:69>) — JWT signature/expiry validate করে claims decode করে।
  - Signature: `decode_access_token(token: str) -> dict[str, Any]`

- [get_current_user()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/security.py:84>) — Bearer token থেকে active database user resolve করে; invalid authentication reject করে।
  - Signature: `async get_current_user(credentials: HTTPAuthorizationCredentials \| None=Depends(_bearer_scheme)) -> User`

- [require_role()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/security.py:109>) — Allowed role set অনুযায়ী authenticated user access অনুমোদন/reject করে।
  - Signature: `require_role(*roles: str)`

- [require_role._check_role()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/security.py:111>) — Allowed role set অনুযায়ী authenticated user access অনুমোদন/reject করে।
  - Signature: `async _check_role(user: User=Depends(get_current_user)) -> User`

- [get_current_user_optional()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/security.py:121>) — Token থাকলে user resolve করে; token না থাকলে guest হিসেবে None দেয়।
  - Signature: `async get_current_user_optional(credentials: HTTPAuthorizationCredentials \| None=Depends(_bearer_scheme)) -> 'User \| None'`

### backend/app/features/auth/service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/service.py>) · 260 lines

Registration/login/refresh/logout এবং email OTP/password-change flow।

- [_generate_otp()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/service.py:39>) — Configured length-এর random numeric password-reset OTP তৈরি করে।
  - Signature: `_generate_otp(length: int) -> str`

- [validate_password_strength()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/service.py:43>) — Password application-এর strength requirements পূরণ করে কি না যাচাই করে।
  - Signature: `validate_password_strength(password: str) -> None`

**Class [AuthService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/service.py:52>)** · inherits `plain class`

- [AuthService.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/service.py:54>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, user_repo: UserRepository, token_repo: RefreshTokenRepository, reset_token_repo: PasswordResetTokenRepository, email_service: EmailService \| None=None) -> None`

- [AuthService.register()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/service.py:66>) — Validated account data দিয়ে regular user register করে এবং registration response দেয়।
  - Signature: `async register(self, email: str, password: str, full_name: str \| None=None, role: str='user') -> tuple[UserMeResponse, TokenResponse]`

- [AuthService.login()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/service.py:96>) — Email/password যাচাই করে access ও refresh token pair দেয়।
  - Signature: `async login(self, email: str, password: str) -> tuple[UserMeResponse, TokenResponse]`

- [AuthService.refresh()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/service.py:115>) — Valid refresh token যাচাই করে token rotation ও নতুন pair তৈরি করে।
  - Signature: `async refresh(self, raw_refresh_token: str) -> TokenResponse`

- [AuthService.logout()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/service.py:142>) — প্রদত্ত refresh token revoke করে session logout সম্পন্ন করে।
  - Signature: `async logout(self, raw_refresh_token: str) -> None`

- [AuthService.request_password_reset()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/service.py:147>) — Account-এর জন্য expiring numeric OTP তৈরি/সংরক্ষণ করে email পাঠানোর ব্যবস্থা করে।
  - Signature: `async request_password_reset(self, email: str) -> str \| None`
  - Source contract: Issue a numeric OTP and email it to the user (req. 1.4: OTP through Email service). Returns the raw OTP only for dev-console logging by the caller — never exposed to the HTTP response.

- [AuthService.confirm_password_reset()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/service.py:194>) — Email/OTP যাচাই করে নতুন password hash লেখে এবং reset token ব্যবহৃত হিসেবে চিহ্নিত করে।
  - Signature: `async confirm_password_reset(self, email: str, otp: str, new_password: str) -> None`

- [AuthService.change_password()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/service.py:218>) — Authenticated user-এর current password যাচাই করে নতুন password স্থাপন করে।
  - Signature: `async change_password(self, user: User, current_password: str, new_password: str) -> None`

- [AuthService._issue_token_pair()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/service.py:232>) — Access token ও persistable refresh token একসঙ্গে তৈরি করে response বানায়।
  - Signature: `async _issue_token_pair(self, user: User) -> TokenResponse`

- [to_me_response()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/auth/service.py:253>) — Current user-এর public account fields দিয়ে profile response বানায়।
  - Signature: `to_me_response(user: User) -> UserMeResponse`

### backend/app/features/cache/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/cache/__init__.py>) · 1 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/cache/cache_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/cache/cache_service.py>) · 97 lines

Redis claim pointer, raw search results ও generic cached value operations; cache health ping।

**Class [CacheService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/cache/cache_service.py:20>)** · inherits `plain class`

- [CacheService.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/cache/cache_service.py:22>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, redis_client: aioredis.Redis) -> None`

- [CacheService.get_claim_result()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/cache/cache_service.py:27>) — Redis থেকে claim pointer/search result/raw cached value আনে।
  - Signature: `async get_claim_result(self, claim_hash: str) -> bytes \| None`

- [CacheService.set_claim_result()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/cache/cache_service.py:34>) — Redis-এ সংশ্লিষ্ট value ও expiry লেখে।
  - Signature: `async set_claim_result(self, claim_hash: str, payload: str) -> None`

- [CacheService.set_claim_pointer()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/cache/cache_service.py:44>) — Code-এর দায়িত্ব-বর্ণনা: Like set_claim_result but with an explicit freshness window (the NOT_FOUND window is shorter than the default claim TTL).
  - Signature: `async set_claim_pointer(self, claim_hash: str, payload: str, *, ttl: int) -> None`

- [CacheService.invalidate_claim()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/cache/cache_service.py:52>) — একটি claim-এর Redis cache entry মুছে দেয়।
  - Signature: `async invalidate_claim(self, claim_hash: str) -> None`

- [CacheService.get_search_result()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/cache/cache_service.py:58>) — Redis থেকে claim pointer/search result/raw cached value আনে।
  - Signature: `async get_search_result(self, provider: str, query_hash: str) -> list[str] \| None`

- [CacheService.set_search_result()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/cache/cache_service.py:69>) — Redis-এ সংশ্লিষ্ট value ও expiry লেখে।
  - Signature: `async set_search_result(self, provider: str, query_hash: str, urls: list[str]) -> None`

- [CacheService.get_raw()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/cache/cache_service.py:81>) — Redis থেকে claim pointer/search result/raw cached value আনে।
  - Signature: `async get_raw(self, key: str) -> bytes \| None`

- [CacheService.set_raw()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/cache/cache_service.py:87>) — Redis-এ সংশ্লিষ্ট value ও expiry লেখে।
  - Signature: `async set_raw(self, key: str, value: str, *, ttl: int=3600) -> None`

- [CacheService.health_check()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/cache/cache_service.py:93>) — Redis ping করে connection usable কি না জানায়।
  - Signature: `async health_check(self) -> bool`

### backend/app/features/dashboard/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/__init__.py>) · 0 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/dashboard/router.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/router.py>) · 107 lines

Feature `dashboard`। এই feature-এর HTTP paths, request/response schema, dependencies ও permission guard define করে; handler সংশ্লিষ্ট service/repository-তে কাজ পাঠায়।

- [_service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/router.py:28>) — FastAPI dependency হিসেবে এই feature-এর service প্রয়োজনীয় repository/shared resources দিয়ে তৈরি করে।
  - Signature: `_service(request: Request, session: AsyncSession=Depends(get_async_session)) -> DashboardService`

- [get_public_stats()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/router.py:41>) — Public platform/submission/method counts query করে response বানায়।
  - Signature: `async get_public_stats(svc: DashboardService=Depends(_service)) -> PublicStatsResponse`

- [get_top_sources()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/router.py:52>) — সবচেয়ে বেশি claimed source-গুলো count অনুযায়ী আনে।
  - Signature: `async get_top_sources(limit: int=Query(default=10, ge=1, le=50), svc: DashboardService=Depends(_service)) -> list[TopSourceItem]`

- [search_explorer()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/router.py:72>) — Filter/search/pagination অনুযায়ী public submissions ও method-specific result data দেখায়।
  - Signature: `async search_explorer(keyword: str \| None=Query(default=None, max_length=255), source_status: SourceStatus \| None=Query(default=None), content_status: ContentStatus \| None=Query(default=None), date_status: DateStatus \| None=Query(default=None), overall_verdict: OverallVerdict \| None=Query(default=None, description='Matches only expert-finalized claims — spans every submission type, unlike source/content/date_status which only apply to SOURCE_BASED/PHOTO_CARD.'), method: SubmissionType \| None=Query(default=None), date_from: date \| None=Query(default=None), date_to: date \| None=Query(default=None), source_id: uuid.UUID \| None=Query(default=None), review_state: Literal['finalized', 'review'] \| None=Query(default=None), limit: int=Query(default=20, ge=1, le=100), offset: int=Query(default=0, ge=0), svc: DashboardService=Depends(_service)) -> ExplorerSearchResponse`

### backend/app/features/dashboard/schemas.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/schemas.py>) · 78 lines

Feature `dashboard`। এই feature-এর Pydantic request/response structures ও validation define করে; এগুলো database table নয়।

**Class [MethodDistribution](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/schemas.py:17>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `source_based` | `int` | required / instance-assigned |
| `multimodal` | `int` | required / instance-assigned |
| `photo_card` | `int` | required / instance-assigned |

**Class [PublicStatsResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/schemas.py:23>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `total_submissions` | `int` | required / instance-assigned |
| `source_confirmed_count` | `int` | required / instance-assigned |
| `source_not_found_count` | `int` | required / instance-assigned |
| `content_matched_count` | `int` | required / instance-assigned |
| `content_altered_count` | `int` | required / instance-assigned |
| `date_matched_count` | `int` | required / instance-assigned |
| `date_mismatched_count` | `int` | required / instance-assigned |
| `pending_count` | `int` | required / instance-assigned |
| `method_distribution` | `MethodDistribution` | required / instance-assigned |
| `avg_verification_time_seconds` | `float \| None` | required / instance-assigned |

**Class [TopSourceItem](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/schemas.py:36>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `source` | `str` | required / instance-assigned |
| `count` | `int` | required / instance-assigned |

**Class [ExplorerItem](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/schemas.py:41>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `prediction` | `str \| None` | None |
| `submission_id` | `str` | required / instance-assigned |
| `headline` | `str \| None` | required / instance-assigned |
| `submission_type` | `SubmissionType` | required / instance-assigned |
| `claimed_source_text` | `str \| None` | required / instance-assigned |
| `overall_verdict` | `OverallVerdict \| None` | Field(default=None, description='The expert-finalized Overall verdict. NULL until expert review finalizes the claim - the automated system never sets it.') |
| `is_finalized` | `bool` | Field(default=False, description='True once expert review has finalized overall_verdict.') |
| `source_status` | `SourceStatus \| None` | None |
| `content_status` | `ContentStatus \| None` | None |
| `headline_status` | `HeadlineAlterationStatus \| None` | None |
| `date_status` | `DateStatus \| None` | None |
| `confidence` | `float \| None` | required / instance-assigned |
| `image_url` | `str \| None` | Field(default=None, description='Thumbnail for MULTIMODAL/PHOTO_CARD submissions') |
| `published_date` | `date \| None` | required / instance-assigned |
| `created_at` | `datetime` | required / instance-assigned |

**Class [ExplorerSearchResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/schemas.py:73>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `items` | `list[ExplorerItem]` | required / instance-assigned |
| `total` | `int` | required / instance-assigned |
| `limit` | `int` | required / instance-assigned |
| `offset` | `int` | required / instance-assigned |
| `archive_summary` | `dict[str, int]` | Field(default_factory=dict) |

### backend/app/features/dashboard/service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/service.py>) · 240 lines

Public counts, most-claimed sources ও searchable Fact Explorer response; তিন method-এর result assemble করে।

**Class [DashboardService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/service.py:40>)** · inherits `plain class`

- [DashboardService.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/service.py:41>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, session: AsyncSession, *, multimodal_storage: MultimodalStorageService \| None=None, photocard_storage: PhotoCardStorageService \| None=None) -> None`

- [DashboardService.public_stats()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/service.py:52>) — Public platform/submission/method counts query করে response বানায়।
  - Signature: `async public_stats(self) -> PublicStatsResponse`

- [DashboardService.top_sources()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/service.py:107>) — সবচেয়ে বেশি claimed source-গুলো count অনুযায়ী আনে।
  - Signature: `async top_sources(self, limit: int) -> list[TopSourceItem]`

- [DashboardService.explorer()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/dashboard/service.py:118>) — Filter/search/pagination অনুযায়ী public submissions ও method-specific result data দেখায়।
  - Signature: `async explorer(self, *, keyword: str \| None, source_status: SourceStatus \| None, content_status: ContentStatus \| None, date_status: DateStatus \| None, overall_verdict: OverallVerdict \| None, method: SubmissionType \| None, date_from: date \| None, date_to: date \| None, source_id: uuid.UUID \| None, review_state: Literal['finalized', 'review'] \| None, limit: int, offset: int) -> ExplorerSearchResponse`

### backend/app/features/expert_review/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/__init__.py>) · 1 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/expert_review/escalation.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/escalation.py>) · 155 lines

সময়সীমা/vote-cap পার হওয়া open claims sweep করে; admin notification ও periodic worker।

- [admin_review_link()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/escalation.py:25>) — Escalated claim-এর admin link/message বানায়।
  - Signature: `admin_review_link(submission_id) -> str`

- [escalation_message()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/escalation.py:29>) — Escalated claim-এর admin link/message বানায়।
  - Signature: `escalation_message(headline: str \| None) -> str`

- [notify_admins_of_escalation()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/escalation.py:34>) — Code-এর দায়িত্ব-বর্ণনা: One notification per active admin, linking to the claim in the admin review queue. `notify_once` keys on (user, type, link), so a retried transaction cannot duplicate it either.
  - Signature: `async notify_admins_of_escalation(session: AsyncSession, submission: Submission) -> int`

- [_service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/escalation.py:54>) — FastAPI dependency হিসেবে এই feature-এর service প্রয়োজনীয় repository/shared resources দিয়ে তৈরি করে।
  - Signature: `_service(session: AsyncSession)`

- [sweep_review_limits()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/escalation.py:77>) — Code-এর দায়িত্ব-বর্ণনা: Re-evaluates open claims that have exceeded a configured limit. Returns how many changed status (finalized or escalated). Caller commits.
  - Signature: `async sweep_review_limits(session: AsyncSession, *, now: datetime \| None=None, limit: int=50) -> int`

**Class [EscalationWorker](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/escalation.py:122>)** · inherits `plain class`

দায়িত্ব/contract: Runs `sweep_review_limits` every SWEEP_INTERVAL_SECONDS.

- [EscalationWorker.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/escalation.py:125>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, session_factory=None, interval_s: float=SWEEP_INTERVAL_SECONDS)`

- [EscalationWorker.start()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/escalation.py:134>) — Background worker-এর asynchronous loop task শুরু করে।
  - Signature: `start(self) -> None`

- [EscalationWorker.stop()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/escalation.py:137>) — Worker/task cancellation ও shutdown অপেক্ষা সম্পন্ন করে।
  - Signature: `async stop(self) -> None`

- [EscalationWorker.run()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/escalation.py:145>) — এই worker-এর recurring processing/poll/sweep loop চালায়।
  - Signature: `async run(self) -> None`

### backend/app/features/expert_review/models.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/models.py>) · 248 lines

Feature `expert_review`। SQLAlchemy ORM entities: নিচে exact table, fields ও foreign-key/constraint declarations দেওয়া আছে।

**Class [ExpertProfile](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/models.py:18>)** · inherits `UUIDMixin, TimestampMixin, ReprMixin, Base` · table `expert_profiles`

দায়িত্ব/contract: Current expert credibility and review statistics.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `user_id` | `Mapped[uuid.UUID]` | mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True, index=True) |
| `area_of_expertise` | `Mapped[str]` | mapped_column(String(255), nullable=False) |
| `credential_notes` | `Mapped[str \| None]` | mapped_column(Text, nullable=True) |
| `credibility_score` | `Mapped[float \| None]` | mapped_column(Float, nullable=True, default=None) |
| `total_votes` | `Mapped[int]` | mapped_column(Integer, nullable=False, default=0) |
| `correct_votes` | `Mapped[int]` | mapped_column(Integer, nullable=False, default=0) |
| `completed_reviews_count` | `Mapped[int]` | mapped_column(Integer, nullable=False, default=0) |
| `is_active` | `Mapped[bool]` | mapped_column(Boolean, nullable=False, default=True) |
| `user` | `Mapped['User']` | relationship('User', primaryjoin='ExpertProfile.user_id == User.id', viewonly=True, lazy='select') |

Database constraints/indexes: `__table_args__ = (CheckConstraint('credibility_score >= 0.0 AND credibility_score <= 1.0', name='ck_expert_profiles_credibility_score_range'),)`

**Class [CredibilityWeightTier](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/models.py:57>)** · inherits `UUIDMixin, TimestampMixin, ReprMixin, Base` · table `credibility_weight_tiers`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `label` | `Mapped[str]` | mapped_column(String(100), nullable=False) |
| `min_accuracy_pct` | `Mapped[float]` | mapped_column(Float, nullable=False) |
| `max_accuracy_pct` | `Mapped[float]` | mapped_column(Float, nullable=False) |
| `weight` | `Mapped[float]` | mapped_column(Float, nullable=False, default=1.0) |
| `is_active` | `Mapped[bool]` | mapped_column(Boolean, nullable=False, default=True) |

**Class [ExpertReview](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/models.py:68>)** · inherits `UUIDMixin, TimestampMixin, ReprMixin, Base` · table `expert_reviews`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `Mapped[uuid.UUID]` | mapped_column(UUID(as_uuid=True), ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False, index=True) |
| `reviewer_id` | `Mapped[uuid.UUID \| None]` | mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True) |
| `ai_overall_verdict` | `Mapped[OverallVerdict \| None]` | mapped_column(Enum(OverallVerdict, name='overall_verdict_enum', create_type=False), nullable=True, comment='Snapshot of the AI-implied Overall verdict at vote time — MULTIMODAL only. Automated checks never produce an Overall verdict for SOURCE_BASED/PHOTO_CARD, so this is NULL for them.') |
| `ai_source_status` | `Mapped[SourceStatus \| None]` | mapped_column(Enum(SourceStatus, name='source_status_enum', create_type=False), nullable=True, comment="Snapshot of the AI's source call at vote time — SOURCE_BASED/PHOTO_CARD only") |
| `ai_content_status` | `Mapped[ContentStatus \| None]` | mapped_column(Enum(ContentStatus, name='content_status_enum', create_type=False), nullable=True) |
| `ai_date_status` | `Mapped[DateStatus \| None]` | mapped_column(Enum(DateStatus, name='date_status_enum', create_type=False), nullable=True) |
| `vote_overall_verdict` | `Mapped[OverallVerdict]` | mapped_column(Enum(OverallVerdict, name='overall_verdict_enum', create_type=False), nullable=False, comment="Expert's own Overall judgment — required for every submission type") |
| `vote_source_status` | `Mapped[SourceStatus \| None]` | mapped_column(Enum(SourceStatus, name='source_status_enum', create_type=False), nullable=True, comment="Expert's own Source judgment — SOURCE_BASED/PHOTO_CARD only") |
| `vote_content_status` | `Mapped[ContentStatus \| None]` | mapped_column(Enum(ContentStatus, name='content_status_enum', create_type=False), nullable=True, comment="Expert's own Content judgment — set only when vote_source_status is CONFIRMED") |
| `vote_date_status` | `Mapped[DateStatus \| None]` | mapped_column(Enum(DateStatus, name='date_status_enum', create_type=False), nullable=True, comment="Expert's own Date judgment — set only when vote_source_status is CONFIRMED") |
| `justification` | `Mapped[str \| None]` | mapped_column(Text, nullable=True) |
| `credibility_weight` | `Mapped[float]` | mapped_column(Float, nullable=False, default=0.5) |
| `applied_weight_tier_id` | `Mapped[uuid.UUID \| None]` | mapped_column(UUID(as_uuid=True), ForeignKey('credibility_weight_tiers.id', ondelete='SET NULL'), nullable=True) |
| `status` | `Mapped[str]` | mapped_column(String(50), nullable=False, default='pending', index=True) |
| `is_admin_decision` | `Mapped[bool]` | mapped_column(Boolean, nullable=False, default=False, server_default='false', comment="True for the administrator's decision on an ESCALATED claim. That overall vote IS the final verdict; earlier expert votes cannot override it.") |
| `submission` | `Mapped['Submission']` | relationship('Submission', primaryjoin='ExpertReview.submission_id == Submission.id', viewonly=True, lazy='select') |
| `reviewer` | `Mapped['User \| None']` | relationship('User', primaryjoin='ExpertReview.reviewer_id == User.id', viewonly=True, lazy='select') |
| `applied_weight_tier` | `Mapped['CredibilityWeightTier \| None']` | relationship('CredibilityWeightTier', primaryjoin='ExpertReview.applied_weight_tier_id == CredibilityWeightTier.id', viewonly=True, lazy='select') |

**Class [VotingConfig](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/models.py:170>)** · inherits `UUIDMixin, TimestampMixin, ReprMixin, Base` · table `voting_config`

দায়িত্ব/contract: Admin-configurable voting parameters — a single-row table (the oldest row is always the one in effect) so none of these are fixed settings in code. Only the reviewers' OVERALL vote (Real/Fake/Misleading/Altered) decides a claim. It finalizes when ALL of these hold for the weighted overall tally: leader's weighted score >= verified_threshold (T) number of votes cast >= min_expert_votes (M) leader's score - runner-up's score >= lead_margin the leader is unique (an exact tie never finalizes) The supplementary source/headline/date assessments are recorded for reference only and never affect finalization or escalation. Escalation: a claim still undecided ESCALATES to admin review as soon as ANY configured limit is exceeded — votes cast >= max_review_votes, OR hours since submission >= max_review_hours. A NULL limit is "not configured" and is never treated as exceeded; with both NULL a claim s… (পূর্ণ docstring source-এ)

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `min_expert_votes` | `Mapped[int]` | mapped_column(Integer, nullable=False, default=3, comment='M — minimum number of expert votes before a claim can finalize') |
| `activation_threshold_votes` | `Mapped[int]` | mapped_column(Integer, nullable=False, default=10, comment="N — an expert's vote counts as weight 1.0 until they have completed this many lifetime votes; their tier weight applies from then on.") |
| `verified_threshold` | `Mapped[float]` | mapped_column(Float, nullable=False, default=5.0, comment='T — the weighted score the leading verdict must reach, per dimension') |
| `lead_margin` | `Mapped[float]` | mapped_column(Float, nullable=False, default=1.0, comment="Leader's weighted score must exceed the runner-up's by at least this") |
| `max_review_votes` | `Mapped[int \| None]` | mapped_column(Integer, nullable=True, comment='Escalate to admin after this many votes without reaching consensus (NULL = no cap)') |
| `max_review_hours` | `Mapped[int \| None]` | mapped_column(Integer, nullable=True, comment='Escalate to admin after this many hours without reaching consensus (NULL = no cap)') |

Database constraints/indexes: `__table_args__ = (CheckConstraint('min_expert_votes >= 1', name='ck_voting_config_min_votes_positive'), CheckConstraint('activation_threshold_votes >= 0', name='ck_voting_config_activation_threshold_nonneg'), CheckConstraint('verified_threshold > 0', name='ck_voting_config_verified_threshold_positive'), CheckConstraint('lead_margin >= 0', name='ck_voting_config_lead_margin_nonneg'))`

### backend/app/features/expert_review/overall_verdict.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/overall_verdict.py>) · 18 lines

Multimodal binary preliminary prediction থেকে corresponding AI overall-label representation; এটি expert finalization নয়।

- [derive_ai_overall_verdict_multimodal()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/overall_verdict.py:8>) — Code-এর দায়িত্ব-বর্ণনা: For MULTIMODAL claims, from the BanglaBERT+EfficientNet binary call — the model can only say FAKE/NON_FAKE, so it never implies MISLEADING or ALTERED; only an expert vote can assign those.
  - Signature: `derive_ai_overall_verdict_multimodal(prediction: MultimodalPredictionLabel \| str) -> OverallVerdict`

### backend/app/features/expert_review/public_votes.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/public_votes.py>) · 96 lines

Finalized claim-এর public votes/justifications; reused structured claim হলে original review resolve।

**Class [PublicVote](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/public_votes.py:20>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `reviewer_name` | `str` | required / instance-assigned |
| `reviewer_role` | `str` | Field(description='Expert \| Admin') |
| `overall_vote` | `OverallVerdict` | required / instance-assigned |
| `justification` | `str \| None` | required / instance-assigned |
| `voted_at` | `datetime` | required / instance-assigned |
| `is_final_decision` | `bool` | Field(default=False, description="True for the administrator's final decision on an escalated claim.") |

**Class [PublicVotingDetails](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/public_votes.py:31>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `uuid.UUID` | required / instance-assigned |
| `final_verdict` | `OverallVerdict` | required / instance-assigned |
| `decided_by` | `str` | Field(description='EXPERT_CONSENSUS \| ADMIN') |
| `finalized_at` | `datetime \| None` | None |
| `votes` | `list[PublicVote]` | required / instance-assigned |

- [_final_verdict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/public_votes.py:39>) — Structured বা multimodal persisted final verdict resolve করে।
  - Signature: `async _final_verdict(session: AsyncSession, origin: Submission)`

- [load_public_voting_details()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/public_votes.py:51>) — Code-এর দায়িত্ব-বর্ণনা: None unless the claim (or, for a reused copy, the original it reads its review from) has a final decision.
  - Signature: `async load_public_voting_details(session: AsyncSession, submission: Submission) -> PublicVotingDetails \| None`

### backend/app/features/expert_review/repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/repository.py>) · 194 lines

Feature `expert_review`। এই feature-এর database queries ও persistence operations; যেখানে BaseRepository inherit করেছে সেখানে common CRUD inherited।

**Class [ExpertProfileRepository](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/repository.py:14>)** · inherits `BaseRepository[ExpertProfile]`

দায়িত্ব/contract: Storage for current expert credibility and review statistics.

- [ExpertProfileRepository.get_by_user_id()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/repository.py:19>) — User ID দিয়ে expert profile record আনে।
  - Signature: `async get_by_user_id(self, user_id: uuid.UUID) -> ExpertProfile \| None`

- [ExpertProfileRepository.get_or_create()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/repository.py:24>) — Record থাকলে আনে; না থাকলে default/new record তৈরি করে।
  - Signature: `async get_or_create(self, user_id: uuid.UUID, *, initial_score: float \| None=None, area_of_expertise: str='General') -> ExpertProfile`

- [ExpertProfileRepository.finalized_vote_counts()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/repository.py:47>) — Code-এর দায়িত্ব-বর্ণনা: (votes, correct) for one expert, counted from the data itself: only votes on claims whose final decision is complete (FINALIZED, by expert consensus or an administrator), and correct when the vote equals that final overall verdict. Votes on claims still in review or escalated do not count yet, and a deleted claim's votes no longer count at all.
  - Signature: `async finalized_vote_counts(self, reviewer_id: uuid.UUID) -> tuple[int, int]`

- [ExpertProfileRepository.refresh_stats()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/repository.py:76>) — Code-এর দায়িত্ব-বর্ণনা: Re-derive a profile's counters from `finalized_vote_counts`. The accuracy score exists only once N (`activation_threshold`) finalized votes are reached.
  - Signature: `async refresh_stats(self, profile: ExpertProfile, activation_threshold: int) -> ExpertProfile`

**Class [CredibilityWeightTierRepository](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/repository.py:90>)** · inherits `BaseRepository[CredibilityWeightTier]`

- [CredibilityWeightTierRepository.get_active_tiers()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/repository.py:94>) — Configured credibility weight tiers query করে।
  - Signature: `async get_active_tiers(self) -> list[CredibilityWeightTier]`

- [CredibilityWeightTierRepository.resolve_tier_for_accuracy()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/repository.py:103>) — Code-এর দায়িত্ব-বর্ণনা: Find the active tier whose [min_accuracy_pct, max_accuracy_pct] range (inclusive both ends) contains the given accuracy percentage. Used by ExpertReviewService to derive each expert's voting weight — this is the admin-configurable replacement for the old hardcoded credibility deltas.
  - Signature: `async resolve_tier_for_accuracy(self, accuracy_pct: float) -> CredibilityWeightTier \| None`

**Class [ExpertReviewRepository](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/repository.py:117>)** · inherits `BaseRepository[ExpertReview]`

- [ExpertReviewRepository.get_by_submission_and_reviewer()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/repository.py:121>) — একই submission-এ reviewer-এর আগের review খোঁজে।
  - Signature: `async get_by_submission_and_reviewer(self, submission_id: uuid.UUID, reviewer_id: uuid.UUID) -> ExpertReview \| None`

- [ExpertReviewRepository.get_for_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/repository.py:137>) — Submission ID-র সঙ্গে যুক্ত result/record(s) query করে।
  - Signature: `async get_for_submission(self, submission_id: uuid.UUID) -> list[ExpertReview]`

- [ExpertReviewRepository.count_votes_for_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/repository.py:146>) — একটি submission-এর submitted review/vote count আনে।
  - Signature: `async count_votes_for_submission(self, submission_id: uuid.UUID) -> int`

- [ExpertReviewRepository.get_history_for_expert()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/repository.py:155>) — Reviewer-এর আগের votes/history query করে response বানায়।
  - Signature: `async get_history_for_expert(self, expert_id: uuid.UUID, *, limit: int=50, offset: int=0, q: str='') -> list[ExpertReview]`

**Class [VotingConfigRepository](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/repository.py:180>)** · inherits `BaseRepository[VotingConfig]`

দায়িত্ব/contract: Single-row admin-configurable voting parameters — the oldest row is always the one in effect, so there is no fixed min-votes-to-finalize setting any more.

- [VotingConfigRepository.get_or_create()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/repository.py:187>) — Record থাকলে আনে; না থাকলে default/new record তৈরি করে।
  - Signature: `async get_or_create(self) -> VotingConfig`

### backend/app/features/expert_review/router.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/router.py>) · 187 lines

Feature `expert_review`। এই feature-এর HTTP paths, request/response schema, dependencies ও permission guard define করে; handler সংশ্লিষ্ট service/repository-তে কাজ পাঠায়।

- [_get_service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/router.py:40>) — FastAPI dependency হিসেবে এই feature-এর service প্রয়োজনীয় repository/shared resources দিয়ে তৈরি করে।
  - Signature: `_get_service(request: Request, session: AsyncSession=Depends(get_async_session)) -> ExpertReviewService`

- [get_queue()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/router.py:68>) — Role অনুযায়ী expert/admin review queue, eligibility, search ও pagination প্রয়োগ করে।
  - Signature: `async get_queue(limit: int=Query(default=20, ge=1, le=100), offset: int=Query(default=0, ge=0), q: str=Query(default='', max_length=200), state: Literal['all', 'escalated', 'review']=Query(default='all', description='Admin queue only: all \| escalated (awaiting an admin decision) \| review (open, view-only).'), current_user: User=Depends(_EXPERT_OR_ADMIN), svc: ExpertReviewService=Depends(_get_service)) -> list[ExpertQueueItemResponse]`

- [get_queue_item()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/router.py:89>) — Submission, automatic findings, evidence/image ও review state মিলিয়ে queue detail তৈরি করে।
  - Signature: `async get_queue_item(submission_id: uuid.UUID, current_user: User=Depends(_EXPERT_OR_ADMIN), svc: ExpertReviewService=Depends(_get_service)) -> ExpertQueueItemResponse`

- [submit_vote()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/router.py:111>) — Eligibility ও submission lock যাচাই করে overall vote save; consensus/escalation/admin decision চালায়।
  - Signature: `async submit_vote(submission_id: uuid.UUID, body: ExpertVoteRequest, current_user: User=Depends(_EXPERT_OR_ADMIN), svc: ExpertReviewService=Depends(_get_service)) -> ExpertReviewResponse`

- [edit_vote()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/router.py:134>) — অনুমোদিত নিজের review edit করে প্রয়োজনমতো finalization পুনর্মূল্যায়ন করে।
  - Signature: `async edit_vote(review_id: uuid.UUID, body: ExpertVoteUpdateRequest, current_user: User=Depends(_EXPERT_ONLY), svc: ExpertReviewService=Depends(_get_service)) -> ExpertReviewResponse`

- [get_history()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/router.py:156>) — Reviewer-এর আগের votes/history query করে response বানায়।
  - Signature: `async get_history(limit: int=Query(default=50, ge=1, le=200), offset: int=Query(default=0, ge=0), q: str=Query(default='', max_length=200), current_user: User=Depends(_EXPERT_OR_ADMIN), svc: ExpertReviewService=Depends(_get_service)) -> list[ExpertHistoryItemResponse]`

- [get_stats()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/router.py:171>) — Expert review participation ও outcome-related statistics হিসাব করে।
  - Signature: `async get_stats(current_user: User=Depends(_EXPERT_OR_ADMIN), svc: ExpertReviewService=Depends(_get_service)) -> ExpertStatsResponse`

- [get_credibility()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/router.py:183>) — Expert-এর calculated credibility/activation state ও weight সম্পর্কিত response দেয়।
  - Signature: `async get_credibility(current_user: User=Depends(_EXPERT_OR_ADMIN), svc: ExpertReviewService=Depends(_get_service)) -> CredibilityScoreResponse`

### backend/app/features/expert_review/schemas.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/schemas.py>) · 179 lines

Feature `expert_review`। এই feature-এর Pydantic request/response structures ও validation define করে; এগুলো database table নয়।

**Class [ExpertVoteRequest](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/schemas.py:20>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `overall_verdict` | `OverallVerdict` | required / instance-assigned |
| `source_status` | `SourceStatus \| None` | None |
| `content_status` | `ContentStatus \| None` | None |
| `date_status` | `DateStatus \| None` | None |
| `justification` | `str` | Field(..., min_length=50, max_length=5000, description="Reviewer's written justification for the vote (min 50 characters). Shown publicly after the final decision.") |

- [ExpertVoteRequest._check_conditional_fields()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/schemas.py:34>) — Supplementary source/headline/date fields পরস্পর সঙ্গতিপূর্ণ কি না validate করে।
  - Signature: `_check_conditional_fields(self) -> 'ExpertVoteRequest'`

**Class [ExpertVoteUpdateRequest](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/schemas.py:44>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `overall_verdict` | `OverallVerdict \| None` | None |
| `source_status` | `SourceStatus \| None` | None |
| `content_status` | `ContentStatus \| None` | None |
| `date_status` | `DateStatus \| None` | None |
| `justification` | `str \| None` | Field(default=None, min_length=50, max_length=5000) |

**Class [ExpertReviewResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/schemas.py:52>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `id` | `str` | required / instance-assigned |
| `submission_id` | `str` | required / instance-assigned |
| `reviewer_id` | `str \| None` | required / instance-assigned |
| `ai_overall_verdict` | `OverallVerdict \| None` | Field(default=None, description='MULTIMODAL only — automated checks never produce an Overall verdict otherwise.') |
| `ai_source_status` | `SourceStatus \| None` | required / instance-assigned |
| `ai_content_status` | `ContentStatus \| None` | required / instance-assigned |
| `ai_date_status` | `DateStatus \| None` | required / instance-assigned |
| `vote_overall_verdict` | `OverallVerdict` | required / instance-assigned |
| `vote_source_status` | `SourceStatus \| None` | required / instance-assigned |
| `vote_content_status` | `ContentStatus \| None` | required / instance-assigned |
| `vote_date_status` | `DateStatus \| None` | required / instance-assigned |
| `justification` | `str \| None` | required / instance-assigned |
| `credibility_weight` | `float` | required / instance-assigned |
| `status` | `str` | required / instance-assigned |
| `is_admin_decision` | `bool` | False |
| `created_at` | `datetime` | required / instance-assigned |
| `updated_at` | `datetime` | required / instance-assigned |

**Class [ExpertTopArticle](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/schemas.py:77>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `url` | `str` | required / instance-assigned |
| `title` | `str \| None` | None |
| `published_date` | `str \| None` | None |
| `rank_score` | `float \| None` | None |
| `body_snippet` | `str \| None` | None |

**Class [ExpertQueueItemResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/schemas.py:85>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `str` | required / instance-assigned |
| `submission_type` | `SubmissionType` | required / instance-assigned |
| `status` | `SubmissionStatus \| None` | None |
| `escalated_at` | `datetime \| None` | None |
| `published_date` | `date \| None` | Field(default=None, description='The publication date the submitter claimed, if any.') |
| `has_voted` | `bool` | False |
| `can_vote` | `bool` | Field(default=False, description='Whether the requesting reviewer may vote now: experts on open claims they did not submit or vote on; admins only on ESCALATED claims.') |
| `decision_mode` | `str` | Field(default='EXPERT_VOTE', description="EXPERT_VOTE, or ADMIN_FINAL when an admin's vote will be the final decision.") |
| `headline` | `str \| None` | required / instance-assigned |
| `body_text` | `str \| None` | None |
| `claimed_source_text` | `str \| None` | required / instance-assigned |
| `ai_label` | `str \| None` | Field(default=None, description="Human-readable summary of the AI's call, for display.") |
| `ai_overall_verdict` | `OverallVerdict \| None` | None |
| `source_status` | `SourceStatus \| None` | None |
| `content_status` | `ContentStatus \| None` | None |
| `headline_status` | `HeadlineAlterationStatus \| None` | None |
| `date_status` | `DateStatus \| None` | None |
| `ai_confidence` | `float \| None` | required / instance-assigned |
| `submitted_at` | `datetime` | required / instance-assigned |
| `vote_count` | `int` | required / instance-assigned |
| `top_article` | `ExpertTopArticle \| None` | None |
| `image_url` | `str \| None` | Field(default=None, description='Multimodal submissions only — the submitted card/photo') |
| `headline_check_status` | `HeadlineCheckStatus \| None` | Field(default=None, description='Processing status of the Headline Alteration check (why content_status may be null).') |
| `headline_alteration` | `HeadlineAlterationDetail \| None` | Field(default=None, description='Headline Alteration detail (claim headline vs. source title only).') |
| `body_similarity` | `BodySimilarityReport \| None` | Field(default=None, description='Claim body vs. source body similarity measurements - never a verdict.') |

**Class [ExpertHistoryItemResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/schemas.py:138>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `review_id` | `str` | required / instance-assigned |
| `submission_id` | `str` | required / instance-assigned |
| `submission_type` | `SubmissionType` | required / instance-assigned |
| `submission_status` | `SubmissionStatus \| None` | None |
| `headline` | `str \| None` | required / instance-assigned |
| `claimed_source_text` | `str \| None` | required / instance-assigned |
| `vote_overall_verdict` | `OverallVerdict` | required / instance-assigned |
| `vote_source_status` | `SourceStatus \| None` | required / instance-assigned |
| `vote_content_status` | `ContentStatus \| None` | required / instance-assigned |
| `vote_date_status` | `DateStatus \| None` | required / instance-assigned |
| `ai_overall_verdict` | `OverallVerdict \| None` | required / instance-assigned |
| `ai_source_status` | `SourceStatus \| None` | required / instance-assigned |
| `ai_content_status` | `ContentStatus \| None` | required / instance-assigned |
| `ai_date_status` | `DateStatus \| None` | required / instance-assigned |
| `final_overall_verdict` | `OverallVerdict \| None` | required / instance-assigned |
| `final_source_status` | `SourceStatus \| None` | None |
| `final_content_status` | `ContentStatus \| None` | None |
| `final_date_status` | `DateStatus \| None` | None |
| `matched` | `bool \| None` | required / instance-assigned |
| `is_admin_decision` | `bool` | False |
| `voted_at` | `datetime` | required / instance-assigned |

**Class [ExpertStatsResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/schemas.py:162>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `user_id` | `str` | required / instance-assigned |
| `full_name` | `str \| None` | required / instance-assigned |
| `total_votes` | `int` | required / instance-assigned |
| `correct_votes` | `int` | required / instance-assigned |
| `accuracy_pct` | `float \| None` | required / instance-assigned |
| `current_credibility` | `float \| None` | required / instance-assigned |
| `activation_threshold` | `int` | 10 |

**Class [CredibilityScoreResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/schemas.py:172>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `user_id` | `str` | required / instance-assigned |
| `score` | `float \| None` | required / instance-assigned |
| `total_votes` | `int` | required / instance-assigned |
| `correct_votes` | `int` | required / instance-assigned |
| `updated_at` | `datetime` | required / instance-assigned |

### backend/app/features/expert_review/service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py>) · 824 lines

Review eligibility, vote/edit, frozen vote weight, overall-only consensus, admin escalation/finalization এবং credibility recomputation।

- [_tally()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:61>) — Code-এর দায়িত্ব-বর্ণনা: Weighted vote counts — experts only. Neither the AI's call nor any supplementary (source/headline/date) assessment is ever added.
  - Signature: `_tally(reviews: list[ExpertReview], get_vote: Callable[[ExpertReview], _T \| None]) -> dict[_T, float]`

- [_evaluate()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:72>) — Code-এর দায়িত্ব-বর্ণনা: Does the overall tally clear ALL of: a unique leader, leader >= T, voters >= M, leader - runner_up >= margin? Returns (passes, leader). `leader` is None while the top weight is tied — there is no AI or ordering tie-break, so a tie never finalizes (even with margin 0).
  - Signature: `_evaluate(weights: dict[_T, float], voters: int, config: VotingConfig) -> tuple[bool, _T \| None]`

- [_aware()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:95>) — Naive datetime হলে timezone-aware representation দেয়।
  - Signature: `_aware(value: datetime) -> datetime`

- [review_limits_exceeded()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:99>) — Code-এর দায়িত্ব-বর্ণনা: OR semantics: any configured limit exceeded escalates. A NULL limit is not configured and never counts as exceeded.
  - Signature: `review_limits_exceeded(config: VotingConfig, *, votes: int, submitted_at: datetime, now: datetime \| None=None) -> bool`

**Class [ExpertReviewService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:112>)** · inherits `plain class`

- [ExpertReviewService.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:114>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, review_repo: ExpertReviewRepository, profile_repo: ExpertProfileRepository, tier_repo: CredibilityWeightTierRepository, submission_repo: SubmissionRepository, result_repo: ResultRepository, multimodal_repo: MultimodalAnalysisRepository, voting_config_repo: VotingConfigRepository, storage: MultimodalStorageService \| None=None, photocard_storage: PhotoCardStorageService \| None=None) -> None`

- [ExpertReviewService._fetch_photocard_image_url()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:139>) — Photocard extraction image key থেকে preview URL নেয়।
  - Signature: `async _fetch_photocard_image_url(self, submission_id: uuid.UUID) -> str \| None`

- [ExpertReviewService._fetch_top_article()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:150>) — Stored selected evidence article-এর review-friendly representation আনে।
  - Signature: `async _fetch_top_article(self, result: VerificationResult \| None) -> ExpertTopArticle \| None`

- [ExpertReviewService._headline_alteration_and_body()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:172>) — Code-এর দায়িত্ব-বর্ণনা: Headline Alteration detail + body similarity report from the persisted analysis blob (the same source presenter.py reads), so the expert view shows the identical detail after save/reload. Legacy rows never surface an old content verdict as a headline detail.
  - Signature: `_headline_alteration_and_body(result: VerificationResult \| None)`

- [ExpertReviewService._build_queue_item()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:185>) — Submission, automatic findings, evidence/image ও review state মিলিয়ে queue detail তৈরি করে।
  - Signature: `async _build_queue_item(self, submission: Submission, *, full_body: bool, viewer_id: uuid.UUID \| None=None, viewer_role: str \| None=None) -> ExpertQueueItemResponse`

- [ExpertReviewService.get_queue_item()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:270>) — Submission, automatic findings, evidence/image ও review state মিলিয়ে queue detail তৈরি করে।
  - Signature: `async get_queue_item(self, submission_id: uuid.UUID, *, viewer_id: uuid.UUID \| None=None, viewer_role: str \| None=None) -> ExpertQueueItemResponse`

- [ExpertReviewService.get_queue()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:285>) — Role অনুযায়ী expert/admin review queue, eligibility, search ও pagination প্রয়োগ করে।
  - Signature: `async get_queue(self, expert_id: uuid.UUID, *, limit: int=20, offset: int=0, q: str='', viewer_role: str='expert', state: str='all') -> list[ExpertQueueItemResponse]`
  - Source contract: Experts see open (EXPERT_REVIEW) claims they have not voted on and did not submit — never escalated ones. Admins see the admin expert queue: escalated claims (theirs to decide, listed first) plus open claims they can only view. `state` (admin only): all | escalated | review.

- [ExpertReviewService._ai_snapshot()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:340>) — Code-এর দায়িত্ব-বর্ণনা: The AI's own call at vote time, frozen onto the vote row.
  - Signature: `async _ai_snapshot(self, submission: Submission) -> tuple[OverallVerdict \| None, SourceStatus \| None, ContentStatus \| None, DateStatus \| None]`

- [ExpertReviewService._check_supplementary()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:366>) — Supplementary source/headline/date fields পরস্পর সঙ্গতিপূর্ণ কি না validate করে।
  - Signature: `_check_supplementary(submission: Submission, source_status: SourceStatus \| None, content_status: ContentStatus \| None, date_status: DateStatus \| None) -> None`
  - Source contract: Supplementary findings are optional and never decide anything — they only have to be internally consistent.

- [ExpertReviewService.submit_vote()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:385>) — Eligibility ও submission lock যাচাই করে overall vote save; consensus/escalation/admin decision চালায়।
  - Signature: `async submit_vote(self, submission_id: uuid.UUID, expert_id: uuid.UUID, overall_verdict: OverallVerdict, source_status: SourceStatus \| None, content_status: ContentStatus \| None, date_status: DateStatus \| None, justification: str, *, voter_role: str='expert') -> ExpertReviewResponse`

- [ExpertReviewService._admin_decision()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:470>) — Code-এর দায়িত্ব-বর্ণনা: An administrator's overall vote on an ESCALATED claim IS the final decision; earlier expert votes cannot override it. Every other claim is view-only for admins. Caller holds the submission row lock, so a second admin decision or a concurrent sweep sees FINALIZED and is refused.
  - Signature: `async _admin_decision(self, submission: Submission, admin_id: uuid.UUID, overall_verdict: OverallVerdict, source_status: SourceStatus \| None, content_status: ContentStatus \| None, date_status: DateStatus \| None, justification: str) -> ExpertReviewResponse`

- [ExpertReviewService._resolve_weight()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:522>) — Code-এর দায়িত্ব-বর্ণনা: Admin-configurable voting weight, resolved from credibility_weight_tiers by the expert's current accuracy% — replaces the old hardcoded ±0.05/-0.03 credibility deltas (PDF §2.2: "administrator-defined rules... without changing system code"). Below config.activation_threshold_votes (N) votes on claims whose final decision is complete, every vote counts as weight 1.0 regardless of tier — this is `weight_applied`, snapshotted onto the vote row so later tier/config changes never retroactively alter it.
  - Signature: `async _resolve_weight(self, profile, config: VotingConfig)`

- [ExpertReviewService.edit_vote()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:538>) — অনুমোদিত নিজের review edit করে প্রয়োজনমতো finalization পুনর্মূল্যায়ন করে।
  - Signature: `async edit_vote(self, review_id: uuid.UUID, expert_id: uuid.UUID, overall_verdict: OverallVerdict \| None, source_status: SourceStatus \| None, content_status: ContentStatus \| None, date_status: DateStatus \| None, justification: str \| None) -> ExpertReviewResponse`

- [ExpertReviewService.get_history()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:587>) — Reviewer-এর আগের votes/history query করে response বানায়।
  - Signature: `async get_history(self, expert_id: uuid.UUID, *, limit: int=50, offset: int=0, q: str='') -> list[ExpertHistoryItemResponse]`

- [ExpertReviewService.get_stats()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:644>) — Expert review participation ও outcome-related statistics হিসাব করে।
  - Signature: `async get_stats(self, expert_id: uuid.UUID) -> ExpertStatsResponse`

- [ExpertReviewService.get_credibility()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:667>) — Expert-এর calculated credibility/activation state ও weight সম্পর্কিত response দেয়।
  - Signature: `async get_credibility(self, expert_id: uuid.UUID) -> CredibilityScoreResponse`
  - Source contract: Current score (unrounded); None until the expert has cast the configured activation number of votes.

- [ExpertReviewService.reevaluate()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:680>) — Code-এর দায়িত্ব-বর্ণনা: Row-lock the submission and finalize or escalate it if its votes or review limits now require it (used by the escalation sweep). Returns True when the status changed. Caller commits.
  - Signature: `async reevaluate(self, submission_id: uuid.UUID, *, now: datetime \| None=None) -> bool`

- [ExpertReviewService._finalize_or_escalate()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:687>) — Code-এর দায়িত্ব-বর্ণনা: Re-evaluates an EXPERT_REVIEW claim after a vote, an edit or a sweep. Only the reviewers' OVERALL votes count — the supplementary source/headline/date assessments never affect the outcome. Finalizes when the overall tally passes; otherwise escalates when any configured review limit is exceeded. Returns True when the status changed. Caller must already hold the submission's row lock.
  - Signature: `async _finalize_or_escalate(self, submission: Submission, *, now: datetime \| None=None) -> bool`

- [ExpertReviewService._apply_final_decision()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:726>) — Code-এর দায়িত্ব-বর্ণনা: Writes the final overall verdict. The AI's own columns and the legacy final_source/content/date columns are left untouched — the supplementary assessments are never promoted into a finding.
  - Signature: `async _apply_final_decision(self, submission: Submission, final_overall: OverallVerdict, expert_reviews: list[ExpertReview]) -> None`

- [ExpertReviewService._maybe_escalate()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:748>) — Configured review limit পেরোলে open claim escalated করে ও admin notification দেয়।
  - Signature: `async _maybe_escalate(self, submission: Submission, voters: int, config: VotingConfig, *, now: datetime \| None=None) -> bool`

- [ExpertReviewService._update_expert_profiles()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:769>) — Code-এর দায়িত্ব-বর্ণনা: Correctness is judged on the Overall verdict uniformly across all submission types — the one dimension every expert votes on, and the headline judgment call the platform ultimately publishes. An admin's own decision row is never scored. A vote counts towards N (activation_threshold_votes) and accuracy only once its claim's final decision is complete. The counters are re-derived from the finalized claims rather than incremented, so they cannot drift (an incremented counter kept counting votes on claims later deleted).
  - Signature: `async _update_expert_profiles(self, reviews: list[ExpertReview]) -> None`

- [_ai_label_structured()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:789>) — Automatic structured/model output থেকে review UI-এর display label বানায়।
  - Signature: `_ai_label_structured(result: VerificationResult \| None, submission: Submission \| None=None) -> str \| None`

- [_ai_label_multimodal()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:799>) — Automatic structured/model output থেকে review UI-এর display label বানায়।
  - Signature: `_ai_label_multimodal(mm: MultimodalAnalysis \| None) -> str \| None`

- [_review_to_response()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/expert_review/service.py:805>) — Stored model/data-কে নির্দিষ্ট public response schema-তে রূপ দেয়।
  - Signature: `_review_to_response(r: ExpertReview) -> ExpertReviewResponse`

### backend/app/features/health/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/health/__init__.py>) · 1 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/health/router.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/health/router.py>) · 62 lines

Feature `health`। এই feature-এর HTTP paths, request/response schema, dependencies ও permission guard define করে; handler সংশ্লিষ্ট service/repository-তে কাজ পাঠায়।

**Class [HealthResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/health/router.py:13>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `status` | `str` | required / instance-assigned |
| `version` | `str` | '1.0.0' |

**Class [ReadinessResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/health/router.py:18>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `status` | `str` | required / instance-assigned |
| `database` | `str` | required / instance-assigned |
| `redis` | `str` | required / instance-assigned |

- [liveness()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/health/router.py:30>) — Application process responding আছে—এই health response দেয়।
  - Signature: `async liveness() -> HealthResponse`

- [readiness()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/health/router.py:40>) — Database ও Redis connectivity পরীক্ষা করে readiness response/status দেয়।
  - Signature: `async readiness(cache: CacheService=Depends(get_cache_service)) -> ReadinessResponse`

### backend/app/features/multimodal/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/__init__.py>) · 0 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/multimodal/models.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/models.py>) · 114 lines

Feature `multimodal`। SQLAlchemy ORM entities: নিচে exact table, fields ও foreign-key/constraint declarations দেওয়া আছে।

**Class [MultimodalAnalysis](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/models.py:18>)** · inherits `UUIDMixin, TimestampMixin, ReprMixin, Base` · table `multimodal_analysis`

দায়িত্ব/contract: DatabaseDescription.pdf Table 4.9 — multimodal_analysis. Storage target for multimodal predictions, tied 1:1 to a `Submission` row per the thesis ER diagram.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `Mapped[uuid.UUID]` | mapped_column(UUID(as_uuid=True), ForeignKey('submissions.id', ondelete='CASCADE'), unique=True, nullable=False, index=True) |
| `image_object_key` | `Mapped[str]` | mapped_column(String(1024), nullable=False) |
| `prediction` | `Mapped[MultimodalPredictionLabel]` | mapped_column(Enum(MultimodalPredictionLabel, name='multimodal_prediction_enum', create_type=True), nullable=False) |
| `confidence_fake` | `Mapped[float]` | mapped_column(Float, nullable=False) |
| `confidence_real` | `Mapped[float]` | mapped_column(Float, nullable=False) |
| `expert_overall_verdict` | `Mapped[OverallVerdict \| None]` | mapped_column(Enum(OverallVerdict, name='overall_verdict_enum', create_type=False), nullable=True, comment='Expert-finalized Overall verdict — NULL until expert review finalizes this claim. Not written by the inference engine.') |
| `finalized_at` | `Mapped[Optional[datetime]]` | mapped_column(DateTime(timezone=True), nullable=True, comment='When expert review finalized this claim; NULL until then.') |
| `text_embedding` | `Mapped[list[float] \| None]` | mapped_column(ARRAY(Float), nullable=True, comment='BanglaBERT [CLS] embedding vector (768-dim)') |
| `image_embedding` | `Mapped[list[float] \| None]` | mapped_column(ARRAY(Float), nullable=True, comment='EfficientNet-B4 global-pool features (1792-dim)') |
| `combined_embedding` | `Mapped[list[float] \| None]` | mapped_column(ARRAY(Float), nullable=True, comment='L2-normalised concat of text+image embeddings (2560-dim)') |
| `model_version` | `Mapped[str]` | mapped_column(String(100), nullable=False, index=True) |
| `is_duplicate_of_id` | `Mapped[Optional[uuid.UUID]]` | mapped_column(UUID(as_uuid=True), ForeignKey('multimodal_analysis.id', ondelete='SET NULL'), nullable=True, default=None, comment="Not in DatabaseDescription.pdf Table 4.9 — added because the PDF's multimodal_analysis has no dedup column and the live duplicate-detection feature needs one. Mirrors legacy multimodal_predictions.is_duplicate_of_id.") |
| `submission` | `Mapped['Submission']` | relationship('Submission', primaryjoin='MultimodalAnalysis.submission_id == Submission.id', viewonly=True, lazy='select') |

Database constraints/indexes: `__table_args__ = (CheckConstraint('confidence_fake >= 0.0 AND confidence_fake <= 1.0', name='ck_multimodal_analysis_confidence_fake_range'), CheckConstraint('confidence_real >= 0.0 AND confidence_real <= 1.0', name='ck_multimodal_analysis_confidence_real_range'))`

### backend/app/features/multimodal/pipeline/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/__init__.py>) · 11 lines

Python package marker। Public imports/re-exports: from app.features.multimodal.pipeline.model_loader import MultimodalModelLoader; from app.features.multimodal.pipeline.embedding_extractor import MultimodalEmbeddingExtractor; from app.features.multimodal.pipeline.inference_engine import MultimodalInferenceEngine

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/multimodal/pipeline/embedding_extractor.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/embedding_extractor.py>) · 151 lines

BanglaBERT text feature, EfficientNet image feature, normalized combined fingerprint ও duplicate-threshold check।

**Class [MultimodalEmbeddingExtractor](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/embedding_extractor.py:26>)** · inherits `plain class`

- [MultimodalEmbeddingExtractor.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/embedding_extractor.py:28>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, loader: MultimodalModelLoader) -> None`

- [MultimodalEmbeddingExtractor.extract_text_embedding()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/embedding_extractor.py:33>) — Tokenized article body থেকে BanglaBERT text feature বের করে।
  - Signature: `async extract_text_embedding(self, body_text: str) -> np.ndarray`

- [MultimodalEmbeddingExtractor.extract_image_embedding()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/embedding_extractor.py:41>) — Preprocessed image থেকে EfficientNet image feature বের করে।
  - Signature: `async extract_image_embedding(self, image_bytes: bytes) -> np.ndarray`

- [MultimodalEmbeddingExtractor.extract_all_embeddings()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/embedding_extractor.py:49>) — Text/image backbone features ও combined duplicate fingerprint একত্রে ফেরত দেয়।
  - Signature: `async extract_all_embeddings(self, body_text: str, image_bytes: bytes) -> tuple[np.ndarray, np.ndarray, np.ndarray]`

- [MultimodalEmbeddingExtractor.cosine_similarity()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/embedding_extractor.py:62>) — দুই vector/text embedding-এর cosine similarity মাপে।
  - Signature: `cosine_similarity(a: np.ndarray, b: np.ndarray) -> float`

- [MultimodalEmbeddingExtractor.is_duplicate()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/embedding_extractor.py:70>) — Text, image ও combined similarity তিনটি configured threshold পূরণ করে কি না দেখে।
  - Signature: `is_duplicate(self, *, query_text_emb: np.ndarray, query_img_emb: np.ndarray, query_combined_emb: np.ndarray, candidate_text_emb: np.ndarray, candidate_img_emb: np.ndarray, candidate_combined_emb: np.ndarray) -> tuple[bool, dict[str, float]]`

- [MultimodalEmbeddingExtractor._text_encode_sync()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/embedding_extractor.py:101>) — Tokenized article body থেকে BanglaBERT text feature বের করে।
  - Signature: `_text_encode_sync(self, body_text: str) -> np.ndarray`

- [MultimodalEmbeddingExtractor._image_encode_sync()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/embedding_extractor.py:122>) — Preprocessed image থেকে EfficientNet image feature বের করে।
  - Signature: `_image_encode_sync(self, image_bytes: bytes) -> np.ndarray`

- [MultimodalEmbeddingExtractor._build_combined_embedding()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/embedding_extractor.py:143>) — Text ও image features normalize/concatenate করে combined fingerprint বানায়।
  - Signature: `_build_combined_embedding(text_emb: np.ndarray, img_emb: np.ndarray) -> np.ndarray`

### backend/app/features/multimodal/pipeline/inference_engine.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/inference_engine.py>) · 145 lines

Raw input অথবা already-computed backbone features থেকে classifier+softmax inference; async executor wrapper।

**Class [PredictionResult](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/inference_engine.py:34>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `prediction` | `str` | required / instance-assigned |
| `confidence_fake` | `float` | required / instance-assigned |
| `confidence_real` | `float` | required / instance-assigned |
| `raw_logits` | `tuple[float, float]` | required / instance-assigned |

**Class [MultimodalInferenceEngine](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/inference_engine.py:42>)** · inherits `plain class`

- [MultimodalInferenceEngine.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/inference_engine.py:44>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, loader: MultimodalModelLoader) -> None`

- [MultimodalInferenceEngine.predict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/inference_engine.py:49>) — Multimodal body/image prediction workflow চালায়; service layer-এ storage/dedup/persistence-ও হয়।
  - Signature: `async predict(self, body_text: str, image_bytes: bytes) -> PredictionResult`
  - Source contract: Full forward pass from raw inputs (both backbones + classifier).

- [MultimodalInferenceEngine.predict_from_features()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/inference_engine.py:57>) — Code-এর দায়িত্ব-বর্ণনা: Classifier only, on the backbone outputs already computed by `MultimodalEmbeddingExtractor` (raw [CLS] text features and pooled image features - NOT the normalised combined vector). Same tokenizer, transform and eval-mode backbones as `predict`, so the backbones need not run a second time.
  - Signature: `async predict_from_features(self, text_features: np.ndarray, image_features: np.ndarray) -> PredictionResult`

- [MultimodalInferenceEngine._run()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/inference_engine.py:69>) — Blocking inference callable executor-এ চালায় এবং model-specific failure handling করে।
  - Signature: `async _run(self, forward) -> PredictionResult`

- [MultimodalInferenceEngine._forward_pass_sync()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/inference_engine.py:90>) — Body tokenize ও image preprocess করে দুই backbone ও classifier চালায়।
  - Signature: `_forward_pass_sync(self, body_text: str, image_bytes: bytes) -> PredictionResult`

- [MultimodalInferenceEngine._classify_features_sync()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/inference_engine.py:122>) — আগেই computed features tensor-এ নিয়ে classifier চালায়।
  - Signature: `_classify_features_sync(self, text_features: np.ndarray, image_features: np.ndarray) -> PredictionResult`

- [MultimodalInferenceEngine._classify()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/inference_engine.py:131>) — Classifier logits থেকে softmax class/confidence result তৈরি করে।
  - Signature: `_classify(self, img_feats: torch.Tensor, text_feats: torch.Tensor) -> PredictionResult`
  - Source contract: Classifier + softmax for one example; caller holds `torch.no_grad()`.

### backend/app/features/multimodal/pipeline/model_architecture.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_architecture.py>) · 74 lines

EfficientNetBackbone, BanglaBERTBackbone, concatenation/LayerNorm/MLP classifier MultiFusionFake।

**Class [EfficientNetBackbone](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_architecture.py:9>)** · inherits `nn.Module`

- [EfficientNetBackbone.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_architecture.py:11>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, model_name: str='efficientnet_b4', pretrained: bool=True) -> None`

- [EfficientNetBackbone.forward()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_architecture.py:23>) — Image tensor থেকে pooled visual features বের করে।
  - Signature: `forward(self, x: torch.Tensor) -> torch.Tensor`

**Class [BanglaBERTBackbone](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_architecture.py:27>)** · inherits `nn.Module`

- [BanglaBERTBackbone.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_architecture.py:29>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, model_name: str='csebuetnlp/banglabert') -> None`

- [BanglaBERTBackbone.forward()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_architecture.py:34>) — Input token IDs/attention mask থেকে প্রথম token-এর [CLS] representation বের করে।
  - Signature: `forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor`

**Class [MultiFusionFake](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_architecture.py:43>)** · inherits `nn.Module`

- [MultiFusionFake.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_architecture.py:45>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, img_dim: int, text_dim: int, num_classes: int, dropout: float=0.4) -> None`

- [MultiFusionFake.forward()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_architecture.py:67>) — Image+text features concatenate, LayerNorm ও MLP দিয়ে দুই class-এর logits দেয়।
  - Signature: `forward(self, img_feats: torch.Tensor, text_feats: torch.Tensor) -> torch.Tensor`

### backend/app/features/multimodal/pipeline/model_loader.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_loader.py>) · 184 lines

Model directory validation, trained weights/tokenizer/device load এবং loaded resources access।

**Class [MultimodalModelLoader](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_loader.py:29>)** · inherits `plain class`

দায়িত্ব/contract: Owns one set of loaded weights. "Loaded" is per instance: a new loader (e.g. after an app restart in the same process) loads its own weights instead of reporting another instance's state.

- [MultimodalModelLoader.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_loader.py:34>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self) -> None`

- [MultimodalModelLoader.load()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_loader.py:46>) — এই service-এর configured model/tokenizer/weights memory-তে load করে।
  - Signature: `async load(self) -> None`

- [MultimodalModelLoader._validate_model_dir()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_loader.py:88>) — প্রয়োজনীয় trained weight/tokenizer paths আছে কি না পরীক্ষা করে।
  - Signature: `_validate_model_dir(self, model_dir: str) -> None`

- [MultimodalModelLoader._load_sync()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_loader.py:105>) — এই service-এর configured model/tokenizer/weights memory-তে load করে।
  - Signature: `_load_sync(self, model_dir: str) -> tuple[EfficientNetBackbone, BanglaBERTBackbone, MultiFusionFake, AutoTokenizer]`

- [MultimodalModelLoader.is_loaded()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_loader.py:155>) — এই loader instance usable model weights load করেছে কি না জানায়।
  - Signature: `is_loaded(self) -> bool`

- [MultimodalModelLoader.img_backbone()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_loader.py:159>) — Loader-এর নির্দিষ্ট model/tokenizer/device resource ফেরত দেয়।
  - Signature: `img_backbone(self) -> EfficientNetBackbone`

- [MultimodalModelLoader.text_backbone()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_loader.py:165>) — Loader-এর নির্দিষ্ট model/tokenizer/device resource ফেরত দেয়।
  - Signature: `text_backbone(self) -> BanglaBERTBackbone`

- [MultimodalModelLoader.classifier()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_loader.py:171>) — Loader-এর নির্দিষ্ট model/tokenizer/device resource ফেরত দেয়।
  - Signature: `classifier(self) -> MultiFusionFake`

- [MultimodalModelLoader.tokenizer()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_loader.py:177>) — Loader-এর নির্দিষ্ট model/tokenizer/device resource ফেরত দেয়।
  - Signature: `tokenizer(self) -> AutoTokenizer`

- [MultimodalModelLoader.device()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/model_loader.py:183>) — Loader-এর নির্দিষ্ট model/tokenizer/device resource ফেরত দেয়।
  - Signature: `device(self) -> torch.device`

### backend/app/features/multimodal/pipeline/preprocessing.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/preprocessing.py>) · 20 lines

Training-compatible evaluation image transform তৈরি।

- [build_eval_transform()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/pipeline/preprocessing.py:13>) — Inference image resize/tensor/normalization transform তৈরি করে।
  - Signature: `build_eval_transform(img_size: int) -> transforms.Compose`

### backend/app/features/multimodal/repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/repository.py>) · 128 lines

Feature `multimodal`। এই feature-এর database queries ও persistence operations; যেখানে BaseRepository inherit করেছে সেখানে common CRUD inherited।

**Class [MultimodalAnalysisRepository](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/repository.py:20>)** · inherits `plain class`

দায়িত্ব/contract: Storage for multimodal analysis linked to submissions.

- [MultimodalAnalysisRepository.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/repository.py:23>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, db: AsyncSession) -> None`

- [MultimodalAnalysisRepository.create()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/repository.py:26>) — নতুন entity/entities session-এ যোগ করে persistence/flush করে।
  - Signature: `async create(self, *, submission_id: uuid.UUID, image_object_key: str, prediction: str, confidence_fake: float, confidence_real: float, text_embedding: np.ndarray, image_embedding: np.ndarray, combined_embedding: np.ndarray, model_version: str, is_duplicate_of_id: uuid.UUID \| None=None) -> MultimodalAnalysis`

- [MultimodalAnalysisRepository.get_by_id()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/repository.py:64>) — ID অনুযায়ী database record আনে; না থাকলে not-found error দেয়।
  - Signature: `async get_by_id(self, analysis_id: uuid.UUID) -> MultimodalAnalysis`

- [MultimodalAnalysisRepository.get_by_submission_id()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/repository.py:76>) — Submission ID-র সঙ্গে যুক্ত result/record(s) query করে।
  - Signature: `async get_by_submission_id(self, submission_id: uuid.UUID) -> MultimodalAnalysis \| None`

- [MultimodalAnalysisRepository.update()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/repository.py:86>) — প্রদত্ত fields entity-তে বদলে database session flush করে।
  - Signature: `async update(self, instance: MultimodalAnalysis, **fields) -> MultimodalAnalysis`

- [MultimodalAnalysisRepository.list_recent()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/repository.py:94>) — নির্ধারিত ordering/pagination অনুযায়ী records আনে।
  - Signature: `async list_recent(self, *, limit: int=20, offset: int=0) -> Sequence[MultimodalAnalysis]`

- [MultimodalAnalysisRepository.count_all()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/repository.py:105>) — সংশ্লিষ্ট records-এর total count বের করে।
  - Signature: `async count_all(self) -> int`

- [MultimodalAnalysisRepository.find_similar_candidates()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/repository.py:109>) — Same model version-এর bounded recent embedding records duplicate comparison-এর জন্য আনে।
  - Signature: `async find_similar_candidates(self, *, model_version: str, limit: int \| None=None) -> Sequence[MultimodalAnalysis]`

### backend/app/features/multimodal/router.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/router.py>) · 294 lines

Feature `multimodal`। এই feature-এর HTTP paths, request/response schema, dependencies ও permission guard define করে; handler সংশ্লিষ্ট service/repository-তে কাজ পাঠায়।

- [predict_async()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/router.py:46>) — Code-এর দায়িত্ব-বর্ণনা: Accept a durable job; poll /submissions/{id} and then /multimodal/by-submission/{id}.
  - Signature: `async predict_async(request: Request, headline: str=Form(..., min_length=1, max_length=2000), body_text: str=Form(..., min_length=10, max_length=50000), image: UploadFile=File(...), db: AsyncSession=Depends(get_async_session), current_user: User \| None=Depends(get_current_user_optional)) -> dict`

- [_get_loader()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/router.py:84>) — Application state থেকে shared client/model/storage service সরবরাহ করে।
  - Signature: `_get_loader(request: Request)`

- [_get_storage()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/router.py:91>) — Application state থেকে shared client/model/storage service সরবরাহ করে।
  - Signature: `_get_storage(request: Request) -> MultimodalStorageService`

- [_to_detail()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/router.py:98>) — Stored model/data-কে নির্দিষ্ট public response schema-তে রূপ দেয়।
  - Signature: `async _to_detail(record: MultimodalAnalysis, submission_repo: SubmissionRepository, storage: MultimodalStorageService) -> MultimodalPredictionDetail`

- [predict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/router.py:145>) — Multimodal body/image prediction workflow চালায়; service layer-এ storage/dedup/persistence-ও হয়।
  - Signature: `async predict(request: Request, headline: str=Form(..., min_length=1, max_length=2000, description='News headline (stored for display; not used by the model)'), body_text: str=Form(..., min_length=10, max_length=50000, description='Article body text — the text input to the BanglaBERT backbone'), image: UploadFile=File(..., description='News article image (JPEG/PNG/WebP, max 10 MB)'), db: AsyncSession=Depends(get_async_session), current_user: User \| None=Depends(get_current_user_optional)) -> MultimodalPredictionResponse`

- [get_prediction()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/router.py:221>) — Prediction ID/submission ID অথবা paginated list দিয়ে multimodal result ফেরত দেয়।
  - Signature: `async get_prediction(prediction_id: uuid.UUID, request: Request, db: AsyncSession=Depends(get_async_session)) -> MultimodalPredictionDetail`

- [get_prediction_by_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/router.py:252>) — Prediction ID/submission ID অথবা paginated list দিয়ে multimodal result ফেরত দেয়।
  - Signature: `async get_prediction_by_submission(submission_id: uuid.UUID, request: Request, db: AsyncSession=Depends(get_async_session)) -> MultimodalPredictionDetail`

- [list_predictions()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/router.py:277>) — Prediction ID/submission ID অথবা paginated list দিয়ে multimodal result ফেরত দেয়।
  - Signature: `async list_predictions(request: Request, limit: int=Query(default=20, ge=1, le=100, description='Number of results to return'), offset: int=Query(default=0, ge=0, description='Pagination offset'), db: AsyncSession=Depends(get_async_session)) -> PredictionListResponse`

### backend/app/features/multimodal/schemas.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/schemas.py>) · 82 lines

Feature `multimodal`। এই feature-এর Pydantic request/response structures ও validation define করে; এগুলো database table নয়।

**Class [MultimodalPredictionResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/schemas.py:12>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `prediction_id` | `str` | Field(..., description='UUID of the stored prediction record') |
| `submission_id` | `str` | Field(..., description='UUID of the paired submissions row') |
| `prediction` | `str` | Field(..., description="'FAKE' or 'NON_FAKE' — the AI's preliminary call") |
| `confidence_fake` | `float` | Field(..., ge=0.0, le=1.0, description='P(FAKE) from softmax') |
| `confidence_real` | `float` | Field(..., ge=0.0, le=1.0, description='P(NON_FAKE) from softmax') |
| `expert_overall_verdict` | `Optional[OverallVerdict]` | Field(default=None, description="Expert-finalized Overall verdict (Fake/Real/Misleading/Altered). NULL until expert review completes — the prediction above is only the AI's preliminary call.") |
| `is_cached` | `bool` | Field(..., description='True if a previous prediction was reused') |
| `original_id` | `Optional[str]` | Field(default=None, description='UUID of the original prediction this was deduplicated from') |
| `similarity_scores` | `Optional[dict[str, float]]` | Field(default=None, description='Cosine similarity scores (text/image/combined) when is_cached=True') |
| `minio_object_key` | `str` | Field(..., description='MinIO object key of the stored image') |
| `image_url` | `Optional[str]` | Field(default=None, description='Pre-signed, time-limited URL for displaying the uploaded image') |
| `model_version` | `str` | Field(..., description='Model version tag') |
| `created_at` | `datetime` | Field(..., description='Prediction record creation timestamp') |

**Class [MultimodalPredictionDetail](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/schemas.py:53>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `prediction_id` | `str` | required / instance-assigned |
| `submission_id` | `str` | required / instance-assigned |
| `headline` | `str \| None` | required / instance-assigned |
| `body_text` | `str \| None` | required / instance-assigned |
| `prediction` | `str` | required / instance-assigned |
| `confidence_fake` | `float` | required / instance-assigned |
| `confidence_real` | `float` | required / instance-assigned |
| `expert_overall_verdict` | `Optional[OverallVerdict]` | None |
| `is_cached` | `bool` | required / instance-assigned |
| `original_id` | `Optional[str]` | None |
| `minio_object_key` | `str` | required / instance-assigned |
| `image_url` | `Optional[str]` | Field(default=None, description='Pre-signed, time-limited URL for displaying the uploaded image') |
| `model_version` | `str` | required / instance-assigned |
| `created_at` | `datetime` | required / instance-assigned |
| `updated_at` | `datetime` | required / instance-assigned |

**Class [PredictionListResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/schemas.py:77>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `items` | `list[MultimodalPredictionDetail]` | required / instance-assigned |
| `total` | `int` | required / instance-assigned |
| `limit` | `int` | required / instance-assigned |
| `offset` | `int` | required / instance-assigned |

### backend/app/features/multimodal/service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/service.py>) · 297 lines

Body+image embeddings, near-duplicate lookup, classifier inference, own submission/result persistence এবং durable upload job।

**Class [MultimodalPredictionService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/service.py:30>)** · inherits `plain class`

- [MultimodalPredictionService.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/service.py:32>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, db: AsyncSession, loader: MultimodalModelLoader, storage: MultimodalStorageService) -> None`

- [MultimodalPredictionService.predict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/service.py:47>) — Multimodal body/image prediction workflow চালায়; service layer-এ storage/dedup/persistence-ও হয়।
  - Signature: `async predict(self, *, headline: str, body_text: str, image_bytes: bytes, original_filename: str, submitter_id: uuid.UUID \| None=None, existing_submission: Submission \| None=None, stored_image_key: str \| None=None) -> MultimodalPredictionResponse`

- [MultimodalPredictionService.accept_upload()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/service.py:138>) — Code-এর দায়িত্ব-বর্ণনা: Store input and queue a job atomically before acknowledging acceptance.
  - Signature: `async accept_upload(self, *, headline: str, body_text: str, image_bytes: bytes, original_filename: str, submitter_id: uuid.UUID \| None) -> Submission`

- [MultimodalPredictionService.process_queued()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/service.py:170>) — Stored multimodal job input process করে; saved result থাকলে duplicate inference এড়ায়, review-ready করে।
  - Signature: `async process_queued(self, submission: Submission, payload: dict) -> None`

- [MultimodalPredictionService._create_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/service.py:188>) — এই method/owner/input-এর নিজস্ব Submission record তৈরি করে।
  - Signature: `async _create_submission(self, *, headline: str, body_text: str, submitter_id: uuid.UUID \| None) -> Submission`
  - Source contract: Every verification method produces a Submission row per the thesis ER model. The AI prediction below is returned to the caller immediately (no long-running search, unlike source-based/photo-card), but the submission still goes to EXPERT_REVIEW rather than FINALIZED — every verification method is reviewed by an expert before its verdict is considered final; see ExpertReviewService's MULTIMODAL branch.

- [MultimodalPredictionService._increment_submitter_total_submissions()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/service.py:214>) — Submitter-এর cached submission counter বাড়ায়।
  - Signature: `async _increment_submitter_total_submissions(self, submitter_id: uuid.UUID) -> None`

- [MultimodalPredictionService.get_prediction()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/service.py:224>) — Prediction ID/submission ID অথবা paginated list দিয়ে multimodal result ফেরত দেয়।
  - Signature: `async get_prediction(self, prediction_id: uuid.UUID) -> MultimodalAnalysis`

- [MultimodalPredictionService.get_prediction_by_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/service.py:227>) — Prediction ID/submission ID অথবা paginated list দিয়ে multimodal result ফেরত দেয়।
  - Signature: `async get_prediction_by_submission(self, submission_id: uuid.UUID) -> MultimodalAnalysis \| None`

- [MultimodalPredictionService.list_predictions()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/service.py:232>) — Prediction ID/submission ID অথবা paginated list দিয়ে multimodal result ফেরত দেয়।
  - Signature: `async list_predictions(self, *, limit: int=20, offset: int=0) -> tuple[list[MultimodalAnalysis], int]`

- [MultimodalPredictionService._find_duplicate()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/service.py:238>) — Candidate embeddings-এর সঙ্গে similarity মিলিয়ে reusable near-duplicate খোঁজে।
  - Signature: `async _find_duplicate(self, *, text_emb, img_emb, combined_emb) -> tuple[MultimodalAnalysis \| None, dict[str, float]]`

- [MultimodalPredictionService._build_response()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/service.py:275>) — Stored model/data-কে নির্দিষ্ট public response schema-তে রূপ দেয়।
  - Signature: `async _build_response(self, *, record: MultimodalAnalysis, is_cached: bool, original_id: str \| None=None, similarity_scores: dict[str, float] \| None=None) -> MultimodalPredictionResponse`

### backend/app/features/multimodal/storage_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/storage_service.py>) · 162 lines

MinIO image upload/read/delete, bucket setup ও expiring image URL।

- [_sanitise_filename()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/storage_service.py:27>) — Storage object path-এর জন্য filename safe form-এ আনে।
  - Signature: `_sanitise_filename(name: str) -> str`

**Class [MultimodalStorageError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/storage_service.py:32>)** · inherits `BanglaFactGuardError`

**Class [MultimodalStorageService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/storage_service.py:36>)** · inherits `plain class`

- [MultimodalStorageService.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/storage_service.py:38>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self) -> None`

- [MultimodalStorageService.ensure_bucket()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/storage_service.py:49>) — MinIO target bucket থাকলে ব্যবহার করে, না থাকলে তৈরি করে।
  - Signature: `async ensure_bucket(self) -> None`

- [MultimodalStorageService._ensure_bucket_sync()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/storage_service.py:63>) — MinIO target bucket থাকলে ব্যবহার করে, না থাকলে তৈরি করে।
  - Signature: `_ensure_bucket_sync(self) -> None`

- [MultimodalStorageService.upload_image()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/storage_service.py:67>) — Image bytes object storage-এ লিখে key/success outcome দেয়।
  - Signature: `async upload_image(self, image_bytes: bytes, original_filename: str, *, submission_id: str \| None=None) -> str`

- [MultimodalStorageService.get_presigned_url()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/storage_service.py:109>) — Stored image দেখার জন্য short-lived signed URL তৈরি/নিয়ে আসে।
  - Signature: `async get_presigned_url(self, object_key: str) -> str`

- [MultimodalStorageService.read_image()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/storage_service.py:130>) — Object key দিয়ে stored image bytes পড়ে; blocking storage operation helper-এ চলে।
  - Signature: `async read_image(self, object_key: str) -> bytes`

- [MultimodalStorageService.read_image.read()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/storage_service.py:131>) — Object key দিয়ে stored image bytes পড়ে; blocking storage operation helper-এ চলে।
  - Signature: `read() -> bytes`

- [MultimodalStorageService.delete_image()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/storage_service.py:140>) — নির্দিষ্ট image object storage থেকে সরায়।
  - Signature: `async delete_image(self, object_key: str) -> None`

- [_infer_content_type()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/storage_service.py:152>) — Image filename/signature থেকে media MIME type নির্ধারণ করে।
  - Signature: `_infer_content_type(filename: str) -> str`

### backend/app/features/nlp/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/__init__.py>) · 1 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/nlp/embedding_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/embedding_service.py>) · 141 lines

SentenceTransformer embedding load/encode/cache/batch/similarity।

**Class [EmbeddingService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/embedding_service.py:36>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `_model` | `SentenceTransformer \| None` | None |
| `_loaded` | `bool` | False |

- [EmbeddingService.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/embedding_service.py:41>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, cache_service: CacheService) -> None`

- [EmbeddingService.load()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/embedding_service.py:44>) — এই service-এর configured model/tokenizer/weights memory-তে load করে।
  - Signature: `async load(self) -> None`

- [EmbeddingService.load._load()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/embedding_service.py:57>) — এই service-এর configured model/tokenizer/weights memory-তে load করে।
  - Signature: `_load() -> SentenceTransformer`

- [EmbeddingService.encode()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/embedding_service.py:72>) — Text বা text batch-এর sentence embedding গণনা করে।
  - Signature: `async encode(self, text: str) -> np.ndarray`

- [EmbeddingService.encode_batch()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/embedding_service.py:105>) — Text বা text batch-এর sentence embedding গণনা করে।
  - Signature: `async encode_batch(self, texts: list[str]) -> list[np.ndarray]`

- [EmbeddingService.compute_similarity()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/embedding_service.py:127>) — দুই vector/text embedding-এর cosine similarity মাপে।
  - Signature: `async compute_similarity(self, text_a: str, text_b: str) -> float`

- [EmbeddingService._write_cache()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/embedding_service.py:136>) — Computed embedding Redis cache-এ serialize করে লেখে।
  - Signature: `async _write_cache(self, key: str, embedding: np.ndarray) -> None`

### backend/app/features/nlp/model_identity.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/model_identity.py>) · 40 lines

Configured embedding name-এর runtime identity ও cache prefix consistent রাখে; legacy model-name mapping আছে।

- [runtime_embedding_model()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/model_identity.py:23>) — Code-এর দায়িত্ব-বর্ণনা: The model to load for a configured ML_EMBEDDING_MODEL_NAME.
  - Signature: `runtime_embedding_model(configured: str) -> str`

- [embedding_identity_tag()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/model_identity.py:31>) — Code-এর দায়িত্ব-বর্ণনা: The embedding-model name used inside persisted claim identities.
  - Signature: `embedding_identity_tag(configured: str) -> str`

- [embedding_cache_prefix()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/model_identity.py:37>) — Code-এর দায়িত্ব-বর্ণনা: Redis key prefix for cached vectors of the runtime model.
  - Signature: `embedding_cache_prefix(configured: str, base: str) -> str`

### backend/app/features/nlp/ner_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/ner_service.py>) · 192 lines

Bangla NER pipeline, label/smoke audit এবং whole-text chunked mentions extraction।

- [_base_type()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/ner_service.py:65>) — Code-এর দায়িত্ব-বর্ণনা: B-PER / I-PER / PER -> PER; anything else (O, LABEL_3) -> None.
  - Signature: `_base_type(label: str) -> str \| None`

**Class [NERResult](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/ner_service.py:74>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `available` | `bool` | required / instance-assigned |
| `mentions` | `list[EntityMention]` | field(default_factory=list) |
| `error` | `str \| None` | None |
| `truncated` | `bool` | False |

**Class [NERService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/ner_service.py:81>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `_loaded` | `bool` | False |
| `_labels_ok` | `bool` | False |
| `_smoke_ok` | `bool` | False |
| `_audit` | `dict` | {} |

- [NERService.usable()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/ner_service.py:91>) — NER label/smoke audit অনুযায়ী model ব্যবহারযোগ্য কি না জানায়।
  - Signature: `usable(self) -> bool`

- [NERService.audit()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/ner_service.py:100>) — Model loading/label validation-এর diagnostic তথ্য দেয়।
  - Signature: `audit(self) -> dict`

- [NERService.load()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/ner_service.py:103>) — এই service-এর configured model/tokenizer/weights memory-তে load করে।
  - Signature: `async load(self) -> None`

- [NERService._run_audit()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/ner_service.py:124>) — NER label mapping ও Bangla smoke example দিয়ে usable entity output যাচাই করে।
  - Signature: `async _run_audit(self) -> None`

- [NERService._tag_chunks()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/ner_service.py:160>) — NER pipeline দিয়ে chunk-wise typed entity mentions নিয়ে normalize/deduplicate করে।
  - Signature: `async _tag_chunks(self, chunks: list[str]) -> NERResult`

- [NERService.extract_mentions()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/ner_service.py:183>) — Code-এর দায়িত্ব-বর্ণনা: Typed entity mentions across the WHOLE text (chunked, not truncated).
  - Signature: `async extract_mentions(self, text: str) -> NERResult`

### backend/app/features/nlp/nli_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/nli_service.py>) · 201 lines

Multilingual NLI pipeline load/label audit; premise-hypothesis scores parse করে।

**Class [NLIService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/nli_service.py:70>)** · inherits `plain class`

দায়িত্ব/contract: Singleton NLI service backed by DeBERTa-v3 cross-encoder. Usage:: service = NLIService() await service.load() result = await service.predict(premise, hypothesis) # → NLIScoresSchema(entailment=0.87, contradiction=0.05, neutral=0.08)

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `_loaded` | `bool` | False |
| `_labels_ok` | `bool` | False |
| `_audit` | `dict` | {} |

- [NLIService.audit()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/nli_service.py:92>) — Model loading/label validation-এর diagnostic তথ্য দেয়।
  - Signature: `audit(self) -> dict`

- [NLIService.load()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/nli_service.py:95>) — এই service-এর configured model/tokenizer/weights memory-তে load করে।
  - Signature: `async load(self) -> None`
  - Source contract: Load the DeBERTa NLI pipeline (called once at startup).

- [NLIService._audit_labels()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/nli_service.py:117>) — NLI label mapping entailment/neutral/contradiction হিসেবে শনাক্তযোগ্য কি না পরীক্ষা করে।
  - Signature: `_audit_labels(self) -> None`

- [NLIService.predict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/nli_service.py:140>) — Multimodal body/image prediction workflow চালায়; service layer-এ storage/dedup/persistence-ও হয়।
  - Signature: `async predict(self, premise: str, hypothesis: str) -> NLIScoresSchema \| None`
  - Source contract: Run NLI inference for a (premise, hypothesis) pair. Args: premise: The retrieved article text (or truncated version). hypothesis: The claim headline (what we are testing). Returns: NLIScoresSchema with entailment/contradiction/neutral probabilities, or None if the model is not loaded or inference fails.

- [NLIService._parse_output()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/nlp/nli_service.py:174>) — Code-এর দায়িত্ব-বর্ণনা: Parse DeBERTa pipeline output into NLIScoresSchema. The pipeline returns a list of dicts: [{"label": "ENTAILMENT", "score": 0.87}, ...] Args: raw_output: Raw HuggingFace pipeline output. Returns: NLIScoresSchema or None if parsing fails.
  - Signature: `_parse_output(raw_output: list[dict]) -> NLIScoresSchema \| None`

### backend/app/features/notifications/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/__init__.py>) · 1 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/notifications/delivery.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/delivery.py>) · 127 lines

Saved results reconcile করে delivery tracking তৈরি; final email পাঠায়/retry করে; worker loop।

- [reconcile()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/delivery.py:30>) — Saved preliminary/final results-এর missing personal notification/delivery records তৈরি করে।
  - Signature: `async reconcile(session, *, limit: int=100) -> int`

- [deliver_email()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/delivery.py:68>) — Code-এর দায়িত্ব-বর্ণনা: Hold a row lock during delivery so multiple workers cannot send together.
  - Signature: `async deliver_email(session, mailer: EmailService) -> bool`

**Class [ResultDeliveryWorker](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/delivery.py:95>)** · inherits `plain class`

- [ResultDeliveryWorker.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/delivery.py:96>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, session_factory=AsyncSessionLocal)`

- [ResultDeliveryWorker.start()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/delivery.py:100>) — Background worker-এর asynchronous loop task শুরু করে।
  - Signature: `start(self)`

- [ResultDeliveryWorker.stop()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/delivery.py:103>) — Worker/task cancellation ও shutdown অপেক্ষা সম্পন্ন করে।
  - Signature: `async stop(self)`

- [ResultDeliveryWorker.run()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/delivery.py:111>) — এই worker-এর recurring processing/poll/sweep loop চালায়।
  - Signature: `async run(self)`

### backend/app/features/notifications/models.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/models.py>) · 38 lines

Feature `notifications`। SQLAlchemy ORM entities: নিচে exact table, fields ও foreign-key/constraint declarations দেওয়া আছে।

**Class [Notification](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/models.py:9>)** · inherits `UUIDMixin, TimestampMixin, Base` · table `notifications`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `user_id` | `Mapped[uuid.UUID]` | mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True) |
| `title` | `Mapped[str]` | mapped_column(String(255), nullable=False) |
| `body` | `Mapped[str]` | mapped_column(Text, nullable=False) |
| `notification_type` | `Mapped[str]` | mapped_column(String(50), nullable=False, index=True) |
| `link_url` | `Mapped[str \| None]` | mapped_column(String(512), nullable=True, comment='Deep-link to the relevant result page') |
| `is_read` | `Mapped[bool]` | mapped_column(Boolean, nullable=False, default=False, index=True) |

**Class [ResultDelivery](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/models.py:30>)** · inherits `TimestampMixin, Base` · table `result_deliveries`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `Mapped[uuid.UUID]` | mapped_column(UUID(as_uuid=True), ForeignKey('submissions.id', ondelete='CASCADE'), primary_key=True) |
| `stage` | `Mapped[str]` | mapped_column(String(20), primary_key=True) |
| `verdict` | `Mapped[str \| None]` | mapped_column(String(20), nullable=True) |
| `email_status` | `Mapped[str]` | mapped_column(String(20), nullable=False, default='not_applicable', index=True) |
| `email_attempts` | `Mapped[int]` | mapped_column(Integer, nullable=False, default=0) |
| `next_attempt_at` | `Mapped[datetime \| None]` | mapped_column(DateTime(timezone=True), nullable=True) |
| `sent_at` | `Mapped[datetime \| None]` | mapped_column(DateTime(timezone=True), nullable=True) |

### backend/app/features/notifications/repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/repository.py>) · 49 lines

Feature `notifications`। এই feature-এর database queries ও persistence operations; যেখানে BaseRepository inherit করেছে সেখানে common CRUD inherited।

**Class [NotificationRepository](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/repository.py:13>)** · inherits `plain class`

- [NotificationRepository.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/repository.py:14>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, session: AsyncSession) -> None`

- [NotificationRepository.list_for_user()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/repository.py:17>) — শুধু current user-এর notifications filter/pagination অনুযায়ী আনে।
  - Signature: `async list_for_user(self, user_id: uuid.UUID, *, limit: int, offset: int, unread_only: bool) -> list[Notification]`

- [NotificationRepository.count_unread()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/repository.py:26>) — Current user-এর unread notification count দেয়।
  - Signature: `async count_unread(self, user_id: uuid.UUID) -> int`

- [NotificationRepository.mark_read()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/repository.py:34>) — একটি/সব নিজের notifications read করে; অন্য user-এর notification পরিবর্তন করে না।
  - Signature: `async mark_read(self, user_id: uuid.UUID, notification_id: uuid.UUID) -> None`
  - Source contract: No-op for a notification that belongs to someone else.

- [NotificationRepository.mark_all_read()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/repository.py:43>) — একটি/সব নিজের notifications read করে; অন্য user-এর notification পরিবর্তন করে না।
  - Signature: `async mark_all_read(self, user_id: uuid.UUID) -> None`

### backend/app/features/notifications/router.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/router.py>) · 76 lines

Feature `notifications`। এই feature-এর HTTP paths, request/response schema, dependencies ও permission guard define করে; handler সংশ্লিষ্ট service/repository-তে কাজ পাঠায়।

- [_repo()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/router.py:17>) — বর্তমান database session দিয়ে উপযুক্ত repository তৈরি করে।
  - Signature: `_repo(session: AsyncSession=Depends(get_async_session)) -> NotificationRepository`

- [list_notifications()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/router.py:22>) — শুধু current user-এর notifications filter/pagination অনুযায়ী আনে।
  - Signature: `async list_notifications(limit: int=Query(default=30, ge=1, le=100), offset: int=Query(default=0, ge=0), unread_only: bool=Query(default=False), current_user: User=Depends(get_current_user), repo: NotificationRepository=Depends(_repo)) -> list[NotificationResponse]`

- [get_unread_count()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/router.py:47>) — Current user-এর unread notification count দেয়।
  - Signature: `async get_unread_count(current_user: User=Depends(get_current_user), repo: NotificationRepository=Depends(_repo)) -> UnreadCountResponse`

- [mark_read()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/router.py:59>) — একটি/সব নিজের notifications read করে; অন্য user-এর notification পরিবর্তন করে না।
  - Signature: `async mark_read(notification_id: uuid.UUID, current_user: User=Depends(get_current_user), repo: NotificationRepository=Depends(_repo)) -> None`

- [mark_all_read()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/router.py:72>) — একটি/সব নিজের notifications read করে; অন্য user-এর notification পরিবর্তন করে না।
  - Signature: `async mark_all_read(current_user: User=Depends(get_current_user), repo: NotificationRepository=Depends(_repo)) -> None`

### backend/app/features/notifications/schemas.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/schemas.py>) · 21 lines

Feature `notifications`। এই feature-এর Pydantic request/response structures ও validation define করে; এগুলো database table নয়।

**Class [NotificationResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/schemas.py:8>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `id` | `str` | required / instance-assigned |
| `title` | `str` | required / instance-assigned |
| `body` | `str` | required / instance-assigned |
| `notification_type` | `str` | required / instance-assigned |
| `link_url` | `str \| None` | required / instance-assigned |
| `is_read` | `bool` | required / instance-assigned |
| `created_at` | `datetime` | required / instance-assigned |

**Class [UnreadCountResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/schemas.py:20>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `unread_count` | `int` | required / instance-assigned |

### backend/app/features/notifications/service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/service.py>) · 102 lines

Consistent preliminary/final notification text এবং duplicate-resistant personal notification insert।

- [preliminary_notification_text()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/service.py:23>) — Headline preview দিয়ে consistent personal result message তৈরি করে।
  - Signature: `preliminary_notification_text(headline: str \| None) -> tuple[str, str]`

- [final_notification_text()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/service.py:27>) — Headline preview দিয়ে consistent personal result message তৈরি করে।
  - Signature: `final_notification_text(headline: str \| None, verdict_label: str \| None) -> tuple[str, str]`

- [notify_preliminary_result()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/service.py:32>) — Code-এর দায়িত্ব-বর্ণনা: The "preliminary result ready" notification for a submission (fresh, reused, photo-card or multimodal alike). Same identity and wording as every other VERIFICATION_COMPLETE notification, so it is written once.
  - Signature: `async notify_preliminary_result(session: AsyncSession, *, user_id: uuid.UUID, submission_id: uuid.UUID, headline: str \| None) -> bool`

- [notify_once()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/notifications/service.py:54>) — Code-এর দায়িত্ব-বর্ণনা: Insert the notification unless an identical one exists. Returns True when a new row was written. Never raises. Every preliminary-result notification (text, photo card, multimodal, reused) uses one wording: the claim headline's first five words, with "..." only when the headline is longer. `headline` is the claim headline.
  - Signature: `async notify_once(session: AsyncSession, *, user_id: uuid.UUID, notification_type: str, link_url: str, title: str, body: str, headline: str \| None=None) -> bool`

### backend/app/features/photocard/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/__init__.py>) · 0 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/photocard/card_date.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/card_date.py>) · 89 lines

Photo card-এ printed বাংলা/English date parse; incomplete/ambiguous date ফেরত দেয় না।

- [_safe()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/card_date.py:57>) — Date components দিয়ে valid calendar date বানায়; invalid হলে None দেয়।
  - Signature: `_safe(year: int, month: int, day: int) -> date \| None`

- [parse_card_date()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/card_date.py:64>) — Code-এর দায়িত্ব-বর্ণনা: The single calendar date in ``raw``, or None when there is none, it is incomplete, or the string is ambiguous.
  - Signature: `parse_card_date(raw: str \| None) -> date \| None`

### backend/app/features/photocard/claim_extraction.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/claim_extraction.py>) · 201 lines

Active source catalogue দিয়ে Gemini response থেকে usable headline, source ও date বানায়; failure ও optional verified-source fallback ঠিক করে।

**Class [CardExtraction](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/claim_extraction.py:66>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `status` | `str` | required / instance-assigned |
| `headline` | `str \| None` | None |
| `source` | `VerifiedSource \| None` | None |
| `source_reason` | `str \| None` | None |
| `raw_source_text` | `str \| None` | None |
| `published_date` | `date \| None` | None |
| `failure_code` | `str \| None` | None |
| `attempts` | `int` | 0 |
| `model_version` | `str \| None` | None |
| `details` | `dict` | field(default_factory=dict) |
| `timings_ms` | `dict[str, int]` | field(default_factory=dict) |

- [CardExtraction.succeeded()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/claim_extraction.py:82>) — Extraction status successful কি না boolean দেয়।
  - Signature: `succeeded(self) -> bool`

- [CardExtraction.failure_message()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/claim_extraction.py:86>) — Extraction failure type থেকে user-readable explanation দেয়।
  - Signature: `failure_message(self) -> str \| None`

- [_usable_headline()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/claim_extraction.py:96>) — Extracted text যথেষ্ট দীর্ঘ ও meaningful letters-সহ usable headline কি না যাচাই করে।
  - Signature: `_usable_headline(raw: str \| None) -> str \| None`

**Class [PhotocardClaimExtractor](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/claim_extraction.py:105>)** · inherits `plain class`

- [PhotocardClaimExtractor.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/claim_extraction.py:107>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, *, source_repo: SourceRepository, http_client: httpx.AsyncClient, sleep: Callable[[float], Awaitable[None]]=asyncio.sleep) -> None`

- [PhotocardClaimExtractor.extract()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/claim_extraction.py:118>) — Active source catalogue দিয়ে Gemini extraction চালিয়ে validated CardExtraction result বানায়।
  - Signature: `async extract(self, image_bytes: bytes) -> CardExtraction`

### backend/app/features/photocard/dependencies.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/dependencies.py>) · 73 lines

Photocard service-এর storage/repositories/shared model dependencies wiring।

- [get_photocard_storage()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/dependencies.py:34>) — Application state থেকে shared client/model/storage service সরবরাহ করে।
  - Signature: `get_photocard_storage(request: Request) -> PhotoCardStorageService`

- [get_extraction_repo()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/dependencies.py:42>) — বর্তমান database session দিয়ে উপযুক্ত repository তৈরি করে।
  - Signature: `async get_extraction_repo(session: AsyncSession=Depends(get_async_session)) -> PhotocardExtractionRepository`

- [get_photocard_service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/dependencies.py:48>) — FastAPI dependency হিসেবে এই feature-এর service প্রয়োজনীয় repository/shared resources দিয়ে তৈরি করে।
  - Signature: `async get_photocard_service(storage: PhotoCardStorageService=Depends(get_photocard_storage), submission_repo: SubmissionRepository=Depends(get_submission_repo), extraction_repo: PhotocardExtractionRepository=Depends(get_extraction_repo), result_repo: ResultRepository=Depends(get_result_repo), article_repo: RetrievedArticleRepository=Depends(get_article_repo), source_repo: SourceRepository=Depends(get_source_repo), cache_service: CacheService=Depends(get_cache_service), embedding_service: EmbeddingService=Depends(get_embedding_service), ner_service: NERService=Depends(get_ner_service), nli_service: NLIService=Depends(get_nli_service), http_client: httpx.AsyncClient=Depends(get_http_client)) -> PhotoCardService`

### backend/app/features/photocard/gemini_image_extractor.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_image_extractor.py>) · 259 lines

Original image দিয়ে Gemini REST call, batched retries, response JSON validation ও attempt accounting।

**Class [GeminiAttempt](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_image_extractor.py:72>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `number` | `int` | required / instance-assigned |
| `batch` | `int` | required / instance-assigned |
| `outcome` | `str` | required / instance-assigned |
| `detail` | `str \| None` | None |
| `status_code` | `int \| None` | None |
| `duration_ms` | `int` | 0 |
| `key` | `int \| None` | None |

- [GeminiAttempt.to_dict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_image_extractor.py:81>) — এই result/value object-এর serializable dictionary representation দেয়।
  - Signature: `to_dict(self) -> dict`

**Class [GeminiExtractionOutcome](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_image_extractor.py:89>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `model` | `str \| None` | required / instance-assigned |
| `fields` | `GeminiPhotocardFields \| None` | None |
| `attempts` | `list[GeminiAttempt]` | field(default_factory=list) |
| `skipped_reason` | `str \| None` | None |

- [GeminiExtractionOutcome.succeeded()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_image_extractor.py:96>) — Extraction status successful কি না boolean দেয়।
  - Signature: `succeeded(self) -> bool`

**Class [_AttemptFailed](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_image_extractor.py:100>)** · inherits `Exception`

- [_AttemptFailed.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_image_extractor.py:101>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, outcome: str, detail: str, status_code: int \| None=None, *, permanent: bool=False, limit_seconds: float \| None=None)`

- [detect_mime_type()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_image_extractor.py:108>) — Image filename/signature থেকে media MIME type নির্ধারণ করে।
  - Signature: `detect_mime_type(image_bytes: bytes) -> str`

- [_response_text()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_image_extractor.py:118>) — Code-এর দায়িত্ব-বর্ণনা: The JSON text of the first candidate, skipping 'thought' parts.
  - Signature: `_response_text(body: dict) -> str`

- [extract_with_gemini()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_image_extractor.py:132>) — Code-এর দায়িত্ব-বর্ণনা: Up to ``settings.max_requests`` (<= 9) requests in batches. Never raises.
  - Signature: `async extract_with_gemini(image_bytes: bytes, *, sources: list[SourceOption], http_client: httpx.AsyncClient, settings: GeminiSettings, sleep: Callable[[float], Awaitable[None]]=asyncio.sleep) -> GeminiExtractionOutcome`

- [_attempt()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_image_extractor.py:214>) — একটি Gemini extraction HTTP request করে response validate ও failure classify করে।
  - Signature: `async _attempt(url: str, payload: dict, *, http_client: httpx.AsyncClient, settings: GeminiSettings, allowed: set[str], api_key: str) -> GeminiPhotocardFields`

### backend/app/features/photocard/gemini_key_pool.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_key_pool.py>) · 89 lines

Process-wide key rotation, quota/rate-limit cooldown ও shared key-pool registry।

- [limit_info()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_key_pool.py:17>) — Code-এর দায়িত্ব-বর্ণনা: (is a per-day quota, seconds until the key may be used again) for a 429.
  - Signature: `limit_info(response: httpx.Response) -> tuple[bool, float]`

**Class [GeminiKeyPool](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_key_pool.py:41>)** · inherits `plain class`

দায়িত্ব/contract: Process-wide rotation over the configured keys. Shared by every card, so a key that ran out of its limit is skipped by later cards too until its limit resets. Keys themselves are never logged - only their number.

- [GeminiKeyPool.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_key_pool.py:46>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, keys: list[str], clock: Callable[[], float]=time.monotonic) -> None`

- [GeminiKeyPool.acquire()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_key_pool.py:52>) — Code-এর দায়িত্ব-বর্ণনা: Index of the next usable key (cycling from the last one used), or None when every key is blocked for longer than is worth waiting.
  - Signature: `acquire(self) -> int \| None`

- [GeminiKeyPool.block()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_key_pool.py:68>) — Rate-limited API key-এর cooldown timestamp বসায়।
  - Signature: `block(self, index: int, seconds: float) -> None`

- [GeminiKeyPool.has_free_key()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_key_pool.py:72>) — এখন ব্যবহারযোগ্য কোনো configured API key আছে কি না পরীক্ষা করে।
  - Signature: `has_free_key(self) -> bool`

- [key_pool()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_key_pool.py:80>) — Configured keys-এর জন্য shared rotation/cooldown pool দেয়।
  - Signature: `key_pool(keys: list[str]) -> GeminiKeyPool`

- [reset_key_pools()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_key_pool.py:87>) — Code-এর দায়িত্ব-বর্ণনা: Forget every blocked key (tests, or after a quota upgrade).
  - Signature: `reset_key_pools() -> None`

### backend/app/features/photocard/gemini_prompt.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_prompt.py>) · 146 lines

Gemini extraction prompt, structured JSON response schema এবং source catalogue DTO।

**Class [FieldStatus](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_prompt.py:13>)** · inherits `str, Enum`

**Class [SourceStatus](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_prompt.py:19>)** · inherits `str, Enum`

**Class [SourceOption](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_prompt.py:27>)** · inherits `plain class`

দায়িত্ব/contract: One active verified source as offered to Gemini.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `canonical_name` | `str` | required / instance-assigned |
| `display_name` | `str` | required / instance-assigned |
| `display_name_en` | `str \| None` | None |
| `aliases` | `tuple[str, ...]` | () |

- [SourceOption.names()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_prompt.py:35>) — একটি source-এর canonical/display/alias names একত্র করে।
  - Signature: `names(self) -> list[str]`

**Class [GeminiPhotocardFields](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_prompt.py:43>)** · inherits `BaseModel`

দায়িত্ব/contract: The validated structured response. Values are raw transcriptions; ``source`` is a canonical id from the offered catalogue (or null).

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `headline` | `str \| None` | None |
| `headline_status` | `FieldStatus` | required / instance-assigned |
| `source` | `str \| None` | None |
| `source_status` | `SourceStatus` | required / instance-assigned |
| `source_evidence` | `str \| None` | None |
| `date` | `str \| None` | None |
| `date_status` | `FieldStatus` | required / instance-assigned |

- [GeminiPhotocardFields.present()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_prompt.py:57>) — Code-এর দায়িত্ব-বর্ণনা: The raw headline/date when the model marked it PRESENT and non-blank.
  - Signature: `present(self, name: str) -> str \| None`

- [GeminiPhotocardFields.identified_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_prompt.py:64>) — Validated model response-এ source শনাক্ত থাকলে তার canonical identity দেয়।
  - Signature: `identified_source(self) -> str \| None`

- [build_user_prompt()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_prompt.py:111>) — Image reading নির্দেশনা ও active source catalogue দিয়ে Gemini user prompt বানায়।
  - Signature: `build_user_prompt(sources: list[SourceOption]) -> str`

- [build_response_schema()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/gemini_prompt.py:126>) — Gemini output-এর structured JSON schema তৈরি করে।
  - Signature: `build_response_schema(sources: list[SourceOption]) -> dict`

### backend/app/features/photocard/router.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/router.py>) · 124 lines

Feature `photocard`। এই feature-এর HTTP paths, request/response schema, dependencies ও permission guard define করে; handler সংশ্লিষ্ট service/repository-তে কাজ পাঠায়।

- [_read_validated_image()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/router.py:28>) — Upload-এর declared/actual image type ও maximum size validate করে bytes নেয়।
  - Signature: `async _read_validated_image(image: UploadFile) -> bytes`

- [verify_photocard_async()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/router.py:77>) — Image validate/store/enqueue করে HTTP 202 acknowledgement ফেরত দেয়।
  - Signature: `async verify_photocard_async(http_request: Request, image: UploadFile=File(..., description='Photo card or screenshot (JPEG/PNG/WebP/GIF, max 10 MB)'), service: PhotoCardService=Depends(get_photocard_service), current_user: User \| None=Depends(get_current_user_optional)) -> PhotoCardAcceptedResponse`

- [get_photocard_result()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/router.py:111>) — Access check করে stored/pending/failed photocard report ফেরত দেয়।
  - Signature: `async get_photocard_result(submission_id: uuid.UUID, service: PhotoCardService=Depends(get_photocard_service), current_user: User \| None=Depends(get_current_user_optional)) -> PhotoCardResultResponse`

### backend/app/features/photocard/schemas.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/schemas.py>) · 71 lines

Feature `photocard`। এই feature-এর Pydantic request/response structures ও validation define করে; এগুলো database table নয়।

**Class [PhotoCardAcceptedResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/schemas.py:12>)** · inherits `BaseModel`

দায়িত্ব/contract: HTTP 202 acknowledgement. The card is stored and the job is durable; extraction and verification continue on the server whether or not the client stays on the page. Fetch current state by `submission_id`.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `uuid.UUID` | required / instance-assigned |
| `status` | `SubmissionStatus` | required / instance-assigned |
| `phase` | `str \| None` | Field(default=None, description='QUEUED \| EXTRACTING \| VERIFYING \| DONE \| FAILED') |
| `message` | `str` | required / instance-assigned |
| `queued_at` | `datetime` | required / instance-assigned |

**Class [PhotoCardResultResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/schemas.py:24>)** · inherits `BaseModel`

দায়িত্ব/contract: Stored photo-card report, retrieved by submission ID. Valid in every state: a pending row has no headline/verification yet, a failed one has a failure_reason, a completed one has the saved verification. The headline, claimed outlet and claimed date are what Gemini read from the card - there is no separate user-entered source or date.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `uuid.UUID` | required / instance-assigned |
| `status` | `SubmissionStatus` | required / instance-assigned |
| `phase` | `str \| None` | None |
| `failure_reason` | `str \| None` | None |
| `claim_scope` | `ClaimScope` | ClaimScope.HEADLINE_ONLY |
| `headline` | `str \| None` | Field(default=None, description='The headline exactly as printed on the card; the only text verified.') |
| `claimed_source_text` | `str \| None` | Field(default=None, description='Canonical id of the active verified source identified on the card - the verification target.') |
| `claimed_source_name` | `str \| None` | Field(default=None, description='Display name of that source.') |
| `detected_source_text` | `str \| None` | Field(default=None, description='Outlet text visible on the card as read by the extractor. Provenance only: when it is not an active verified source the card is checked against the verified sources.') |
| `published_date` | `date \| None` | Field(default=None, description='Publication date printed on the card - the claimed date. Null when the card shows no complete date.') |
| `extraction_status` | `str \| None` | Field(default=None, description='PENDING \| SUCCEEDED \| API_FAILED \| INVALID_CONTENT') |
| `extraction_attempts` | `int \| None` | Field(default=None, description='Gemini requests made (first request included, at most 9).') |
| `extraction_model_version` | `str \| None` | None |
| `extraction_failures` | `list[str]` | Field(default_factory=list, description='Short, user-presentable reasons for failed reading attempts.') |
| `image_url` | `str \| None` | None |
| `verification` | `VerificationResponse \| None` | None |
| `created_at` | `datetime` | required / instance-assigned |

### backend/app/features/photocard/service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/service.py>) · 389 lines

Fast image acceptance, durable storage/job, Gemini extraction, shared verification pipeline এবং stored report presentation।

**Class [PhotoCardService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/service.py:64>)** · inherits `plain class`

দায়িত্ব/contract: Unattended extraction and verification for photo-card submissions.

- [PhotoCardService.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/service.py:67>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, *, storage: PhotoCardStorageService, submission_repo: SubmissionRepository, extraction_repo: PhotocardExtractionRepository, result_repo: ResultRepository, article_repo: RetrievedArticleRepository, source_repo: SourceRepository, cache_service: CacheService, embedding_service: EmbeddingService, ner_service: NERService, nli_service: NLIService, http_client: httpx.AsyncClient) -> None`

- [PhotoCardService.accept_upload()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/service.py:97>) — Code-এর দায়িত্ব-বর্ণনা: Durably store the image and persist the submission + job. The caller acknowledges (HTTP 202) only after this returns.
  - Signature: `async accept_upload(self, *, image_bytes: bytes, original_filename: str, submitter_id: uuid.UUID \| None=None, enqueue: bool=True) -> Submission`

- [PhotoCardService.accepted_response()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/service.py:146>) — Accepted submission-এর ID/state/message দিয়ে acknowledgement schema বানায়।
  - Signature: `accepted_response(self, submission: Submission) -> PhotoCardAcceptedResponse`

- [PhotoCardService.process_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/service.py:165>) — Code-এর দায়িত্ব-বর্ণনা: Extraction -> shared pipeline for a stored card. Raises ``PermanentJobError`` for failures retrying cannot fix (including an exhausted Gemini budget: the job is never re-run, so a card never costs more than 9 Gemini requests). Any other exception is retryable and is handled by the worker.
  - Signature: `async process_submission(self, submission_id: uuid.UUID) -> None`

- [PhotoCardService._store_extraction()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/service.py:289>) — Extraction status/model/attempt/details ORM record-এ বসায়।
  - Signature: `_store_extraction(record: PhotocardExtraction, extraction: CardExtraction) -> None`

- [PhotoCardService._build_stages()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/service.py:296>) — প্রয়োজনীয় dependencies দিয়ে ordered pipeline stage instances তৈরি করে।
  - Signature: `_build_stages(self) -> list`
  - Source contract: Shared retrieval with the photo-card-only content comparison policy.

- [PhotoCardService.get_result()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/service.py:312>) — Saved structured/photo result reconstruct করে ফেরত দেয়; feature-specific response shape ব্যবহার হয়।
  - Signature: `async get_result(self, submission_id: uuid.UUID) -> PhotoCardResultResponse \| None`
  - Source contract: Current state by submission id: a pending/processing/failed card renders from the submission row; a completed one adds the saved verification (identical to what was shown right after it finished).

- [PhotoCardService._image_url()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/service.py:354>) — Stored image দেখার জন্য short-lived signed URL তৈরি/নিয়ে আসে।
  - Signature: `async _image_url(self, record: PhotocardExtraction \| None) -> str \| None`

- [extraction_failures()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/service.py:370>) — Code-এর দায়িত্ব-বর্ণনা: Short, user-presentable reasons for failed reading attempts.
  - Signature: `extraction_failures(details: dict \| None) -> list[str]`

- [_detected_source_text()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/service.py:385>) — Code-এর দায়িত্ব-বর্ণনা: The outlet text Gemini saw on the card (provenance only).
  - Signature: `_detected_source_text(details: dict \| None) -> str \| None`

### backend/app/features/photocard/storage_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/storage_service.py>) · 146 lines

Photocard image MinIO-তে রাখা ও worker-এর জন্য পুনরায় পড়া; preview URL।

**Class [PhotoCardStorageService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/storage_service.py:45>)** · inherits `plain class`

দায়িত্ব/contract: Stores photo-card images and issues short-lived preview URLs.

- [PhotoCardStorageService.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/storage_service.py:48>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self) -> None`

- [PhotoCardStorageService.ensure_bucket()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/storage_service.py:59>) — MinIO target bucket থাকলে ব্যবহার করে, না থাকলে তৈরি করে।
  - Signature: `async ensure_bucket(self) -> None`

- [PhotoCardStorageService._ensure_bucket_sync()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/storage_service.py:64>) — MinIO target bucket থাকলে ব্যবহার করে, না থাকলে তৈরি করে।
  - Signature: `_ensure_bucket_sync(self) -> None`

- [PhotoCardStorageService.build_object_key()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/storage_service.py:68>) — Submission identity ও filename দিয়ে image storage key বানায়।
  - Signature: `build_object_key(self, submission_id: uuid.UUID, filename: str) -> str`

- [PhotoCardStorageService.upload()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/storage_service.py:72>) — Image bytes object storage-এ লিখে key/success outcome দেয়।
  - Signature: `async upload(self, image_bytes: bytes, object_key: str) -> bool`
  - Source contract: Upload the card. Returns ``False`` when storage is unavailable.

- [PhotoCardStorageService.download()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/storage_service.py:101>) — Object key দিয়ে stored image bytes পড়ে; blocking storage operation helper-এ চলে।
  - Signature: `async download(self, object_key: str) -> bytes \| None`
  - Source contract: Fetch the stored card. The background job reads the image from here rather than from the (long gone) upload request.

- [PhotoCardStorageService.download._get()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/storage_service.py:106>) — Object key দিয়ে stored image bytes পড়ে; blocking storage operation helper-এ চলে।
  - Signature: `_get() -> bytes`

- [PhotoCardStorageService.get_presigned_url()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/storage_service.py:120>) — Stored image দেখার জন্য short-lived signed URL তৈরি/নিয়ে আসে।
  - Signature: `async get_presigned_url(self, object_key: str) -> str \| None`
  - Source contract: Short-lived preview URL, or ``None`` when it cannot be issued.

- [_infer_content_type()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/storage_service.py:141>) — Image filename/signature থেকে media MIME type নির্ধারণ করে।
  - Signature: `_infer_content_type(name: str) -> str`

### backend/app/features/photocard/verification_stages.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/verification_stages.py>) · 58 lines

Photo-specific hash/normalizer দিয়ে shared 13-stage list বানায়; HEADLINE_ONLY scope বজায় থাকে।

- [compute_photocard_hash()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/verification_stages.py:20>) — Code-এর দায়িত্ব-বর্ণনা: Never reuse a result computed under another pipeline version, headline comparison method or model set.
  - Signature: `compute_photocard_hash(headline: str, source: str, *, published_date=None) -> str`

**Class [PhotocardNormalizerStage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/verification_stages.py:32>)** · inherits `InputNormalizerStage`

- [PhotocardNormalizerStage.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/verification_stages.py:33>) — Photocard input normalize করে photo-specific claim identity বসায়।
  - Signature: `async execute(self, context)`

- [build_photocard_stages()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/photocard/verification_stages.py:49>) — Code-এর দায়িত্ব-বর্ণনা: The shared stages with the photo-card normaliser. Dispatch is explicit from PhotoCardService, never inferred from HEADLINE_ONLY (which also describes text claims submitted without a body).
  - Signature: `build_photocard_stages(**kwargs)`

### backend/app/features/search/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/__init__.py>) · 1 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/search/internal_site_client.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/internal_site_client.py>) · 204 lines

Publisher-এর own search page query করে valid article links/title সংগ্রহ; navigation-only ফল বাদ দেয়।

- [_build_keyword_query()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/internal_site_client.py:35>) — Code-এর দায়িত্ব-বর্ণনা: Keep the complete headline/keyword query for the outlet's own search.
  - Signature: `_build_keyword_query(raw: str) -> str`

**Class [InternalSiteSearchError](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/internal_site_client.py:41>)** · inherits `Exception`

দায়িত্ব/contract: The outlet's own search page could not be queried.

**Class [InternalSiteSearchClient](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/internal_site_client.py:45>)** · inherits `plain class`

- [InternalSiteSearchClient.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/internal_site_client.py:47>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, async_client: httpx.AsyncClient) -> None`

- [InternalSiteSearchClient.search_entries()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/internal_site_client.py:50>) — এই provider-এর search query থেকে article URL ও title entries সংগ্রহ করে।
  - Signature: `async search_entries(self, query: str, domain: Optional[str]=None, published_date: Optional[date]=None, source_config: Optional[dict]=None) -> list[tuple[str, str]]`

- [_visible_text()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/internal_site_client.py:151>) — Code-এর দায়িত্ব-বর্ণনা: The element's text with the whitespace the page actually has, collapsed. `get_text(strip=True)` strips every text node separately and joins them with nothing, so a kicker span and the headline after it ("<span>মন্ত্রিসভার বৈঠক</span> গ্রাম সরকার...") become one glued word ("বৈঠকগ্রাম"). No space is inserted where the page has none.
  - Signature: `_visible_text(element) -> str`

- [_query_tokens()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/internal_site_client.py:162>) — Code-এর দায়িত্ব-বর্ণনা: Content words from the query, long enough to be worth matching on.
  - Signature: `_query_tokens(query: str) -> set[str]`

- [_drop_if_query_independent()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/internal_site_client.py:167>) — Code-এর দায়িত্ব-বর্ণনা: Discard a result set that is really just the page's own chrome. Several Bangla outlets serve a `/search` page whose results are filled in client-side (a Google CSE embed, or an XHR). A plain GET still returns a full page of "latest news" links, and those links match the source's `article_url_patterns` perfectly — so they were being accepted as search hits. Because this client is the highest-priority provider, that quietly pushed a handful of unrelated articles to the front of the evidence budget and crowded out the real match from the other providers. A genuine result set mentions the query somewhere; page chrome does not. So require at least one result whose link text shares a content word with the query, and keep only the results that do. If nothing matches, the response carried no search results at all and is dropped entirely.
  - Signature: `_drop_if_query_independent(results: list[tuple[str, str]], kw_query: str, domain: str \| None) -> list[tuple[str, str]]`

### backend/app/features/search/pygooglenews_client.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/pygooglenews_client.py>) · 306 lines

Google News queries, date restriction, Google wrapper URL resolve, browser retry ও resolution cache।

- [_cached_resolution()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/pygooglenews_client.py:62>) — Google wrapper URL-এর resolved article URL cache পড়ে/লেখে।
  - Signature: `_cached_resolution(url: str) -> str \| None`

- [_remember_resolution()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/pygooglenews_client.py:70>) — Google wrapper URL-এর resolved article URL cache পড়ে/লেখে।
  - Signature: `_remember_resolution(url: str, final: str) -> None`

- [_date_filter_is_useful()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/pygooglenews_client.py:80>) — Claimed date search-window filter হিসেবে ব্যবহারযোগ্য কি না যাচাই করে।
  - Signature: `_date_filter_is_useful(published_date: date) -> bool`

- [_unwrap_google_url()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/pygooglenews_client.py:84>) — Google URL wrapper থেকে embedded target URL বের করার চেষ্টা করে।
  - Signature: `_unwrap_google_url(url: str) -> str`

- [_strip_challenge_params()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/pygooglenews_client.py:94>) — Code-এর দায়িত্ব-বর্ণনা: Drop the one-shot token Cloudflare appends after clearing a challenge. Landing on a protected article through a browser leaves the URL as ...?__cf_chl_rt_tk=<token>. Kept as-is it becomes a second, unusable copy of an article already in the candidate set, and is what the user would be shown as the source link.
  - Signature: `_strip_challenge_params(url: str) -> str`

**Class [PyGoogleNewsClient](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/pygooglenews_client.py:115>)** · inherits `plain class`

- [PyGoogleNewsClient.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/pygooglenews_client.py:117>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self) -> None`

- [PyGoogleNewsClient._sync_search()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/pygooglenews_client.py:121>) — Blocking Google News client দিয়ে optional date-bound search চালায়।
  - Signature: `_sync_search(self, query: str, domain: str \| None, published_date: date \| None) -> list[tuple[str, str]]`

- [PyGoogleNewsClient.search_entries()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/pygooglenews_client.py:160>) — এই provider-এর search query থেকে article URL ও title entries সংগ্রহ করে।
  - Signature: `async search_entries(self, query: str, domain: str \| None=None, published_date: date \| None=None) -> list[tuple[str, str]]`

- [PyGoogleNewsClient._resolve_with_playwright()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/pygooglenews_client.py:189>) — Browser দিয়ে Google redirect resolve করে; প্রয়োজনমতো bounded retry।
  - Signature: `async _resolve_with_playwright(self, urls: list[str]) -> dict[str, str]`

- [PyGoogleNewsClient._resolve_with_retry()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/pygooglenews_client.py:201>) — Browser দিয়ে Google redirect resolve করে; প্রয়োজনমতো bounded retry।
  - Signature: `async _resolve_with_retry(self, urls: list[str]) -> dict[str, str]`

- [PyGoogleNewsClient._run_playwright_sync()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/pygooglenews_client.py:212>) — Browser context/page lifecycle চালায়; search client-এ redirects resolve, retrieval stage-এ article HTML fetch করে।
  - Signature: `_run_playwright_sync(self, urls: list[str]) -> dict[str, str]`

- [PyGoogleNewsClient._run_playwright_async()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/pygooglenews_client.py:227>) — Browser context/page lifecycle চালায়; search client-এ redirects resolve, retrieval stage-এ article HTML fetch করে।
  - Signature: `async _run_playwright_async(self, urls: list[str]) -> dict[str, str]`

- [PyGoogleNewsClient._run_playwright_async.resolve_one()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/search/pygooglenews_client.py:259>) — একটি Google News wrapper link browser-এ খুলে final publisher URL resolve করে।
  - Signature: `async resolve_one(url: str) -> tuple[str, str]`

### backend/app/features/sources/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/__init__.py>) · 1 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/sources/models.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/models.py>) · 132 lines

Feature `sources`। SQLAlchemy ORM entities: নিচে exact table, fields ও foreign-key/constraint declarations দেওয়া আছে।

**Class [VerifiedSource](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/models.py:10>)** · inherits `UUIDMixin, TimestampMixin, ReprMixin, Base` · table `verified_sources`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `canonical_name` | `Mapped[str]` | mapped_column(String(255), unique=True, nullable=False, index=True, comment='Canonical domain name (e.g. prothomalo.com) — unique identifier') |
| `display_name` | `Mapped[str]` | mapped_column(String(255), nullable=False, comment='Human-readable outlet name (e.g. Prothom Alo)') |
| `display_name_en` | `Mapped[str \| None]` | mapped_column(String(255), nullable=True, comment='English display name') |
| `aliases` | `Mapped[list \| None]` | mapped_column(JSON().with_variant(JSONB, 'postgresql'), nullable=True, default=list, comment='JSONB array of alternate names, e.g. ["প্রথম আলো", "prothom alo"]') |
| `base_url` | `Mapped[str]` | mapped_column(String(512), nullable=False, comment='Homepage URL (e.g. https://www.prothomalo.com)') |
| `rss_url` | `Mapped[str \| None]` | mapped_column(String(512), nullable=True, comment='RSS feed URL for Google News RSS client (optional)') |
| `language` | `Mapped[str]` | mapped_column(String(10), nullable=False, default='bn', comment="Primary language code: 'bn' (Bangla) or 'en' (English)") |
| `search_language` | `Mapped[str]` | mapped_column(String(10), nullable=False, default='bn', comment="Language for search queries: 'bn' or 'en'") |
| `js_rendered` | `Mapped[bool]` | mapped_column(Boolean, nullable=False, default=False, comment='Whether the site is JS-rendered (requires Playwright)') |
| `is_active` | `Mapped[bool]` | mapped_column(Boolean, nullable=False, default=True, index=True, comment='Whether this source is active and eligible for verification') |
| `description` | `Mapped[str \| None]` | mapped_column(Text, nullable=True, comment='Optional editorial description of the news outlet') |
| `body_selectors` | `Mapped[list[str] \| None]` | mapped_column(JSON().with_variant(JSONB, 'postgresql'), nullable=True, default=list, comment='CSS selectors for extracting article body') |
| `title_selectors` | `Mapped[list[str] \| None]` | mapped_column(JSON().with_variant(JSONB, 'postgresql'), nullable=True, default=list, comment='CSS selectors for extracting article title') |
| `date_selectors` | `Mapped[list[str] \| None]` | mapped_column(JSON().with_variant(JSONB, 'postgresql'), nullable=True, default=list, comment='CSS selectors for extracting published date') |
| `internal_search_url` | `Mapped[str \| None]` | mapped_column(String(512), nullable=True, comment='URL template for internal site search (e.g. .../search?q={query})') |
| `article_url_patterns` | `Mapped[list[str] \| None]` | mapped_column(JSON().with_variant(JSONB, 'postgresql'), nullable=True, default=list, comment='Regex patterns to match valid article URLs') |

Database constraints/indexes: `__table_args__ = (Index('ix_verified_sources_aliases_gin', aliases, postgresql_using='gin'), Index('ix_verified_sources_language_active', language, is_active))`

### backend/app/features/sources/repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/repository.py>) · 160 lines

Feature `sources`। এই feature-এর database queries ও persistence operations; যেখানে BaseRepository inherit করেছে সেখানে common CRUD inherited।

**Class [SourceRepository](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/repository.py:15>)** · inherits `BaseRepository[VerifiedSource]`

- [SourceRepository.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/repository.py:19>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, session: AsyncSession) -> None`

- [SourceRepository.get_by_canonical_name()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/repository.py:22>) — Canonical name/alias অনুযায়ী publisher resolve বা policy অনুযায়ী source mode নির্ধারণ করে।
  - Signature: `async get_by_canonical_name(self, canonical_name: str) -> VerifiedSource \| None`

- [SourceRepository.get_by_alias()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/repository.py:31>) — Canonical name/alias অনুযায়ী publisher resolve বা policy অনুযায়ী source mode নির্ধারণ করে।
  - Signature: `async get_by_alias(self, alias: str) -> VerifiedSource \| None`

- [SourceRepository.resolve_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/repository.py:46>) — Canonical name/alias অনুযায়ী publisher resolve বা policy অনুযায়ী source mode নির্ধারণ করে।
  - Signature: `async resolve_source(self, raw_name: str) -> VerifiedSource \| None`

- [SourceRepository.list_active()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/repository.py:62>) — Active verified publishers-এর list/count দেয়।
  - Signature: `async list_active(self, *, language: str \| None=None, limit: int=50, offset: int=0) -> list[VerifiedSource]`

- [SourceRepository.count_active()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/repository.py:80>) — Active verified publishers-এর list/count দেয়।
  - Signature: `async count_active(self) -> int`

- [SourceRepository.list_all()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/repository.py:91>) — নির্ধারিত ordering/pagination অনুযায়ী records আনে।
  - Signature: `async list_all(self, *, language: str \| None=None, limit: int=50, offset: int=0) -> list[VerifiedSource]`

- [SourceRepository.search()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/repository.py:109>) — Code-এর দায়িত্ব-বর্ণনা: Sources matching `query` in the Bangla or English name, domain, base URL or aliases (best matches first), with the matching total.
  - Signature: `async search(self, query: str, *, include_inactive: bool, language: str \| None=None, limit: int=50, offset: int=0) -> tuple[list[VerifiedSource], int]`

- [SourceRepository.count_all()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/repository.py:155>) — সংশ্লিষ্ট records-এর total count বের করে।
  - Signature: `async count_all(self) -> int`

### backend/app/features/sources/resolution.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/resolution.py>) · 54 lines

URL/domain, known aliases, database aliases থেকে canonical claimed source resolve।

- [resolve_claimed_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/resolution.py:18>) — Code-এর দায়িত্ব-বর্ণনা: Best-effort resolution, in order of decreasing certainty: 1. The text itself is a URL or bare domain. 2. The text matches a known static alias. 3. The text matches an entry in the verified-source registry (fuzzy/DB lookup). Returns ``None`` when none of the three succeed — callers decide what to do with that (raise, in every current caller).
  - Signature: `async resolve_claimed_source(raw_source: str, source_repo: SourceRepository) -> str \| None`

### backend/app/features/sources/router.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/router.py>) · 126 lines

Feature `sources`। এই feature-এর HTTP paths, request/response schema, dependencies ও permission guard define করে; handler সংশ্লিষ্ট service/repository-তে কাজ পাঠায়।

- [list_sources()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/router.py:28>) — Source filters/search/page অনুযায়ী source catalogue response দেয়।
  - Signature: `async list_sources(language: str \| None=Query(None, description="Filter by language code (e.g. 'bn', 'en')"), page: int=Query(1, ge=1, description='Page number (1-indexed)'), size: int=Query(20, ge=1, le=100, description='Results per page'), include_inactive: bool=Query(False, description='Include deactivated sources (admin management use). Public callers — e.g. the claimed-source dropdown — should omit this so only active sources are returned.'), q: str \| None=Query(None, max_length=200, description='Search name, domain, URL or aliases'), service: SourceService=Depends(get_source_service)) -> SourceListSchema`

- [create_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/router.py:58>) — Validated source registry entry তৈরি করে; duplicate name reject করে।
  - Signature: `async create_source(payload: SourceCreateSchema, _: User=Depends(_ADMIN_ONLY), service: SourceService=Depends(get_source_service)) -> SourceResponseSchema`

- [get_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/router.py:77>) — Source UUID অনুযায়ী public source detail আনে।
  - Signature: `async get_source(source_id: uuid.UUID, service: SourceService=Depends(get_source_service)) -> SourceResponseSchema`

- [update_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/router.py:95>) — Source-এর শুধু provided editable fields পরিবর্তন করে।
  - Signature: `async update_source(source_id: uuid.UUID, payload: SourceUpdateSchema, _: User=Depends(_ADMIN_ONLY), service: SourceService=Depends(get_source_service)) -> SourceResponseSchema`

- [delete_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/router.py:115>) — অনুমোদিত source registry entry delete করে।
  - Signature: `async delete_source(source_id: uuid.UUID, _: User=Depends(_ADMIN_ONLY), service: SourceService=Depends(get_source_service)) -> None`

### backend/app/features/sources/schemas.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/schemas.py>) · 210 lines

Feature `sources`। এই feature-এর Pydantic request/response structures ও validation define করে; এগুলো database table নয়।

**Class [SourceCreateSchema](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/schemas.py:12>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `canonical_name` | `str` | Field(..., min_length=4, max_length=255, description='Canonical domain name in lowercase (e.g. prothomalo.com)', examples=['prothomalo.com', 'thedailystar.net']) |
| `display_name` | `str` | Field(..., min_length=1, max_length=255) |
| `display_name_en` | `str \| None` | Field(default=None, max_length=255) |
| `aliases` | `list[str]` | Field(default_factory=list) |
| `base_url` | `str` | Field(..., max_length=512) |
| `rss_url` | `str \| None` | Field(default=None, max_length=512) |
| `language` | `str` | Field(default='bn', min_length=2, max_length=10, examples=['bn', 'en']) |
| `search_language` | `str` | Field(default='bn', min_length=2, max_length=10, examples=['bn', 'en']) |
| `js_rendered` | `bool` | Field(default=False) |
| `description` | `str \| None` | Field(default=None, max_length=2000) |
| `body_selectors` | `list[str]` | Field(default_factory=list) |
| `title_selectors` | `list[str]` | Field(default_factory=list) |
| `date_selectors` | `list[str]` | Field(default_factory=list) |
| `internal_search_url` | `str \| None` | Field(default=None, max_length=512) |
| `article_url_patterns` | `list[str]` | Field(default_factory=list) |

- [SourceCreateSchema._validate_canonical_name()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/schemas.py:42>) — Canonical publisher name/domain syntax normalize ও validate করে।
  - Signature: `_validate_canonical_name(cls, v: str) -> str`

- [SourceCreateSchema._validate_language()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/schemas.py:52>) — Language code normalize করে allowed format পরীক্ষা করে।
  - Signature: `_validate_language(cls, v: str) -> str`

- [SourceCreateSchema._validate_search_language()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/schemas.py:61>) — Language code normalize করে allowed format পরীক্ষা করে।
  - Signature: `_validate_search_language(cls, v: str) -> str`

- [SourceCreateSchema._validate_aliases()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/schemas.py:70>) — Alias values trim ও deduplicate করে।
  - Signature: `_validate_aliases(cls, v: list[str]) -> list[str]`

- [SourceCreateSchema._validate_base_url()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/schemas.py:82>) — HTTP(S) source base URL validate/normalize করে।
  - Signature: `_validate_base_url(cls, v: str) -> str`

**Class [SourceUpdateSchema](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/schemas.py:102>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `display_name` | `str \| None` | Field(default=None, min_length=1, max_length=255) |
| `display_name_en` | `str \| None` | Field(default=None, max_length=255) |
| `aliases` | `list[str] \| None` | Field(default=None) |
| `base_url` | `str \| None` | Field(default=None, max_length=512) |
| `rss_url` | `str \| None` | Field(default=None, max_length=512) |
| `language` | `str \| None` | Field(default=None, min_length=2, max_length=10) |
| `search_language` | `str \| None` | Field(default=None, min_length=2, max_length=10) |
| `js_rendered` | `bool \| None` | Field(default=None) |
| `description` | `str \| None` | Field(default=None, max_length=2000) |
| `is_active` | `bool \| None` | Field(default=None) |
| `body_selectors` | `list[str] \| None` | Field(default=None) |
| `title_selectors` | `list[str] \| None` | Field(default=None) |
| `date_selectors` | `list[str] \| None` | Field(default=None) |
| `internal_search_url` | `str \| None` | Field(default=None, max_length=512) |
| `article_url_patterns` | `list[str] \| None` | Field(default=None) |

- [SourceUpdateSchema._validate_aliases()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/schemas.py:122>) — Alias values trim ও deduplicate করে।
  - Signature: `_validate_aliases(cls, v: list[str] \| None) -> list[str] \| None`

- [SourceUpdateSchema._validate_base_url()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/schemas.py:136>) — HTTP(S) source base URL validate/normalize করে।
  - Signature: `_validate_base_url(cls, v: str \| None) -> str \| None`

**Class [SourceResponseSchema](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/schemas.py:154>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `id` | `uuid.UUID` | required / instance-assigned |
| `canonical_name` | `str` | required / instance-assigned |
| `display_name` | `str` | required / instance-assigned |
| `display_name_en` | `str \| None` | None |
| `aliases` | `list[str]` | Field(default_factory=list) |
| `base_url` | `str` | required / instance-assigned |
| `rss_url` | `str \| None` | None |
| `language` | `str` | required / instance-assigned |
| `search_language` | `str` | required / instance-assigned |
| `js_rendered` | `bool` | required / instance-assigned |
| `is_active` | `bool` | required / instance-assigned |
| `description` | `str \| None` | None |
| `body_selectors` | `list[str]` | Field(default_factory=list) |
| `title_selectors` | `list[str]` | Field(default_factory=list) |
| `date_selectors` | `list[str]` | Field(default_factory=list) |
| `internal_search_url` | `str \| None` | None |
| `article_url_patterns` | `list[str]` | Field(default_factory=list) |
| `created_at` | `datetime` | required / instance-assigned |
| `updated_at` | `datetime` | required / instance-assigned |

**Class [SourceListSchema](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/schemas.py:198>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `items` | `list[SourceResponseSchema]` | required / instance-assigned |
| `total` | `int` | Field(..., ge=0) |
| `page` | `int` | Field(..., ge=1) |
| `size` | `int` | Field(..., ge=1, le=100) |
| `pages` | `int` | Field(..., ge=0) |

### backend/app/features/sources/service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/service.py>) · 95 lines

Source create/read/update/delete/list/search; duplicate canonical source validation।

**Class [SourceService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/service.py:17>)** · inherits `plain class`

- [SourceService.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/service.py:19>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, source_repo: SourceRepository) -> None`

- [SourceService.create_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/service.py:22>) — Validated source registry entry তৈরি করে; duplicate name reject করে।
  - Signature: `async create_source(self, payload: SourceCreateSchema) -> SourceResponseSchema`

- [SourceService.get_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/service.py:48>) — Source UUID অনুযায়ী public source detail আনে।
  - Signature: `async get_source(self, source_id: uuid.UUID) -> SourceResponseSchema`

- [SourceService.update_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/service.py:52>) — Source-এর শুধু provided editable fields পরিবর্তন করে।
  - Signature: `async update_source(self, source_id: uuid.UUID, payload: SourceUpdateSchema) -> SourceResponseSchema`

- [SourceService.delete_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/service.py:61>) — অনুমোদিত source registry entry delete করে।
  - Signature: `async delete_source(self, source_id: uuid.UUID) -> None`

- [SourceService.list_sources()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/sources/service.py:64>) — Source filters/search/page অনুযায়ী source catalogue response দেয়।
  - Signature: `async list_sources(self, *, language: str \| None=None, page: int=1, size: int=20, include_inactive: bool=False, q: str \| None=None) -> SourceListSchema`

### backend/app/features/submissions/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/__init__.py>) · 0 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/submissions/access.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/access.py>) · 31 lines

Pending/processing/failed owner submission-এর access policy; public completed results এবং guest-ID behavior আলাদা।

- [viewer_can_see()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/access.py:24>) — Submission lifecycle/owner/staff/guest policy অনুযায়ী read permission জানায়।
  - Signature: `viewer_can_see(submission: Submission, user) -> bool`

### backend/app/features/submissions/models.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/models.py>) · 334 lines

Feature `submissions`। SQLAlchemy ORM entities: নিচে exact table, fields ও foreign-key/constraint declarations দেওয়া আছে।

**Class [Submission](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/models.py:37>)** · inherits `UUIDMixin, TimestampMixin, ReprMixin, Base` · table `submissions`

দায়িত্ব/contract: DatabaseDescription.pdf Table 4.5 — submissions.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_type` | `Mapped[SubmissionType]` | mapped_column(Enum(SubmissionType, name='submission_type_enum', create_type=True), nullable=False, index=True, comment='MULTIMODAL \| SOURCE_BASED \| PHOTO_CARD') |
| `headline` | `Mapped[str \| None]` | mapped_column(Text, nullable=True) |
| `body_text` | `Mapped[str \| None]` | mapped_column(Text, nullable=True) |
| `claimed_source_text` | `Mapped[str \| None]` | mapped_column(String(255), nullable=True, comment='Raw source string as provided by the user') |
| `claimed_source_id` | `Mapped[uuid.UUID \| None]` | mapped_column(UUID(as_uuid=True), ForeignKey('verified_sources.id', ondelete='SET NULL'), nullable=True, index=True) |
| `published_date` | `Mapped[date \| None]` | mapped_column(Date, nullable=True) |
| `submitter_id` | `Mapped[uuid.UUID \| None]` | mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True) |
| `content_hash` | `Mapped[str]` | mapped_column(String(64), nullable=False, index=True, comment='SHA-256 hex of normalised submission content — dedup key') |
| `duplicate_of_submission_id` | `Mapped[uuid.UUID \| None]` | mapped_column(UUID(as_uuid=True), ForeignKey('submissions.id', ondelete='SET NULL'), nullable=True, comment='Self-referential FK — set when this submission is a duplicate of another') |
| `status` | `Mapped[SubmissionStatus]` | mapped_column(Enum(SubmissionStatus, name='submission_status_enum', create_type=True), nullable=False, default=SubmissionStatus.PENDING, index=True) |
| `is_published` | `Mapped[bool]` | mapped_column(Boolean, nullable=False, default=False) |
| `view_count` | `Mapped[int]` | mapped_column(Integer, nullable=False, default=0) |
| `processing_phase` | `Mapped[str \| None]` | mapped_column(String(16), nullable=True, comment='Finer progress inside PENDING/PROCESSING (QUEUED \| EXTRACTING \| VERIFYING \| DONE \| FAILED). The public lifecycle enum is unchanged.') |
| `failure_reason` | `Mapped[str \| None]` | mapped_column(Text, nullable=True, comment='Short, user-presentable reason when status is FAILED (e.g. no readable headline in the image).') |
| `escalated_at` | `Mapped[datetime \| None]` | mapped_column(DateTime(timezone=True), nullable=True, comment='When expert review escalated this claim to admin review (NULL otherwise).') |
| `claimed_source` | `Mapped['VerifiedSource \| None']` | relationship('VerifiedSource', primaryjoin='Submission.claimed_source_id == VerifiedSource.id', viewonly=True, lazy='select') |
| `submitter` | `Mapped['User \| None']` | relationship('User', primaryjoin='Submission.submitter_id == User.id', viewonly=True, lazy='select') |
| `evidence_queries` | `Mapped[list['SourceEvidenceQuery']]` | relationship('SourceEvidenceQuery', back_populates='submission', lazy='select', cascade='all, delete-orphan') |
| `retrieved_articles` | `Mapped[list['RetrievedArticle']]` | relationship('RetrievedArticle', back_populates='submission', lazy='select', cascade='all, delete-orphan') |
| `photocard_extraction` | `Mapped['PhotocardExtraction \| None']` | relationship('PhotocardExtraction', back_populates='submission', lazy='select', cascade='all, delete-orphan', uselist=False) |

Database constraints/indexes: `__table_args__ = (Index('ix_submissions_status_created', status, 'created_at'),)`

**Class [SourceEvidenceQuery](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/models.py:162>)** · inherits `UUIDMixin, ReprMixin, Base` · table `source_evidence_queries`

দায়িত্ব/contract: DatabaseDescription.pdf Table 4.6 — source_evidence_queries.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `Mapped[uuid.UUID]` | mapped_column(UUID(as_uuid=True), ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False, index=True) |
| `query_type` | `Mapped[QueryType]` | mapped_column(Enum(QueryType, name='query_type_enum', create_type=False), nullable=False) |
| `query_text` | `Mapped[str]` | mapped_column(Text, nullable=False) |
| `search_provider` | `Mapped[SearchProvider]` | mapped_column(Enum(SearchProvider, name='search_provider_enum', create_type=False), nullable=False, index=True) |
| `results_count` | `Mapped[int]` | mapped_column(Integer, nullable=False, default=0) |
| `executed_at` | `Mapped[datetime]` | mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True) |
| `submission` | `Mapped['Submission']` | relationship('Submission', back_populates='evidence_queries', lazy='select') |

Database constraints/indexes: `__table_args__ = (Index('ix_source_evidence_queries_submission_provider', submission_id, search_provider),)`

**Class [RetrievedArticle](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/models.py:207>)** · inherits `UUIDMixin, ReprMixin, Base` · table `retrieved_articles`

দায়িত্ব/contract: Retrieved source evidence for a submission.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `Mapped[uuid.UUID]` | mapped_column(UUID(as_uuid=True), ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False, index=True) |
| `url` | `Mapped[str]` | mapped_column(Text, nullable=False) |
| `url_hash` | `Mapped[str]` | mapped_column(String(64), nullable=False) |
| `title` | `Mapped[str \| None]` | mapped_column(Text, nullable=True) |
| `body` | `Mapped[str \| None]` | mapped_column(Text, nullable=True) |
| `author` | `Mapped[str \| None]` | mapped_column(String(255), nullable=True) |
| `published_date` | `Mapped[date \| None]` | mapped_column(Date, nullable=True) |
| `extraction_method` | `Mapped[ExtractionMethod \| None]` | mapped_column(Enum(ExtractionMethod, name='extraction_method_enum', create_type=False), nullable=True) |
| `extraction_success` | `Mapped[bool]` | mapped_column(Boolean, nullable=False, default=False, index=True) |
| `rank_score` | `Mapped[float \| None]` | mapped_column(Float, nullable=True, index=True) |
| `retrieved_at` | `Mapped[datetime]` | mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False) |
| `submission` | `Mapped['Submission']` | relationship('Submission', back_populates='retrieved_articles', lazy='select') |

Database constraints/indexes: `__table_args__ = (CheckConstraint('rank_score IS NULL OR (rank_score >= 0.0 AND rank_score <= 1.0)', name='ck_retrieved_articles_rank_score_range'), Index('uq_retrieved_articles_submission_url_hash', submission_id, url_hash, unique=True))`

**Class [PhotocardExtraction](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/models.py:268>)** · inherits `UUIDMixin, TimestampMixin, ReprMixin, Base` · table `photocard_extractions`

দায়িত্ব/contract: Gemini extraction of a photo card (one row per PHOTO_CARD submission). The extracted headline, verified source and published date are NOT stored here: on success they become the submission's own headline, claimed_source_id/claimed_source_text and published_date - the single representation of the claim. This row keeps the stored image and the extraction provenance only.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `Mapped[uuid.UUID]` | mapped_column(UUID(as_uuid=True), ForeignKey('submissions.id', ondelete='CASCADE'), unique=True, nullable=False, index=True) |
| `image_object_key` | `Mapped[str]` | mapped_column(String(1024), nullable=False) |
| `status` | `Mapped[str]` | mapped_column(String(20), nullable=False, default='PENDING', server_default='PENDING', comment='PENDING \| SUCCEEDED \| API_FAILED (every Gemini request failed) \| INVALID_CONTENT (no headline or no active verified source on the card) \| FAILED (legacy OCR-era failure)') |
| `failure_code` | `Mapped[str \| None]` | mapped_column(String(40), nullable=True, comment='gemini_unavailable \| headline_missing \| source_not_identified \| headline_and_source_missing') |
| `model_version` | `Mapped[str \| None]` | mapped_column(String(100), nullable=True, comment='Gemini model id that read the card.') |
| `attempts` | `Mapped[int \| None]` | mapped_column(Integer, nullable=True, comment='Gemini requests made for this card (first request included, at most 9).') |
| `extraction_details` | `Mapped[dict \| None]` | mapped_column(JSONB, nullable=True, comment="Provenance: per-attempt Gemini outcomes, the validated raw response (headline, source id + visible evidence, date as printed) and the parsed date. Legacy OCR-era values are kept under 'legacy'.") |
| `submission` | `Mapped['Submission']` | relationship('Submission', back_populates='photocard_extraction', lazy='select') |

### backend/app/features/submissions/repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py>) · 363 lines

Feature `submissions`। এই feature-এর database queries ও persistence operations; যেখানে BaseRepository inherit করেছে সেখানে common CRUD inherited।

**Class [SubmissionRepository](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:34>)** · inherits `BaseRepository[Submission]`

- [SubmissionRepository.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:38>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, session: AsyncSession) -> None`

- [SubmissionRepository.get_by_id_locked()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:41>) — Code-এর দায়িত্ব-বর্ণনা: Row-locks the submission for the rest of this transaction — concurrent vote/finalize attempts on the same claim serialize on this lock instead of racing, since a single request's session is one transaction (committed when the request completes).
  - Signature: `async get_by_id_locked(self, submission_id: uuid.UUID) -> Submission`

- [SubmissionRepository.get_reusable_candidates()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:55>) — Code-এর দায়িত্ব-বর্ণনা: Verified, non-duplicate submissions with this exact claim identity, newest first. Callers still validate each one's result for reusability and freshness.
  - Signature: `async get_reusable_candidates(self, content_hash: str, *, limit: int=5) -> list[Submission]`

- [SubmissionRepository.get_in_flight_by_content_hash()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:75>) — Code-এর দায়িত্ব-বর্ণনা: A submission for this claim that is queued or still running.
  - Signature: `async get_in_flight_by_content_hash(self, content_hash: str) -> Submission \| None`

- [SubmissionRepository.set_status()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:93>) — Submission lifecycle status পরিবর্তন করে।
  - Signature: `async set_status(self, submission_id: uuid.UUID, status: SubmissionStatus) -> None`

- [SubmissionRepository.mark_processing()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:106>) — Submission PROCESSING করে।
  - Signature: `async mark_processing(self, submission_id: uuid.UUID) -> None`

- [SubmissionRepository.mark_ai_done()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:109>) — Automatic work complete করে EXPERT_REVIEW এবং processing phase DONE করে।
  - Signature: `async mark_ai_done(self, submission_id: uuid.UUID) -> None`

- [SubmissionRepository.mark_finalized()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:124>) — Submission FINALIZED করে।
  - Signature: `async mark_finalized(self, submission_id: uuid.UUID) -> None`

- [SubmissionRepository.escalate_if_open()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:127>) — Code-এর দায়িত্ব-বর্ণনা: EXPERT_REVIEW -> ESCALATED, only if the claim is still open. Returns True only for the one transaction that performs the transition, so a racing vote, edit or sweep can never escalate (or notify) twice.
  - Signature: `async escalate_if_open(self, submission_id: uuid.UUID) -> bool`

- [SubmissionRepository.mark_failed()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:141>) — Code-এর দায়িত্ব-বর্ণনা: Terminal failure. Returns True only on the transition INTO failed, so callers can emit the failure notification exactly once.
  - Signature: `async mark_failed(self, submission_id: uuid.UUID, reason: str \| None=None) -> bool`

- [SubmissionRepository.set_phase()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:166>) — QUEUED/EXTRACTING/VERIFYING ইত্যাদি fine-grained progress বদলায়।
  - Signature: `async set_phase(self, submission_id: uuid.UUID, phase: str) -> None`

- [SubmissionRepository.search()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:174>) — Code-এর দায়িত্ব-বর্ণনা: Fact Explorer search — browse verified (EXPERT_REVIEW/FINALIZED) submissions with optional filters. Returns (rows, total_count). overall_verdict spans every submission type (its finalized value lives on VerificationResult for SOURCE_BASED/PHOTO_CARD, and on MultimodalAnalysis for MULTIMODAL) and only matches claims that have actually been expert-finalized — a claim still under review doesn't match any overall_verdict filter, even though its AI-implied value may be shown on its own detail page.
  - Signature: `async search(self, *, keyword: str \| None=None, source_status: SourceStatus \| None=None, content_status: ContentStatus \| None=None, date_status: DateStatus \| None=None, overall_verdict: OverallVerdict \| None=None, method: SubmissionType \| None=None, date_from: date \| None=None, date_to: date \| None=None, source_id: uuid.UUID \| None=None, review_state: Literal['finalized', 'review'] \| None=None, limit: int=20, offset: int=0) -> tuple[list[Submission], int]`

- [SubmissionRepository.explorer_summary()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:285>) — Code-এর দায়িত্ব-বর্ণনা: All-time counts for exactly the public archive's eligible records.
  - Signature: `async explorer_summary(self) -> dict[str, int]`

**Class [RetrievedArticleRepository](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:305>)** · inherits `BaseRepository[RetrievedArticle]`

- [RetrievedArticleRepository.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:309>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, session: AsyncSession) -> None`

- [RetrievedArticleRepository.get_by_url_hash()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:312>) — একটি submission-এর একই article URL hash-এর saved evidence খোঁজে।
  - Signature: `async get_by_url_hash(self, submission_id: uuid.UUID, url_hash: str) -> RetrievedArticle \| None`

- [RetrievedArticleRepository.get_for_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:328>) — Submission ID-র সঙ্গে যুক্ত result/record(s) query করে।
  - Signature: `async get_for_submission(self, submission_id: uuid.UUID, *, successful_only: bool=True, order_by_rank: bool=True, limit: int=10) -> list[RetrievedArticle]`

**Class [PhotocardExtractionRepository](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:347>)** · inherits `BaseRepository[PhotocardExtraction]`

- [PhotocardExtractionRepository.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:351>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, session: AsyncSession) -> None`

- [PhotocardExtractionRepository.get_by_submission_id()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/repository.py:354>) — Submission ID-র সঙ্গে যুক্ত result/record(s) query করে।
  - Signature: `async get_by_submission_id(self, submission_id: uuid.UUID) -> PhotocardExtraction \| None`

### backend/app/features/submissions/router.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/router.py>) · 97 lines

Feature `submissions`। এই feature-এর HTTP paths, request/response schema, dependencies ও permission guard define করে; handler সংশ্লিষ্ট service/repository-তে কাজ পাঠায়।

- [get_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/router.py:32>) — Access-checked method-neutral submission metadata দেয়; caller detail endpoint বেছে নিতে পারে।
  - Signature: `async get_submission(submission_id: uuid.UUID, session: AsyncSession=Depends(get_async_session), current_user: User \| None=Depends(get_current_user_optional)) -> SubmissionLookupResponse`

- [get_voting_details()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/router.py:86>) — Finalized claim-এর public expert/admin vote details দেয়; আগে 404।
  - Signature: `async get_voting_details(submission_id: uuid.UUID, session: AsyncSession=Depends(get_async_session)) -> PublicVotingDetails`

### backend/app/features/submissions/schemas.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/schemas.py>) · 34 lines

Feature `submissions`। এই feature-এর Pydantic request/response structures ও validation define করে; এগুলো database table নয়।

**Class [SubmissionLookupResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/submissions/schemas.py:11>)** · inherits `BaseModel`

দায়িত্ব/contract: Minimal, type-agnostic submission summary. Each verification method (source-based, multimodal, photo-card) has its own detail endpoint with its own shape — GET /verify/{id}, GET /multimodal/by-submission/{id}, GET /photocard/{id}. A result page that only has a submission_id (from Fact Explorer, submission history, or a notification link) needs to know which of those to call before it can fetch anything, since the three are not interchangeable. This endpoint is that first lookup.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `uuid.UUID` | required / instance-assigned |
| `submission_type` | `SubmissionType` | required / instance-assigned |
| `status` | `SubmissionStatus` | required / instance-assigned |
| `headline` | `str \| None` | required / instance-assigned |
| `body_text` | `str \| None` | None |
| `claimed_source_text` | `str \| None` | None |
| `published_date` | `date \| None` | None |
| `processing_phase` | `str \| None` | None |
| `failure_reason` | `str \| None` | None |
| `created_at` | `datetime` | required / instance-assigned |

### backend/app/features/users/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/__init__.py>) · 1 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/users/router.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/router.py>) · 77 lines

Feature `users`। এই feature-এর HTTP paths, request/response schema, dependencies ও permission guard define করে; handler সংশ্লিষ্ট service/repository-তে কাজ পাঠায়।

- [_service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/router.py:23>) — FastAPI dependency হিসেবে এই feature-এর service প্রয়োজনীয় repository/shared resources দিয়ে তৈরি করে।
  - Signature: `_service(request: Request, session: AsyncSession=Depends(get_async_session)) -> UserAccountService`

- [get_my_submissions()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/router.py:32>) — Authenticated user-এর নিজের submission history দেয়।
  - Signature: `async get_my_submissions(limit: int=Query(default=20, ge=1, le=100), offset: int=Query(default=0, ge=0), q: str \| None=Query(default=None, max_length=200, description='Keyword search over headline, text and outlet'), state: Literal['in_progress', 'review', 'final', 'failed'] \| None=Query(default=None), submission_type: SubmissionType \| None=Query(default=None, alias='type'), current_user: User=Depends(get_current_user), svc: UserAccountService=Depends(_service)) -> list[SubmissionSummary]`

- [get_my_submission_stats()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/router.py:47>) — নিজের submissions-এর status/finding counts aggregate করে।
  - Signature: `async get_my_submission_stats(current_user: User=Depends(get_current_user), svc: UserAccountService=Depends(_service)) -> SubmissionStatsResponse`

- [get_my_profile()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/router.py:55>) — Authenticated user-এর profile response দেয়।
  - Signature: `async get_my_profile(current_user: User=Depends(get_current_user), svc: UserAccountService=Depends(_service)) -> ProfileResponse`

- [update_my_profile()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/router.py:63>) — Authenticated user-এর editable full name update করে।
  - Signature: `async update_my_profile(body: UpdateProfileRequest, current_user: User=Depends(get_current_user), svc: UserAccountService=Depends(_service)) -> ProfileResponse`

### backend/app/features/users/schemas.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/schemas.py>) · 63 lines

Feature `users`। এই feature-এর Pydantic request/response structures ও validation define করে; এগুলো database table নয়।

**Class [SubmissionSummary](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/schemas.py:17>)** · inherits `BaseModel`

দায়িত্ব/contract: One row of My Submissions. Valid for a submission that has no result or even no headline yet (a just-accepted photo card).

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `str` | required / instance-assigned |
| `submission_type` | `SubmissionType` | SubmissionType.SOURCE_BASED |
| `headline` | `str \| None` | required / instance-assigned |
| `claimed_source_text` | `str \| None` | required / instance-assigned |
| `status` | `str` | required / instance-assigned |
| `phase` | `str \| None` | None |
| `failure_reason` | `str \| None` | None |
| `source_status` | `SourceStatus \| None` | required / instance-assigned |
| `content_status` | `ContentStatus \| None` | required / instance-assigned |
| `headline_status` | `HeadlineAlterationStatus \| None` | None |
| `date_status` | `DateStatus \| None` | None |
| `published_date` | `date \| None` | None |
| `overall_verdict` | `OverallVerdict \| None` | None |
| `prediction` | `str \| None` | None |
| `is_finalized` | `bool` | False |
| `ai_confidence` | `float \| None` | required / instance-assigned |
| `image_url` | `str \| None` | None |
| `submitted_at` | `datetime` | required / instance-assigned |
| `updated_at` | `datetime \| None` | None |

**Class [SubmissionStatsResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/schemas.py:43>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `total` | `int` | required / instance-assigned |
| `source_confirmed` | `int` | required / instance-assigned |
| `source_not_found` | `int` | required / instance-assigned |
| `content_matched` | `int` | required / instance-assigned |
| `content_altered` | `int` | required / instance-assigned |
| `pending` | `int` | required / instance-assigned |

**Class [ProfileResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/schemas.py:52>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `id` | `str` | required / instance-assigned |
| `full_name` | `str \| None` | required / instance-assigned |
| `email` | `str` | required / instance-assigned |
| `role` | `str` | required / instance-assigned |
| `is_active` | `bool` | required / instance-assigned |
| `total_submissions` | `int` | required / instance-assigned |
| `member_since` | `datetime` | required / instance-assigned |

**Class [UpdateProfileRequest](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/schemas.py:62>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `full_name` | `str \| None` | Field(default=None, max_length=255) |

### backend/app/features/users/service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/service.py>) · 256 lines

Signed-in user-এর নিজের submissions/filter/stats, profile ও name update; live submission counts।

- [to_profile_response()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/service.py:22>) — Stored model/data-কে নির্দিষ্ট public response schema-তে রূপ দেয়।
  - Signature: `to_profile_response(user: User, total_submissions: int) -> ProfileResponse`

- [_state_condition()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/service.py:40>) — History filter state-এর SQL condition তৈরি করে।
  - Signature: `_state_condition(state: str, original)`

**Class [UserAccountService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/service.py:58>)** · inherits `plain class`

- [UserAccountService.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/service.py:59>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, session: AsyncSession, *, photocard_storage: PhotoCardStorageService \| None=None) -> None`

- [UserAccountService.my_submissions()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/service.py:65>) — Code-এর দায়িত্ব-বর্ণনা: Owner-only: the user's own submissions, including ones still PENDING/PROCESSING or FAILED and ones with no headline yet. Optional filters: `q` keyword search over the headline, body text and claimed outlet (best matches first), `state` (MY_SUBMISSION_STATES) and `submission_type`. Filtering happens before pagination.
  - Signature: `async my_submissions(self, user: User, *, limit: int, offset: int, q: str \| None=None, state: str \| None=None, submission_type: SubmissionType \| None=None) -> list[SubmissionSummary]`

- [UserAccountService.my_submission_stats()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/service.py:178>) — নিজের submissions-এর status/finding counts aggregate করে।
  - Signature: `async my_submission_stats(self, user: User) -> SubmissionStatsResponse`

- [UserAccountService.my_submission_stats._sc()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/service.py:201>) — Submission statistics-এর নির্দিষ্ট source/content outcome count helper।
  - Signature: `_sc(status: SourceStatus)`

- [UserAccountService.my_submission_stats._cc()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/service.py:212>) — Submission statistics-এর নির্দিষ্ট source/content outcome count helper।
  - Signature: `_cc(status: ContentStatus)`

- [UserAccountService.submission_count()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/service.py:237>) — Code-এর দায়িত্ব-বর্ণনা: Every submission the user has made, counted live - the same total My Submissions shows. (The cached `users.total_submissions` counter was only bumped for some completed checks - never for photo cards, reused results or failed checks - so it drifted far from the real number.)
  - Signature: `async submission_count(self, user: User) -> int`

- [UserAccountService.profile()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/service.py:248>) — Authenticated user-এর profile response দেয়।
  - Signature: `async profile(self, user: User) -> ProfileResponse`

- [UserAccountService.update_full_name()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/users/service.py:251>) — Authenticated user-এর editable full name update করে।
  - Signature: `async update_full_name(self, user: User, full_name: str \| None) -> ProfileResponse`

### backend/app/features/verification/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/__init__.py>) · 1 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/verification/analysis/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/__init__.py>) · 7 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/verification/analysis/body_similarity.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/body_similarity.py>) · 214 lines

TF-IDF/Jaccard/normalized edit-distance/semantic cosine measures এবং available/skipped/unavailable result states।

**Class [MetricResult](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/body_similarity.py:75>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `available` | `bool` | required / instance-assigned |
| `value` | `float \| None` | None |
| `raw_value` | `float \| None` | None |
| `reason` | `str \| None` | None |
| `details` | `dict` | field(default_factory=dict) |

**Class [BodySimilarityResult](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/body_similarity.py:84>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `status` | `BodyComparisonStatus` | required / instance-assigned |
| `reason` | `str \| None` | None |
| `metrics` | `dict[str, MetricResult]` | field(default_factory=dict) |
| `claim_chars` | `int \| None` | None |
| `source_chars` | `int \| None` | None |

- [_light_normalise()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/body_similarity.py:92>) — Body edit-distance comparison-এর জন্য হালকা Unicode/whitespace normalization করে।
  - Signature: `_light_normalise(text: str) -> str`

- [tfidf_cosine_similarity()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/body_similarity.py:98>) — দুই body-র token-frequency/IDF weighted vector-এর cosine similarity বের করে।
  - Signature: `tfidf_cosine_similarity(a: str, b: str) -> MetricResult`

- [tfidf_cosine_similarity.idf()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/body_similarity.py:104>) — এই pair-এর document frequency থেকে inverse-document-frequency weight দেয়।
  - Signature: `idf(term: str) -> float`

- [jaccard_similarity()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/body_similarity.py:120>) — দুই body-র token-set intersection/union ratio বের করে।
  - Signature: `jaccard_similarity(a: str, b: str) -> MetricResult`

- [normalized_levenshtein_similarity()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/body_similarity.py:130>) — Normalized text-এর edit distance length দিয়ে scale করে similarity বের করে।
  - Signature: `normalized_levenshtein_similarity(a: str, b: str) -> MetricResult`

- [semantic_cosine_similarity()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/body_similarity.py:149>) — Text chunks-এর embedding similarity থেকে body semantic score বের করে।
  - Signature: `async semantic_cosine_similarity(a: str, b: str, embedder) -> MetricResult`

- [compare_bodies()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/body_similarity.py:182>) — Code-এর দায়িত্ব-বর্ণনা: All four metrics, each independently. Never raises.
  - Signature: `async compare_bodies(claim_body: str \| None, source_body: str \| None, embedder) -> BodySimilarityResult`

### backend/app/features/verification/analysis/decisions.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/decisions.py>) · 169 lines

Source correspondence, search adequacy ও date comparison-এর pure decision functions।

**Class [Metric](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/decisions.py:24>)** · inherits `plain class`

দায়িত্ব/contract: A score plus the state that explains it.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `state` | `MetricState` | MetricState.UNAVAILABLE |
| `value` | `float \| None` | None |

- [Metric.ok()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/decisions.py:31>) — Metric state COMPUTED এবং value উপস্থিত কি না জানায়।
  - Signature: `ok(self) -> bool`

**Class [CorrespondenceInputs](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/decisions.py:36>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `headline_title_similarity` | `Metric` | field(default_factory=Metric) |
| `title_keyword_coverage` | `Metric` | field(default_factory=Metric) |
| `passage_keyword_coverage` | `Metric` | field(default_factory=Metric) |

**Class [Correspondence](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/decisions.py:43>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `level` | `str` | required / instance-assigned |
| `basis` | `list[str]` | field(default_factory=list) |

- [assess_correspondence()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/decisions.py:48>) — Code-এর দায়িত্ব-বর্ণনা: Is the retrieved article plausibly THE report the claim is about? Correspondence is a separate decision from headline equivalence: an altered headline can still correspond to the report it distorts. A shared topic, person or country is not enough - apart from a near- identical headline/title (similarity >= `corr_headline_sim_alone`), correspondence always needs lexical support: the claim's own keywords in the source title, or in the source passages that discuss the claim.
  - Signature: `assess_correspondence(inp: CorrespondenceInputs, t) -> Correspondence`

- [decide_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/decisions.py:93>) — Code-এর দায়িত্ব-বর্ণনা: CONFIRMED needs a corresponding report; NOT_FOUND needs an ADEQUATE search that came up without one; everything else is INCOMPLETE (a failed search is never reported as a confident NOT_FOUND). `blocked_match` names a search result whose title corresponds to the claim better than anything that was read, but whose page could not be fetched (typically an anti-bot wall). The likely report was never read, so neither absence nor a weaker stand-in is reported: INCOMPLETE.
  - Signature: `decide_source(*, has_evidence: bool, search_adequate: bool \| None, retrieval_failed: bool, correspondence: Correspondence \| None, blocked_match: str \| None=None) -> tuple[SourceStatus, list[str]]`

- [decide_date()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/decisions.py:140>) — Source confirmation ও দুই publication day অনুযায়ী matched/mismatched/incomplete/absent date finding দেয়।
  - Signature: `decide_date(claimed: date \| None, article_date: date \| None, *, source_confirmed: bool) -> DateStatus \| None`

- [search_adequate()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/decisions.py:153>) — Code-এর দায়িত্ব-বর্ণনা: `completed` = SUCCESS + SUCCESS_EMPTY + CACHED provider calls.
  - Signature: `search_adequate(attempted: int, completed: int, *, min_calls: int, min_ratio: float) -> bool`

- [correspondence_strength()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/decisions.py:166>) — Code-এর দায়িত্ব-বর্ণনা: Mean of the available correspondence measurements (0.0 when none).
  - Signature: `correspondence_strength(values: list[float \| None]) -> float`

### backend/app/features/verification/analysis/entities.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/entities.py>) · 147 lines

Normalized/stemmed entity keys; source mention/text-এর সঙ্গে claimed named entity match।

- [entity_key()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/entities.py:36>) — Code-এর দায়িত্ব-বর্ণনা: Normalised, stemmed token tuple used for every entity comparison.
  - Signature: `entity_key(text: str) -> tuple[str, ...]`

**Class [EntityMention](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/entities.py:48>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `text` | `str` | required / instance-assigned |
| `type` | `str` | required / instance-assigned |

- [EntityMention.key()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/entities.py:53>) — Entity mention-এর normalized matching key দেয়।
  - Signature: `key(self) -> tuple[str, ...]`

**Class [EntityMatch](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/entities.py:57>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `claimed` | `str` | required / instance-assigned |
| `type` | `str` | required / instance-assigned |
| `status` | `str` | required / instance-assigned |
| `matched_to` | `str \| None` | None |

- [EntityMatch.matched()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/entities.py:64>) — Entity matching outcome positive কি না জানায়।
  - Signature: `matched(self) -> bool`

- [_contains()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/entities.py:67>) — Token-sequence/window অথবা SQL substring matching-এর local helper; সংশ্লিষ্ট class/file অনুযায়ী ব্যবহার হয়।
  - Signature: `_contains(seq: tuple[str, ...], sub: tuple[str, ...]) -> bool`

- [match_entity()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/entities.py:73>) — Code-এর দায়িত্ব-বর্ণনা: Match one claimed entity against evidence entities and evidence text.
  - Signature: `match_entity(claimed: EntityMention, evidence_mentions: list[EntityMention], evidence_token_keys: tuple[str, ...]) -> EntityMatch`

- [_windows()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/entities.py:130>) — Token-sequence/window অথবা SQL substring matching-এর local helper; সংশ্লিষ্ট class/file অনুযায়ী ব্যবহার হয়।
  - Signature: `_windows(tokens: tuple[str, ...], max_n: int)`

- [mentions_in_sentence()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/entities.py:138>) — Code-এর দায়িত্ব-বর্ণনা: Mentions whose normalised token sequence occurs in `sentence`.
  - Signature: `mentions_in_sentence(sentence: str, mentions: list[EntityMention]) -> list[EntityMention]`

### backend/app/features/verification/analysis/headline_comparison.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/headline_comparison.py>) · 299 lines

Exact/same-word/material-difference/NLI+embedding evidence দিয়ে headline-title verdict।

- [exact_match_key()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/headline_comparison.py:79>) — Code-এর দায়িত্ব-বর্ণনা: The ONLY normalisation applied before the exact-match shortcut (see module docstring). Internal punctuation, quotes, digits and words are untouched.
  - Signature: `exact_match_key(text: str) -> str`

- [is_exact_match()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/headline_comparison.py:89>) — Conservative exact-match normalization-এর পরে headline/title সমান কি না দেখে।
  - Signature: `is_exact_match(claim_headline: str, source_title: str) -> bool`

**Class [SemanticAssessment](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/headline_comparison.py:95>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `available` | `bool` | required / instance-assigned |
| `entailment_title_to_claim` | `float \| None` | None |
| `contradiction_title_to_claim` | `float \| None` | None |
| `entailment_claim_to_title` | `float \| None` | None |
| `contradiction_claim_to_title` | `float \| None` | None |
| `embedding_cosine` | `float \| None` | None |
| `reason` | `str \| None` | None |

- [SemanticAssessment.equivalent()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/headline_comparison.py:105>) — NLI entailment/contradiction ও embedding thresholds মিলে semantic equivalence হয়েছে কি না জানায়।
  - Signature: `equivalent(self) -> bool`

- [SemanticAssessment.to_dict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/headline_comparison.py:114>) — এই result/value object-এর serializable dictionary representation দেয়।
  - Signature: `to_dict(self) -> dict`

- [SemanticAssessment.to_dict.r()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/headline_comparison.py:115>) — Present numeric score display precision-এ round করে; None অক্ষুণ্ণ রাখে।
  - Signature: `r(v: float \| None) -> float \| None`

**Class [HeadlineComparison](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/headline_comparison.py:130>)** · inherits `plain class`

দায়িত্ব/contract: Outcome of one headline-vs-title comparison. `verdict` is MATCHED, ALTERED or None; `status` explains a missing verdict.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `status` | `HeadlineCheckStatus` | required / instance-assigned |
| `verdict` | `ContentStatus \| None` | required / instance-assigned |
| `reason` | `str` | required / instance-assigned |
| `exact_match` | `bool` | False |
| `basis` | `str` | 'none' |
| `differences` | `list[MaterialDifference]` | field(default_factory=list) |
| `semantic` | `SemanticAssessment \| None` | None |
| `ner_available` | `bool` | False |

**Class [HeadlineComparator](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/headline_comparison.py:144>)** · inherits `plain class`

দায়িত্ব/contract: Compares a claim headline with a source title using the already-loaded local NLI, embedding and NER services (no third-party API).

- [HeadlineComparator.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/headline_comparison.py:148>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, nli_service, embedding_service, ner_service=None) -> None`

- [HeadlineComparator.compare()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/headline_comparison.py:153>) — Headline/title exact match, deterministic differences, NER ও semantic assessment একত্রে চালায়।
  - Signature: `async compare(self, claim_headline: str, source_title: str \| None) -> HeadlineComparison`

- [HeadlineComparator._decide()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/headline_comparison.py:191>) — Material differences/positive semantic evidence অনুযায়ী headline verdict অথবা no-verdict state বেছে নেয়।
  - Signature: `_decide(headline: str, title: str, differences: list[MaterialDifference], semantic: SemanticAssessment) -> HeadlineComparison`

- [HeadlineComparator._semantic()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/headline_comparison.py:258>) — Title→claim ও claim→title NLI এবং supporting embedding cosine বের করে।
  - Signature: `async _semantic(self, headline: str, title: str) -> SemanticAssessment`

- [HeadlineComparator._mentions()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/headline_comparison.py:289>) — দুই headline-এর typed NER mentions ও availability নেয়।
  - Signature: `async _mentions(self, headline: str, title: str) -> tuple[list[EntityMention], list[EntityMention], bool]`

### backend/app/features/verification/analysis/keywords.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/keywords.py>) · 122 lines

Meaningful claim keyword units ও weighted evidence coverage; missing/empty/computed states পৃথক।

**Class [KeywordUnit](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/keywords.py:34>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `text` | `str` | required / instance-assigned |
| `weight` | `float` | required / instance-assigned |
| `kind` | `str` | required / instance-assigned |

**Class [KeywordCoverage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/keywords.py:40>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `state` | `MetricState` | required / instance-assigned |
| `value` | `float \| None` | required / instance-assigned |
| `units` | `list[KeywordUnit]` | field(default_factory=list) |
| `matched` | `list[str]` | field(default_factory=list) |
| `unmatched` | `list[str]` | field(default_factory=list) |
| `reason` | `str \| None` | None |

- [extract_claim_units()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/keywords.py:48>) — Code-এর দায়িত্ব-বর্ণনা: Deterministic keyword units for a claim: every content word once.
  - Signature: `extract_claim_units(text: str) -> list[KeywordUnit]`

- [evidence_keys()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/keywords.py:68>) — Evidence text-এর normalized/stemmed keyword matching keys তৈরি করে।
  - Signature: `evidence_keys(evidence_text: str) -> set[str]`

- [keyword_coverage()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/keywords.py:83>) — Code-এর দায়িত্ব-বর্ণনা: Weighted fraction of the claim's keyword units found in the evidence. States: COMPUTED (value may be a genuine 0.0), EMPTY (claim yielded no applicable units), UNAVAILABLE (no evidence text / utility failure).
  - Signature: `keyword_coverage(claim_text: str, evidence_text: str) -> KeywordCoverage`

### backend/app/features/verification/analysis/material_differences.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py>) · 467 lines

Headline-এর সংখ্যাগত/তারিখ/negation/modality/scope/role/attribution/entity পরিবর্তন ধরার deterministic rules।

**Class [MaterialDifference](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:46>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `kind` | `str` | required / instance-assigned |
| `detail` | `str` | required / instance-assigned |
| `claim_text` | `str` | required / instance-assigned |
| `source_text` | `str` | required / instance-assigned |
| `meta` | `dict[str, str]` | field(default_factory=dict) |

- [_n()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:54>) — Rule-based comparison-এর প্রয়োজনীয় normalized text form দেয়।
  - Signature: `_n(text: str) -> str`

- [_norm_words()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:58>) — Code-এর দায়িত্ব-বর্ণনা: Word lists in exactly the form `tokenize` produces for compared text.
  - Signature: `_norm_words(*words: str) -> frozenset[str]`

- [_any_of()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:63>) — Specified word/marker alternatives-এর কোনোটি উপস্থিত কি না পরীক্ষা করে।
  - Signature: `_any_of(*words: str) -> str`

- [content_units()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:69>) — Meaningful comparison words/stems সংগ্রহ করে।
  - Signature: `content_units(text: str)`

- [coverage()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:73>) — Claim content-এর কতটা source-side content-এ আছে তা মাপে।
  - Signature: `coverage(units, keys: set[str]) -> float`

- [unmatched_content()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:79>) — Code-এর দায়িত্ব-বর্ণনা: Claim content words (stem-aware) that do not occur in the source.
  - Signature: `unmatched_content(claim: str, source: str) -> list[str]`

- [same_word_sequence()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:85>) — Code-এর দায়িত্ব-বর্ণনা: Same words in the same order — only punctuation/spacing differs.
  - Signature: `same_word_sequence(a: str, b: str) -> bool`

- [_is_negation()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:128>) — Token negation বা negated verb marker কি না শনাক্ত করে।
  - Signature: `_is_negation(tok: str, prev: str='') -> bool`

- [polarity()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:134>) — Code-এর দায়িত্ব-বর্ণনা: True when the text is negated (an odd number of negations).
  - Signature: `polarity(text: str) -> bool`

- [_same_predicate()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:140>) — Code-এর দায়িত্ব-বর্ণনা: A fused negation hides its verb (কমায়নি). Only compare polarity when the other side uses the same verb root (কমিয়েছে), so 'did not raise' is never read as the negation of 'reduced'.
  - Signature: `_same_predicate(a: str, b: str) -> bool`

- [_is_future()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:154>) — Future/planned-action marker শনাক্ত করে।
  - Signature: `_is_future(tok: str) -> bool`

- [modality()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:163>) — Code-এর দায়িত্ব-বর্ণনা: COMPLETED | NOT_COMPLETED (planned, possible, future) | UNKNOWN.
  - Signature: `modality(text: str) -> str`

- [qualifier_groups()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:173>) — Scope/degree/qualification marker groups বের করে।
  - Signature: `qualifier_groups(text: str) -> set[str]`

- [_scope_conflict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:178>) — Headline ও title-এর quantity/scope qualifiers-এর গুরুত্বপূর্ণ বিরোধ দেখে।
  - Signature: `_scope_conflict(a: str, b: str) -> bool`

- [_clauses()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:187>) — Comparison-এর জন্য text-কে clause fragments-এ ভাগ করে।
  - Signature: `_clauses(text: str) -> list[str]`

- [_clause_alignment()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:191>) — Code-এর দায়িত্ব-বর্ণনা: Pair each claim clause with the source clause that discusses it: (claim_clause, source_clause, ambiguous). `ambiguous` when equally aligned source clauses disagree in polarity or modality.
  - Signature: `_clause_alignment(claim: str, source: str)`

- [_roles()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:220>) — Clause/quantity-এর subject/object/referent roles নির্ধারণের helper।
  - Signature: `_roles(text: str) -> dict[str, str]`

- [role_swap()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:239>) — Code-এর দায়িত্ব-বর্ণনা: (word that became the object, word that became the subject) when the headline reverses who did what to whom relative to the title.
  - Signature: `role_swap(claim: str, source: str) -> tuple[str, str] \| None`

**Class [Quantity](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:286>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `value` | `float` | required / instance-assigned |
| `unit` | `str` | required / instance-assigned |
| `role` | `str` | required / instance-assigned |
| `surface` | `str` | required / instance-assigned |

- [_role_in()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:293>) — Clause/quantity-এর subject/object/referent roles নির্ধারণের helper।
  - Signature: `_role_in(tokens: list[str]) -> list[str]`

- [quantities()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:297>) — Code-এর দায়িত্ব-বর্ণনা: Numbers with unit and (when clear) referent: ৫ জন নিহত, ২০ শতাংশ.
  - Signature: `quantities(text: str) -> list[Quantity]`

- [_same_value()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:317>) — Quantity-এর numeric value/unit/referent তুলনাযোগ্য বা সমান কি না দেখে।
  - Signature: `_same_value(a: Quantity, b: Quantity) -> bool`

- [_compatible()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:321>) — Quantity-এর numeric value/unit/referent তুলনাযোগ্য বা সমান কি না দেখে।
  - Signature: `_compatible(a: Quantity, b: Quantity) -> bool`

- [_bangla_digits()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:327>) — Number/date text-এর বাংলা digit representation সামলায়।
  - Signature: `_bangla_digits(text: str) -> str`

- [date_words()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:356>) — Headline text-এর date/month expressions সংগ্রহ করে।
  - Signature: `date_words(text: str) -> set[str]`

- [find_material_differences()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:362>) — Code-এর দায়িত্ব-বর্ণনা: Every concrete meaning change between `claim` and `source`.
  - Signature: `find_material_differences(claim: str, source: str, *, claim_mentions: list[EntityMention] \| None=None, source_mentions: list[EntityMention] \| None=None, ner_available: bool=False) -> list[MaterialDifference]`

- [find_material_differences.add()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/material_differences.py:373>) — Parent function-এর local collection-এ validated/nonduplicate query বা difference যোগ করে।
  - Signature: `add(kind: str, detail: str, claim_text: str=claim, source_text: str=source, **meta: str) -> None`

### backend/app/features/verification/analysis/passages.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/passages.py>) · 71 lines

Claim keyword coverage দিয়ে relevant sentence windows select/merge।

**Class [Passage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/passages.py:18>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `text` | `str` | required / instance-assigned |
| `score` | `float` | required / instance-assigned |
| `first_sentence` | `int` | required / instance-assigned |
| `last_sentence` | `int` | required / instance-assigned |
| `location` | `str` | 'body' |

- [select_relevant_passages()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/passages.py:25>) — Code-এর দায়িত্ব-বর্ণনা: Top sentences by claim-keyword coverage, each widened by `context_window` neighbouring sentences, overlapping windows merged.
  - Signature: `select_relevant_passages(claim_text: str, article_body: str \| None, *, max_passages: int=3, context_window: int=1, min_score: float=0.25, max_chars: int=600) -> list[Passage]`

### backend/app/features/verification/analysis/text.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/text.py>) · 174 lines

Analysis-specific normalization/tokenization/light stemming/chunking; meaning-bearing negation/qualifier রাখে।

- [normalize_for_match()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/text.py:68>) — Code-এর দায়িত্ব-বর্ণনা: NFC, Bangla punctuation/zero-width cleanup, digits -> ASCII, casefold.
  - Signature: `normalize_for_match(text: str) -> str`

- [tokenize()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/text.py:79>) — Code-এর দায়িত্ব-বর্ণনা: Normalised tokens in order (no stopword removal).
  - Signature: `tokenize(text: str) -> list[str]`

- [light_stem()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/text.py:84>) — Code-এর দায়িত্ব-বর্ণনা: Conservative inflection stripping, applied identically to both sides. Strips case/plural markers only while at least _MIN_STEM code points remain. This is for *matching* only; it is not linguistic stemming.
  - Signature: `light_stem(token: str) -> str`

- [is_negation_token()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/text.py:109>) — Token negation বা negated verb marker কি না শনাক্ত করে।
  - Signature: `is_negation_token(token: str) -> bool`

- [is_qualifier_token()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/text.py:115>) — Token meaning-bearing qualifier অথবা numeric unit কি না চিহ্নিত করে।
  - Signature: `is_qualifier_token(token: str) -> bool`

- [is_number_token()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/text.py:119>) — Token meaning-bearing qualifier অথবা numeric unit কি না চিহ্নিত করে।
  - Signature: `is_number_token(token: str) -> bool`

- [content_tokens()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/text.py:123>) — Code-এর দায়িত্ব-বর্ণনা: Tokens that carry claim content: stopwords dropped, but negation and qualifier words are RETAINED (they are meaning-bearing in content checks even though retrieval would filter them).
  - Signature: `content_tokens(text: str) -> list[str]`

- [split_sentences()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/text.py:136>) — বাংলা/English punctuation অনুযায়ী sentence ভাগ করে।
  - Signature: `split_sentences(text: str, *, min_len: int=8) -> list[str]`

- [chunk_text()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/analysis/text.py:143>) — Code-এর দায়িত্ব-বর্ণনা: Group consecutive sentences into chunks of at most `max_chars`. Nothing is dropped for being long: a long body becomes many chunks. Returns (chunks, truncated) where `truncated` is True only if the `max_chunks` safety cap had to drop trailing text — callers must then treat the body comparison as partial.
  - Signature: `chunk_text(text: str, *, max_chars: int=450, max_chunks: int=120) -> tuple[list[str], bool]`

### backend/app/features/verification/headline_status.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/headline_status.py>) · 62 lines

Stored MATCHED/ALTERED থেকে EXACT_MATCHED/MEANING_PRESERVED/ALTERED display distinction।

- [derive_headline_status()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/headline_status.py:25>) — Stored content verdict/exact-match evidence থেকে display-level headline status বানায়।
  - Signature: `derive_headline_status(content_status: ContentStatus \| str \| None, *, exact_match: bool \| None=None, basis: str \| None=None, claim_headline: str \| None=None, source_title: str \| None=None) -> HeadlineAlterationStatus \| None`

- [headline_status_for_result()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/headline_status.py:45>) — Code-এর দায়িত্ব-বর্ণনা: The display status for a stored VerificationResult (AI preliminary finding). Legacy rows (no headline_check_status) have no headline verdict.
  - Signature: `headline_status_for_result(result, *, claim_headline: str \| None=None) -> HeadlineAlterationStatus \| None`

### backend/app/features/verification/job_repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/job_repository.py>) · 127 lines

Durable job enqueue/claim/heartbeat/done/retry/fail; PostgreSQL row locking।

- [_now()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/job_repository.py:12>) — Timezone-aware বর্তমান timestamp দেয়।
  - Signature: `_now() -> datetime`

**Class [VerificationJobRepository](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/job_repository.py:16>)** · inherits `plain class`

দায়িত্ব/contract: Queue operations for `verification_jobs`. `claim_next` uses ``FOR UPDATE SKIP LOCKED`` so several workers (or processes) never take the same job, and treats a RUNNING job whose ``locked_at`` is older than ``stale_after`` as abandoned — that is how work interrupted by a crash or restart is recovered.

- [VerificationJobRepository.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/job_repository.py:25>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, session: AsyncSession) -> None`

- [VerificationJobRepository.get_by_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/job_repository.py:28>) — Submission ID-র সঙ্গে যুক্ত result/record(s) query করে।
  - Signature: `async get_by_submission(self, submission_id: uuid.UUID) -> VerificationJob \| None`

- [VerificationJobRepository.enqueue()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/job_repository.py:35>) — Code-এর দায়িত্ব-বর্ণনা: Idempotent: one job per submission.
  - Signature: `async enqueue(self, submission_id: uuid.UUID, kind: str, *, payload: dict \| None=None) -> VerificationJob`

- [VerificationJobRepository.claim_next()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/job_repository.py:54>) — Code-এর দায়িত্ব-বর্ণনা: The oldest claimable job, optionally restricted to (or excluding) some job kinds - the worker runs one lane per kind group.
  - Signature: `async claim_next(self, worker_id: str, *, stale_after_s: float, kinds: tuple[str, ...] \| None=None, exclude_kinds: tuple[str, ...] \| None=None) -> VerificationJob \| None`

- [VerificationJobRepository.heartbeat()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/job_repository.py:95>) — Running job-এর activity timestamp নিয়মিত refresh করে।
  - Signature: `async heartbeat(self, job_id: uuid.UUID) -> None`

- [VerificationJobRepository.mark_done()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/job_repository.py:100>) — Job DONE করে completion timestamp/lock state update করে।
  - Signature: `async mark_done(self, job_id: uuid.UUID) -> None`

- [VerificationJobRepository.release_or_fail()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/job_repository.py:107>) — Code-এর দায়িত্ব-বর্ণনা: Retry (back to QUEUED) unless permanent or out of attempts. Returns True when the job is now terminally FAILED.
  - Signature: `async release_or_fail(self, job_id: uuid.UUID, error: str, *, permanent: bool) -> bool`

### backend/app/features/verification/jobs.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py>) · 406 lines

Shared job dependencies, তিন ধরনের job handler এবং bounded two-lane background worker।

**Class [JobDeps](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:61>)** · inherits `plain class`

দায়িত্ব/contract: Process-wide services the job needs (taken from ``app.state``).

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `cache_service` | `CacheService` | required / instance-assigned |
| `embedding_service` | `EmbeddingService` | required / instance-assigned |
| `ner_service` | `NERService` | required / instance-assigned |
| `nli_service` | `NLIService` | required / instance-assigned |
| `http_client` | `httpx.AsyncClient` | required / instance-assigned |
| `photocard_storage` | `PhotoCardStorageService \| None` | None |
| `multimodal_loader` | `Any` | None |
| `multimodal_storage` | `Any` | None |

- [JobDeps.from_app_state()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:74>) — Shared app resources দিয়ে JobDeps value object বানায়।
  - Signature: `from_app_state(cls, state: Any) -> 'JobDeps'`

- [execute_job()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:87>) — Code-এর দায়িত্ব-বর্ণনা: Run one job body in its own session and commit on success.
  - Signature: `async execute_job(*, kind: str, submission_id: uuid.UUID, payload: dict, deps: JobDeps, session_factory: Callable[[], Any]=AsyncSessionLocal) -> None`

**Class [_JobContext](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:134>)** · inherits `plain class`

দায়িত্ব/contract: What one job handler works with: the job's own session, the loaded submission and the repositories bound to that session.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `session` | `Any` | required / instance-assigned |
| `submission_id` | `uuid.UUID` | required / instance-assigned |
| `submission` | `Any` | required / instance-assigned |
| `payload` | `dict` | required / instance-assigned |
| `deps` | `JobDeps` | required / instance-assigned |
| `submission_repo` | `SubmissionRepository` | required / instance-assigned |
| `result_repo` | `ResultRepository` | required / instance-assigned |
| `article_repo` | `RetrievedArticleRepository` | required / instance-assigned |
| `source_repo` | `SourceRepository` | required / instance-assigned |

- [_mark_verifying()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:149>) — Code-এর দায়িত্ব-বর্ণনা: Visible PROCESSING/VERIFYING before the slow part starts.
  - Signature: `async _mark_verifying(ctx: _JobContext) -> None`

- [_run_multimodal()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:156>) — Stored job kind অনুযায়ী সংশ্লিষ্ট service entry point চালায়।
  - Signature: `async _run_multimodal(ctx: _JobContext) -> None`

- [_run_photocard()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:169>) — Stored job kind অনুযায়ী সংশ্লিষ্ট service entry point চালায়।
  - Signature: `async _run_photocard(ctx: _JobContext) -> None`

- [_run_source_based()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:188>) — Stored job kind অনুযায়ী সংশ্লিষ্ট service entry point চালায়।
  - Signature: `async _run_source_based(ctx: _JobContext) -> None`

**Class [_Lane](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:216>)** · inherits `plain class`

দায়িত্ব/contract: One independently bounded queue consumer. Photo cards get their own lane: their Gemini step can wait out retries for minutes, and must never hold the slots that text and text & image jobs need (nor vice versa).

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `name` | `str` | required / instance-assigned |
| `concurrency` | `int` | required / instance-assigned |
| `kinds` | `tuple[str, ...] \| None` | None |
| `exclude_kinds` | `tuple[str, ...] \| None` | None |
| `slots` | `asyncio.Semaphore \| None` | None |
| `wake` | `asyncio.Event \| None` | None |
| `task` | `asyncio.Task \| None` | None |

**Class [VerificationJobWorker](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:230>)** · inherits `plain class`

দায়িত্ব/contract: Drains ``verification_jobs`` with bounded concurrency, in two lanes: photo cards, and everything else.

- [VerificationJobWorker.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:234>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, deps: JobDeps, *, session_factory: Callable[[], Any]=AsyncSessionLocal, concurrency: int=2, photocard_concurrency: int=4, poll_interval_s: float=5.0, stale_after_s: float=120.0, heartbeat_interval_s: float=30.0, runner: Callable[..., Any] \| None=None) -> None`

- [VerificationJobWorker.start()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:262>) — Background worker-এর asynchronous loop task শুরু করে।
  - Signature: `start(self) -> None`

- [VerificationJobWorker.stop()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:273>) — Worker/task cancellation ও shutdown অপেক্ষা সম্পন্ন করে।
  - Signature: `async stop(self) -> None`

- [VerificationJobWorker.wake()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:286>) — Code-এর দায়িত্ব-বর্ণনা: Poke the worker after enqueueing; purely a latency optimisation.
  - Signature: `wake(self) -> None`

- [VerificationJobWorker._run_loop()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:294>) — এই worker-এর recurring processing/poll/sweep loop চালায়।
  - Signature: `async _run_loop(self, lane: _Lane) -> None`

- [VerificationJobWorker._claim()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:318>) — নিজ lane-এর next queued/stale job transactionally claim করে।
  - Signature: `async _claim(self, lane: _Lane) -> dict \| None`

- [VerificationJobWorker._run_job()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:338>) — Claimed job execute করে heartbeat ও success/failure handling পরিচালনা করে।
  - Signature: `async _run_job(self, job: dict, lane: _Lane) -> None`

- [VerificationJobWorker._heartbeat()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:366>) — Running job-এর activity timestamp নিয়মিত refresh করে।
  - Signature: `async _heartbeat(self, job_id: uuid.UUID) -> None`

- [VerificationJobWorker._fail()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/jobs.py:378>) — Code-এর দায়িত্ব-বর্ণনা: Retry or terminally fail. A terminal failure marks the submission FAILED (with a user-presentable reason) and notifies the owner exactly once. Notification trouble never changes the failure itself.
  - Signature: `async _fail(self, job: dict, reason: str, *, permanent: bool, error: str \| None=None) -> None`

### backend/app/features/verification/models.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/models.py>) · 270 lines

Feature `verification`। SQLAlchemy ORM entities: নিচে exact table, fields ও foreign-key/constraint declarations দেওয়া আছে।

**Class [VerificationResult](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/models.py:18>)** · inherits `UUIDMixin, TimestampMixin, ReprMixin, Base` · table `verification_results`

দায়িত্ব/contract: Stored source-based or photo-card analysis for one submission.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `Mapped[uuid.UUID]` | mapped_column(UUID(as_uuid=True), ForeignKey('submissions.id', ondelete='CASCADE'), unique=True, nullable=False, index=True) |
| `ai_preliminary_label` | `Mapped[str \| None]` | mapped_column(String(20), nullable=True) |
| `source_status` | `Mapped[SourceStatus \| None]` | mapped_column(Enum(SourceStatus, name='source_status_enum', create_type=True), nullable=True, index=True, comment="The AI pipeline's own call — an immutable snapshot, written once by the verification pipeline and never overwritten by expert review. See final_source_status for the expert-finalized value, which may differ from this one.") |
| `content_status` | `Mapped[ContentStatus \| None]` | mapped_column(Enum(ContentStatus, name='content_status_enum', create_type=True), nullable=True, comment="Headline Alteration verdict (MATCHED \| ALTERED): the claim headline vs the selected source TITLE only. The AI's own call — immutable, see source_status. NULL when no verdict was reached; headline_check_status says why.") |
| `headline_check_status` | `Mapped[str \| None]` | mapped_column(String(32), nullable=True, comment='HeadlineCheckStatus: COMPLETED \| SOURCE_NOT_FOUND \| SOURCE_CHECK_INCOMPLETE \| SOURCE_TITLE_MISSING \| MODEL_UNAVAILABLE \| UNDETERMINED. Processing status of the headline check, separate from the verdict.') |
| `headline_exact_match` | `Mapped[bool \| None]` | mapped_column(Boolean, nullable=True, comment='True when the headline verdict came from an exact match with the source title.') |
| `body_comparison_status` | `Mapped[str \| None]` | mapped_column(String(24), nullable=True, comment='BodyComparisonStatus: COMPUTED \| SKIPPED \| UNAVAILABLE. The four body similarity scores themselves live in analysis_details.body_similarity.') |
| `date_status` | `Mapped[DateStatus \| None]` | mapped_column(Enum(DateStatus, name='date_status_enum', create_type=True), nullable=True, comment="The AI's own call — immutable, see source_status. Only set when both dates are known; independent of content_status — a mismatch here does not imply false content.") |
| `final_source_status` | `Mapped[SourceStatus \| None]` | mapped_column(Enum(SourceStatus, name='source_status_enum', create_type=False), nullable=True, comment='Expert-finalized Source verdict — NULL until finalized. Written only by ExpertReviewService.') |
| `final_content_status` | `Mapped[ContentStatus \| None]` | mapped_column(Enum(ContentStatus, name='content_status_enum', create_type=False), nullable=True, comment='Expert-finalized Headline Alteration verdict — NULL until finalized, or if final_source_status is NOT_FOUND.') |
| `final_date_status` | `Mapped[DateStatus \| None]` | mapped_column(Enum(DateStatus, name='date_status_enum', create_type=False), nullable=True, comment='Expert-finalized Date verdict — NULL until finalized, or if final_source_status is NOT_FOUND.') |
| `overall_verdict` | `Mapped[OverallVerdict \| None]` | mapped_column(Enum(OverallVerdict, name='overall_verdict_enum', create_type=False), nullable=True, index=True, comment="Expert-finalized Overall verdict (Fake/Real/Misleading/Altered) — NULL until expert review finalizes this claim. Functionally the 'final_overall_verdict' of this fields group — named before final_source/content/date_status existed. Written only by ExpertReviewService, never by the AI pipeline itself.") |
| `finalized_at` | `Mapped[datetime \| None]` | mapped_column(DateTime(timezone=True), nullable=True, comment='When expert review finalized this claim; NULL until then.') |
| `ai_consensus_label` | `Mapped[ExpertVerdict \| None]` | mapped_column(Enum(ExpertVerdict, name='verification_label_enum', create_type=False), nullable=True, index=True, comment='LEGACY / NO LONGER WRITTEN. Formerly a single-category projection of (source_status, content_status) onto TRUE/FALSE/PARTIALLY_TRUE. The automated system casts no overall truth vote, so new rows leave this NULL; historical values are kept, never erased. See verdict_compat.py.') |
| `confidence` | `Mapped[float \| None]` | mapped_column(Float, nullable=True) |
| `reasoning` | `Mapped[str \| None]` | mapped_column(Text, nullable=True) |
| `top_article_id` | `Mapped[uuid.UUID \| None]` | mapped_column(UUID(as_uuid=True), ForeignKey('retrieved_articles.id', ondelete='SET NULL'), nullable=True) |
| `avg_verification_time_ms` | `Mapped[int \| None]` | mapped_column(Integer, nullable=True) |
| `headline_similarity` | `Mapped[float \| None]` | mapped_column(Float, nullable=True, comment='LaBSE cosine of claim headline vs selected source title (correspondence).') |
| `headline_keyword_coverage` | `Mapped[float \| None]` | mapped_column(Float, nullable=True, comment='Share of claim keywords found in the source title (correspondence).') |
| `passage_keyword_coverage` | `Mapped[float \| None]` | mapped_column(Float, nullable=True, comment='Share of claim keywords found in the title + relevant source passages (correspondence).') |
| `claim_scope` | `Mapped[str \| None]` | mapped_column(String(24), nullable=True, comment='HEADLINE_ONLY \| HEADLINE_WITH_BODY — the scope this result was computed under.') |
| `pipeline_version` | `Mapped[str \| None]` | mapped_column(String(40), nullable=True, comment='VERIFICATION_PIPELINE_VERSION in force when computed. NULL on rows from before the scope-aware rewrite; those are never reused as fresh results.') |
| `analysis_details` | `Mapped[dict \| None]` | mapped_column(JSONB, nullable=True, comment='AnalysisDetails payload: correspondence measurements, search accounting, source basis, Headline Alteration detail, body similarity scores, date analysis and timings. Durable source for result display after the Redis entry expires.') |
| `reused_from_submission_id` | `Mapped[uuid.UUID \| None]` | mapped_column(UUID(as_uuid=True), ForeignKey('submissions.id', ondelete='SET NULL'), nullable=True, comment='Set when this result row is an automated-result copy of an earlier identical verification.') |
| `submission` | `Mapped['Submission']` | relationship('Submission', primaryjoin='VerificationResult.submission_id == Submission.id', viewonly=True, lazy='select') |
| `top_article` | `Mapped['RetrievedArticle \| None']` | relationship('RetrievedArticle', primaryjoin='VerificationResult.top_article_id == RetrievedArticle.id', viewonly=True, lazy='select') |

Database constraints/indexes: `__table_args__ = (CheckConstraint('confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)', name='ck_verification_results_confidence_range'), Index('ix_verification_results_status_created', source_status, content_status, 'created_at'))`

**Class [VerificationJob](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/models.py:224>)** · inherits `UUIDMixin, TimestampMixin, ReprMixin, Base` · table `verification_jobs`

দায়িত্ব/contract: Durable unit of background verification work. The row is written in the same transaction as the accepted submission, so an accepted submission can never exist without its job. A worker claims jobs with ``FOR UPDATE SKIP LOCKED`` and stamps ``locked_at``; a job whose lock has gone stale (process crashed or restarted mid-run) is reclaimed on the next poll. Nothing about execution depends on the browser, polling, or the request that created it.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `Mapped[uuid.UUID]` | mapped_column(UUID(as_uuid=True), ForeignKey('submissions.id', ondelete='CASCADE'), unique=True, nullable=False, index=True) |
| `kind` | `Mapped[str]` | mapped_column(String(20), nullable=False, comment='SOURCE_BASED \| PHOTO_CARD \| MULTIMODAL') |
| `status` | `Mapped[str]` | mapped_column(String(12), nullable=False, default='QUEUED', index=True, comment='QUEUED \| RUNNING \| DONE \| FAILED') |
| `attempts` | `Mapped[int]` | mapped_column(Integer, nullable=False, default=0) |
| `max_attempts` | `Mapped[int]` | mapped_column(Integer, nullable=False, default=3) |
| `locked_at` | `Mapped[datetime \| None]` | mapped_column(DateTime(timezone=True), nullable=True) |
| `locked_by` | `Mapped[str \| None]` | mapped_column(String(64), nullable=True) |
| `finished_at` | `Mapped[datetime \| None]` | mapped_column(DateTime(timezone=True), nullable=True) |
| `last_error` | `Mapped[str \| None]` | mapped_column(Text, nullable=True) |
| `payload` | `Mapped[dict \| None]` | mapped_column(JSONB, nullable=True, comment='Job inputs that are not on the submission row.') |

Database constraints/indexes: `__table_args__ = (Index('ix_verification_jobs_status_created', status, 'created_at'),)`

### backend/app/features/verification/pipeline/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/__init__.py>) · 0 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/verification/pipeline/context.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/context.py>) · 209 lines

PipelineContext shared state এবং PipelineStage interface; request থেকে starting context।

**Class [PipelineContext](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/context.py:21>)** · inherits `plain class`

দায়িত্ব/contract: Shared state passed through the verification stages. Each decision has its own owner: S08 source correspondence -> source_status, analysis.metrics/search/source_basis S09 headline alteration -> content_status (MATCHED | ALTERED | None), headline_check_status, analysis.headline_alteration S10 body similarity -> analysis.body_similarity (measurements only) S11 date verification -> date_status, analysis.date S12 result assembly -> confidence, reasoning, analysis bookkeeping S13 result persistence -> result_id, persisted

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `request_id` | `uuid.UUID` | field(default_factory=uuid.uuid4) |
| `submission_id` | `uuid.UUID \| None` | None |
| `submitter_id` | `uuid.UUID \| None` | None |
| `raw_headline` | `str` | '' |
| `raw_news_body` | `str \| None` | None |
| `raw_claimed_source` | `str` | '' |
| `published_date` | `date \| None` | None |
| `claim_scope` | `ClaimScope` | ClaimScope.HEADLINE_ONLY |
| `normalized_headline` | `str` | '' |
| `normalized_body` | `str \| None` | None |
| `normalized_source` | `str \| None` | None |
| `source_config` | `dict \| None` | None |
| `content_hash` | `str \| None` | None |
| `verification_mode` | `str` | 'CLAIMED_SOURCE' |
| `source_resolution_reason` | `str \| None` | None |
| `verified_scope` | `Any` | None |
| `cache_hit` | `bool` | False |
| `reused_from_submission_id` | `uuid.UUID \| None` | None |
| `search_queries` | `list[tuple[str, str]]` | field(default_factory=list) |
| `claim_keywords` | `list[str]` | field(default_factory=list) |
| `candidate_urls` | `list[CandidateArticleSchema]` | field(default_factory=list) |
| `search_provider_used` | `str \| None` | None |
| `search_attempted` | `int` | 0 |
| `search_errors` | `int` | 0 |
| `search_success` | `int` | 0 |
| `search_success_empty` | `int` | 0 |
| `search_cached` | `int` | 0 |
| `search_skipped` | `int` | 0 |
| `search_redirect_rejected` | `int` | 0 |
| `search_provider_outcomes` | `dict[str, dict[str, int]]` | field(default_factory=dict) |
| `search_adequate` | `bool \| None` | None |
| `fetch_attempted` | `int` | 0 |
| `fetch_errors` | `int` | 0 |
| `extraction_attempted` | `int` | 0 |
| `extraction_errors` | `int` | 0 |
| `fetched_html` | `dict[str, str]` | field(default_factory=dict) |
| `extracted_articles` | `list[RankedArticleSchema]` | field(default_factory=list) |
| `failed_extraction_urls` | `list[str]` | field(default_factory=list) |
| `ranked_articles` | `list[RankedArticleSchema]` | field(default_factory=list) |
| `top_article` | `RankedArticleSchema \| None` | None |
| `analysis` | `AnalysisDetails` | field(default_factory=AnalysisDetails) |
| `source_status` | `SourceStatus \| None` | None |
| `content_status` | `ContentStatus \| None` | None |
| `headline_check_status` | `HeadlineCheckStatus \| None` | None |
| `date_status` | `DateStatus \| None` | None |
| `confidence` | `float` | 0.0 |
| `reasoning` | `str` | '' |
| `result_id` | `uuid.UUID \| None` | None |
| `persisted` | `bool` | False |
| `pipeline_start_time` | `datetime` | field(default_factory=datetime.utcnow) |
| `stage_timings` | `dict[str, int]` | field(default_factory=dict) |
| `stage_errors` | `dict[str, str]` | field(default_factory=dict) |
| `fatal_error` | `str \| None` | None |

- [PipelineContext.is_verified_sources_mode()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/context.py:112>) — Current source resolution VERIFIED_SOURCES mode কি না জানায়।
  - Signature: `is_verified_sources_mode(self) -> bool`

- [PipelineContext.publisher_for_url()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/context.py:115>) — URL/host eligible verified publisher-এর কোনটির অধীনে পড়ে তা resolve করে।
  - Signature: `publisher_for_url(self, url: str \| None) -> str \| None`
  - Source contract: Canonical name of the publisher an evidence URL belongs to.

- [PipelineContext.has_body()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/context.py:125>) — Applicable nonempty body text আছে কি না জানায়।
  - Signature: `has_body(self) -> bool`

- [PipelineContext.has_evidence()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/context.py:129>) — Pipeline-এ usable evidence article আছে কি না জানায়।
  - Signature: `has_evidence(self) -> bool`

- [PipelineContext.retrieval_failed()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/context.py:133>) — Code-এর দায়িত্ব-বর্ণনা: Candidates existed but every page fetch / extraction failed, so the evidence could not be retrieved (as opposed to not existing).
  - Signature: `retrieval_failed(self) -> bool`

- [PipelineContext.source_confirmed()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/context.py:143>) — Current source finding CONFIRMED কি না জানায়।
  - Signature: `source_confirmed(self) -> bool`

- [PipelineContext.has_fatal_error()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/context.py:147>) — Recorded stage error/fatal state সম্পর্কে query দেয়।
  - Signature: `has_fatal_error(self) -> bool`

- [PipelineContext.elapsed_ms()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/context.py:151>) — Pipeline-এর elapsed wall time milliseconds-এ দেয়।
  - Signature: `elapsed_ms(self) -> int`

- [PipelineContext.stage_error_count()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/context.py:156>) — Recorded stage error/fatal state সম্পর্কে query দেয়।
  - Signature: `stage_error_count(self) -> int`

- [PipelineContext.record_stage_error()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/context.py:159>) — একটি stage-এর error/timing context-এ record করে।
  - Signature: `record_stage_error(self, stage_id: PipelineStageID, message: str) -> None`

- [PipelineContext.record_stage_timing()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/context.py:162>) — একটি stage-এর error/timing context-এ record করে।
  - Signature: `record_stage_timing(self, stage_id: PipelineStageID, duration_ms: int) -> None`

**Class [PipelineStage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/context.py:167>)** · inherits `Protocol`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `stage_id` | `PipelineStageID` | required / instance-assigned |

- [PipelineStage.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/context.py:171>) — PipelineStage protocol-এর required method signature; concrete stage implementation কাজটি করে।
  - Signature: `async execute(self, context: PipelineContext) -> PipelineContext`

- [build_context()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/context.py:174>) — Code-এর দায়িত্ব-বর্ণনা: Build the pipeline's starting state for one verification run. `claim_scope` controls what the pipeline treats as "the claim" (see `ClaimScope`). When not given explicitly it is inferred from whether `news_body` was supplied - the right default for a SOURCE_BASED text claim. Photo-card callers must pass `claim_scope=ClaimScope.HEADLINE_ONLY` and no `news_body`: a photo card is verified on its headline alone.
  - Signature: `build_context(headline: str, claimed_source: str \| None, *, news_body: str \| None=None, published_date: date \| None=None, submission_id: uuid.UUID \| None=None, submitter_id: uuid.UUID \| None=None, claim_scope: ClaimScope \| None=None, source_resolution_reason: str \| None=None) -> PipelineContext`

### backend/app/features/verification/pipeline/factory.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/factory.py>) · 89 lines

S01–S13 stage-এর ordered dependency-injected list তৈরি।

- [build_verification_stages()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/factory.py:47>) — প্রয়োজনীয় dependencies দিয়ে ordered pipeline stage instances তৈরি করে।
  - Signature: `build_verification_stages(*, submission_repo: SubmissionRepository, result_repo: ResultRepository, article_repo: RetrievedArticleRepository, source_repo: SourceRepository, cache_service: CacheService, embedding_service: EmbeddingService, ner_service: NERService, nli_service: NLIService, http_client: httpx.AsyncClient) -> list[PipelineStage]`

### backend/app/features/verification/pipeline/orchestrator.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/orchestrator.py>) · 247 lines

Sequential stage execution, cache short-circuit, critical/non-critical errors ও stage timings।

**Class [PipelineOrchestrator](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/orchestrator.py:82>)** · inherits `plain class`

দায়িত্ব/contract: Executes the verification stages (S01-S13) in sequence. Stages are injected (see `factory.build_verification_stages`), so tests can replace any of them without touching the orchestration logic.

- [PipelineOrchestrator.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/orchestrator.py:89>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, stages: list[PipelineStage], submission_repo: SubmissionRepository) -> None`

- [PipelineOrchestrator.run()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/orchestrator.py:99>) — এই worker-এর recurring processing/poll/sweep loop চালায়।
  - Signature: `async run(self, context: PipelineContext) -> PipelineContext`
  - Source contract: Run every stage for one verification request. Raises `PipelineError` when a critical stage fails.

- [PipelineOrchestrator._handle_fatal_failure()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/orchestrator.py:221>) — Code-এর দায়িত্ব-বর্ণনা: Mark the submission as FAILED in the database after a critical stage error. This is a best-effort operation — if the DB call itself fails, the exception is swallowed and only logged, because we are already in an error-handling path. Args: context: The pipeline context with `submission_id` set (may be None if failure occurred in Stage 1 before DB insert).
  - Signature: `async _handle_fatal_failure(self, context: PipelineContext) -> None`

### backend/app/features/verification/pipeline/source_registry.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/source_registry.py>) · 381 lines

Static per-publisher extraction selectors/search URL/article patterns configuration; database source config-এর সঙ্গে ব্যবহৃত fallback knowledge।

**Class [SourceConfig](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/source_registry.py:13>)** · inherits `TypedDict`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `name` | `str` | required / instance-assigned |
| `display_name_en` | `str \| None` | required / instance-assigned |
| `base_url` | `str` | required / instance-assigned |
| `aliases` | `list[str] \| None` | required / instance-assigned |
| `body_selectors` | `list[str] \| None` | required / instance-assigned |
| `title_selectors` | `list[str] \| None` | required / instance-assigned |
| `date_selectors` | `list[str] \| None` | required / instance-assigned |
| `internal_search_url` | `str \| None` | required / instance-assigned |
| `article_url_patterns` | `list[str] \| None` | required / instance-assigned |
| `rss_url` | `str \| None` | required / instance-assigned |
| `js_rendered` | `bool` | required / instance-assigned |
| `search_language` | `str` | required / instance-assigned |
| `language` | `str` | required / instance-assigned |
| `is_active` | `bool` | required / instance-assigned |
| `description` | `str \| None` | required / instance-assigned |

### backend/app/features/verification/pipeline/stages/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/__init__.py>) · 0 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/features/verification/pipeline/stages/cross_encoder_reranker.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/cross_encoder_reranker.py>) · 58 lines

Lazy cross-encoder model দিয়ে candidate relevance tie-break scores; unavailable হলে graceful fallback।

**Class [CrossEncoderReranker](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/cross_encoder_reranker.py:13>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `_model` | `CrossEncoder \| None` | None |

- [CrossEncoderReranker._get_model()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/cross_encoder_reranker.py:25>) — Cross-encoder model lazy-load অথবা loaded model access করে।
  - Signature: `_get_model(cls) -> CrossEncoder \| None`

- [CrossEncoderReranker.model()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/cross_encoder_reranker.py:39>) — Cross-encoder model lazy-load অথবা loaded model access করে।
  - Signature: `model(self) -> CrossEncoder \| None`

- [CrossEncoderReranker.scores()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/cross_encoder_reranker.py:42>) — Code-এর দায়িত্ব-বর্ণনা: Cross-encoder relevance of each article to the claim, or None when the model is unavailable or fails.
  - Signature: `async scores(self, claim_headline: str, articles: List[RankedArticleSchema]) -> List[float] \| None`

### backend/app/features/verification/pipeline/stages/s01_normalizer.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s01_normalizer.py>) · 115 lines

Input normalize, source resolution/scope/config এবং claim identity hash প্রস্তুত।

**Class [InputNormalizerStage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s01_normalizer.py:16>)** · inherits `plain class`

- [InputNormalizerStage.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s01_normalizer.py:20>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, source_repo: SourceRepository) -> None`

- [InputNormalizerStage.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s01_normalizer.py:23>) — Input normalize, source resolution/scope/config এবং claim identity hash প্রস্তুত।
  - Signature: `async execute(self, context: PipelineContext) -> PipelineContext`

### backend/app/features/verification/pipeline/stages/s02_cache_lookup.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s02_cache_lookup.py>) · 157 lines

Redis pointer ও DB reusable result lookup; cache hit context এবং expiry-সহ Redis pointer writing। DB reuse-তে age limit নেই।

**Class [CacheLookupStage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s02_cache_lookup.py:22>)** · inherits `plain class`

দায়িত্ব/contract: S02: reuse an earlier identical, complete verification. Invariants: * Redis stores only a pointer to the submission holding the result; the database row is authoritative and is re-validated on every hit (`reuse.result_is_reusable`), so a deleted or non-reusable result is never served from a leftover pointer. The DB fallback applies the same rules. * A hit never changes `context.submission_id`: the caller's own submission (owner, photo-card image, extraction record) stays the target and the service layer copies the result onto it (`ResultReuseService`). * A claim already checked is not re-run to look for newer evidence. Identity = `context.content_hash` (`hashing.compute_claim_hash`).

- [CacheLookupStage.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s02_cache_lookup.py:41>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, cache_service: CacheService, submission_repo: SubmissionRepository, result_repo: ResultRepository) -> None`

- [CacheLookupStage.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s02_cache_lookup.py:52>) — Redis pointer ও DB reusable result lookup; cache hit context এবং expiry-সহ Redis pointer writing। DB reuse-তে age limit নেই।
  - Signature: `async execute(self, context: PipelineContext) -> PipelineContext`

- [CacheLookupStage._check_redis()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s02_cache_lookup.py:75>) — Redis result-pointer hit database-এ revalidate করে।
  - Signature: `async _check_redis(self, context: PipelineContext, log) -> bool`

- [CacheLookupStage._check_db()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s02_cache_lookup.py:106>) — Claim identity দিয়ে database reusable result fallback খোঁজে।
  - Signature: `async _check_db(self, context: PipelineContext, log) -> bool`

- [CacheLookupStage._populate()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s02_cache_lookup.py:125>) — Code-এর দায়িত্ব-বর্ণনা: Mark the hit. The reused automated result itself is copied by the service layer (`ResultReuseService.materialize`); nothing of it is replayed into this context.
  - Signature: `_populate(context: PipelineContext, source_submission_id: uuid.UUID, result) -> None`

- [CacheLookupStage.write_pointer()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s02_cache_lookup.py:134>) — Code-এর দায়িত্ব-বর্ণনা: Record the submission holding the latest complete result for this identity. TTL is the shorter NOT_FOUND window when applicable.
  - Signature: `async write_pointer(cache_service: CacheService, content_hash: str, submission_id: uuid.UUID, source_status: SourceStatus \| None) -> None`

### backend/app/features/verification/pipeline/stages/s03_query_generator.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s03_query_generator.py>) · 116 lines

Headline/keyword/date/source-restricted queries; verified-source mode-এর bounded phrasings।

**Class [QueryGeneratorStage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s03_query_generator.py:15>)** · inherits `plain class`

দায়িত্ব/contract: Headline, all-keyword, first-3 and first-4 keyword searches; the headline and all-keyword queries are repeated with the user date when one is given. Every query is restricted to the resolved source. Body text is used only for downstream content verification, never for evidence discovery.

- [QueryGeneratorStage.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s03_query_generator.py:25>) — Headline/keyword/date/source-restricted queries; verified-source mode-এর bounded phrasings।
  - Signature: `async execute(self, context: PipelineContext) -> PipelineContext`

- [QueryGeneratorStage.execute.add()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s03_query_generator.py:44>) — Parent function-এর local collection-এ validated/nonduplicate query বা difference যোগ করে।
  - Signature: `add(text: str, kind: QueryType) -> None`

- [QueryGeneratorStage._verified_sources_queries()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s03_query_generator.py:73>) — Code-এর দায়িত্ব-বর্ণনা: Bounded phrasings without a site operator: S04 runs each one once per group of verified domains (``site:a OR site:b ...``), never once per source.
  - Signature: `_verified_sources_queries(self, context: PipelineContext) -> PipelineContext`

- [QueryGeneratorStage._verified_sources_queries.add()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s03_query_generator.py:99>) — Parent function-এর local collection-এ validated/nonduplicate query বা difference যোগ করে।
  - Signature: `add(text: str, kind: QueryType) -> None`

### backend/app/features/verification/pipeline/stages/s04_source_search.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s04_source_search.py>) · 544 lines

Parallel-capable provider calls, domain restriction, URL/title candidates, dedup/cache এবং adequate-search accounting।

**Class [_CallResult](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s04_source_search.py:54>)** · inherits `plain class`

দায়িত্ব/contract: Outcome of ONE provider call. A failed call is FAILED - never a successful empty result - so the caller's accounting cannot mistake an outage for "the source has nothing".

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `provider` | `SearchProvider` | required / instance-assigned |
| `outcome` | `SearchCallOutcome` | required / instance-assigned |
| `candidates` | `list[CandidateArticleSchema]` | field(default_factory=list) |
| `error` | `str \| None` | None |

- [_canonicalise_url()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s04_source_search.py:65>) — Search URL normalize করে tracking/wrapper/duplicate differences কমায়।
  - Signature: `_canonicalise_url(url: str) -> str`

**Class [SourceSearchStage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s04_source_search.py:99>)** · inherits `plain class`

- [SourceSearchStage.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s04_source_search.py:103>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, pygooglenews_client: PyGoogleNewsClient, internal_site_client: InternalSiteSearchClient, cache_service: CacheService) -> None`

- [SourceSearchStage.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s04_source_search.py:113>) — Parallel-capable provider calls, domain restriction, URL/title candidates, dedup/cache এবং adequate-search accounting।
  - Signature: `async execute(self, context: PipelineContext) -> PipelineContext`

- [SourceSearchStage._search_verified_sources()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s04_source_search.py:248>) — Code-এর দায়িত্ব-বর্ণনা: VERIFIED_SOURCES mode: Google only (the internal-site provider is never dispatched and its cached candidates never read), restricted to the active verified publishers. Each phrasing runs once per bounded group of domains, so the call count does not multiply per source.
  - Signature: `async _search_verified_sources(self, context: PipelineContext, log: structlog.BoundLogger) -> PipelineContext`

- [SourceSearchStage._record_outcomes()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s04_source_search.py:350>) — Provider success/empty/failure ও adequacy-এর হিসাব analysis/context-এ রাখে।
  - Signature: `_record_outcomes(context: PipelineContext, results: list[_CallResult]) -> None`

- [SourceSearchStage._should_dispatch()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s04_source_search.py:377>) — Query/provider combination বাস্তবে চালানো উচিত কি না নির্ধারণ করে।
  - Signature: `_should_dispatch(self, provider: SearchProvider, domain: str \| None) -> bool`

- [SourceSearchStage._adapt_query()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s04_source_search.py:389>) — Provider-এর supported search syntax অনুযায়ী query বদলায়।
  - Signature: `_adapt_query(self, provider: SearchProvider, query: str, domain: str \| None) -> str`

- [SourceSearchStage._call_provider()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s04_source_search.py:404>) — এক provider search call চালিয়ে success/failure/cached outcome ও candidates দেয়।
  - Signature: `async _call_provider(self, *, provider_enum: SearchProvider, client, query: str, query_type: str, domain: str \| None, context: PipelineContext, source_config: dict \| None, log: structlog.BoundLogger, cache_namespace: str \| None=None) -> _CallResult`

- [SourceSearchStage._get_cached_search()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s04_source_search.py:508>) — Date/source-aware search cache key দিয়ে ফল পড়ে/লেখে।
  - Signature: `async _get_cached_search(self, provider: str, query_hash: str) -> list \| None`

- [SourceSearchStage._cache_search_result()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s04_source_search.py:516>) — Date/source-aware search cache key দিয়ে ফল পড়ে/লেখে।
  - Signature: `async _cache_search_result(self, provider: str, query_hash: str, urls: list) -> None`

- [_cached_entries()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s04_source_search.py:525>) — Code-এর দায়িত্ব-বর্ণনা: Cached search results: [url, title] pairs, or plain URLs (older entries).
  - Signature: `_cached_entries(cached: list) -> list[tuple[str, str \| None]]`

- [_title_relevance()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s04_source_search.py:536>) — Code-এর দায়িত্ব-বর্ণনা: Share of the claim's keywords (stemmed, compound-aware - the same measure S08 uses) found in a search-result title, ignoring the " - <publisher>" suffix Google adds. None without a title.
  - Signature: `_title_relevance(claim_headline: str, title: str \| None) -> float \| None`

### backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py>) · 415 lines

HTTP HTML fetch, anti-bot detection/cooldown, browser fallback, redirect domain check।

- [_host_cooling_down()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:84>) — Recently anti-bot-blocked host-এর cooldown পড়া/লেখা।
  - Signature: `_host_cooling_down(url: str) -> bool`

- [_mark_walled()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:96>) — Recently anti-bot-blocked host-এর cooldown পড়া/লেখা।
  - Signature: `_mark_walled(url: str) -> None`

- [_visible_text_len()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:107>) — Code-এর দায়িত্ব-বর্ণনা: Length of the text a reader would actually see. Stripping tags alone leaves the *contents* of <script>/<style> behind, which on a challenge page runs to tens of thousands of characters and makes an almost text-free interstitial look like a full article.
  - Signature: `_visible_text_len(html: str) -> int`

- [_is_shell_html()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:118>) — HTML শুধু client-rendered shell কি না চিহ্নিত করে।
  - Signature: `_is_shell_html(html: str) -> bool`

- [_is_bot_wall()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:125>) — Code-এর দায়িত্ব-বর্ণনা: Detect an anti-bot interstitial served with a 200. Cloudflare leaves its challenge script on ordinary pages too, so the marker alone is not enough — a real article would be re-fetched in a browser for nothing. An interstitial also carries almost no text, so require both signals.
  - Signature: `_is_bot_wall(html: str) -> bool`

**Class [_OriginBlocked](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:138>)** · inherits `Exception`

দায়িত্ব/contract: The origin refused the plain HTTP client, not the URL itself. Several outlets (bd-pratidin, kalerkantho, jugantor) sit behind Cloudflare bot protection that rejects httpx on its TLS fingerprint alone — the same URL loads fine in a real browser. Treated as "retry in Playwright" rather than a dead URL, which is what it looked like before.

- [_OriginBlocked.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:147>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, status: int) -> None`

**Class [_RedirectRejected](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:152>)** · inherits `Exception`

দায়িত্ব/contract: The request ended on a host outside the claimed source's registered domains/channels (open redirect, shortener, syndication partner). The page is NOT evidence from the claimed source, so it is dropped - and it is a rejected candidate, not a fetch failure.

- [_RedirectRejected.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:158>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, final_url: str) -> None`

**Class [EvidenceRetrievalStage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:166>)** · inherits `plain class`

- [EvidenceRetrievalStage.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:170>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, http_client: httpx.AsyncClient) -> None`

- [EvidenceRetrievalStage.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:179>) — HTTP HTML fetch, anti-bot detection/cooldown, browser fallback, redirect domain check।
  - Signature: `async execute(self, context: PipelineContext) -> PipelineContext`

- [EvidenceRetrievalStage._fetch_httpx()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:264>) — HTTP client দিয়ে page fetch এবং response/redirect checks করে।
  - Signature: `async _fetch_httpx(self, url: str) -> str \| Exception`

- [EvidenceRetrievalStage._fetch_playwright_batch()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:296>) — HTTP-এ পাওয়া না যাওয়া eligible pages browser দিয়ে batch fetch করে।
  - Signature: `async _fetch_playwright_batch(self, urls: list[str]) -> dict[str, str \| None]`

- [EvidenceRetrievalStage._run_playwright_sync()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:303>) — Browser context/page lifecycle চালায়; search client-এ redirects resolve, retrieval stage-এ article HTML fetch করে।
  - Signature: `_run_playwright_sync(self, urls: list[str]) -> dict[str, str \| None]`

- [EvidenceRetrievalStage._run_playwright_async()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:316>) — Browser context/page lifecycle চালায়; search client-এ redirects resolve, retrieval stage-এ article HTML fetch করে।
  - Signature: `async _run_playwright_async(self, urls: list[str]) -> dict[str, str \| None]`

- [EvidenceRetrievalStage._run_playwright_async.fetch_one()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:357>) — Browser batch-এর একটি article URL fetch করে final host/body/error outcome সংগ্রহ করে।
  - Signature: `async fetch_one(url: str) -> tuple[str, str \| None]`

- [_maybe_deamp()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s05_evidence_retrieval.py:409>) — AMP URL variant-এর matching/canonicalization helper।
  - Signature: `_maybe_deamp(candidate)`

### backend/app/features/verification/pipeline/stages/s06_article_extractor.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s06_article_extractor.py>) · 529 lines

HTML-এর structured metadata/selectors/extraction libraries থেকে clean article ও publication provenance।

**Class [ArticleExtractorStage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s06_article_extractor.py:33>)** · inherits `plain class`

- [ArticleExtractorStage.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s06_article_extractor.py:37>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, cache_service: CacheService) -> None`

- [ArticleExtractorStage.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s06_article_extractor.py:43>) — HTML-এর structured metadata/selectors/extraction libraries থেকে clean article ও publication provenance।
  - Signature: `async execute(self, context: PipelineContext) -> PipelineContext`

- [ArticleExtractorStage.execute.outlet_for()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s06_article_extractor.py:54>) — Evidence URL-এর জন্য উপযুক্ত publisher selector/config resolve করে।
  - Signature: `outlet_for(url: str) -> tuple[str \| None, dict \| None]`

- [ArticleExtractorStage._extract_one()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s06_article_extractor.py:103>) — একটি HTML page থেকে article fields ও publication metadata বের করে।
  - Signature: `_extract_one(self, url: str, html: str, url_to_candidate: dict[str, CandidateArticleSchema], normalized_source: str \| None, source_config: dict \| None) -> RankedArticleSchema`

- [ArticleExtractorStage._find_publication()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s06_article_extractor.py:288>) — Code-এর দায়িত্ব-বর্ণনা: (parsed publication, provenance label). Priority: the outlet's own date selectors, JSON-LD datePublished, publication meta tags, <time itemprop=datePublished>.
  - Signature: `_find_publication(self, soup, config) -> tuple[ParsedPublication \| None, str \| None]`

- [ArticleExtractorStage._build_result()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s06_article_extractor.py:333>) — Extracted fields দিয়ে RankedArticleSchema বানায়।
  - Signature: `_build_result(self, url, title, body, author, published, method, provider, candidate, soup) -> RankedArticleSchema`

- [ArticleExtractorStage._safe_select_one()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s06_article_extractor.py:369>) — Invalid CSS selector-এ পুরো extraction না ভেঙে safe DOM selection করে।
  - Signature: `_safe_select_one(soup: BeautifulSoup, selector: str)`

- [ArticleExtractorStage._safe_select()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s06_article_extractor.py:376>) — Invalid CSS selector-এ পুরো extraction না ভেঙে safe DOM selection করে।
  - Signature: `_safe_select(soup: BeautifulSoup, selector: str)`

- [ArticleExtractorStage._extract_trafilatura()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s06_article_extractor.py:382>) — নির্দিষ্ট extraction library/selector strategy দিয়ে article text/title বের করে।
  - Signature: `_extract_trafilatura(self, url: str, html: str)`

- [ArticleExtractorStage._extract_bs4()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s06_article_extractor.py:406>) — নির্দিষ্ট extraction library/selector strategy দিয়ে article text/title বের করে।
  - Signature: `_extract_bs4(self, url: str, html: str, config: dict \| None)`

- [_iter_ld_items()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s06_article_extractor.py:486>) — Code-এর দায়িত্ব-বর্ণনা: Yield every dict in a JSON-LD payload, including @graph members.
  - Signature: `_iter_ld_items(data)`

- [_headline_variants()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s06_article_extractor.py:504>) — Code-এর দায়িত্ব-বর্ণনা: Headline lines printed next to the title: a kicker/shoulder heading immediately before or after the page's <h1> (e.g. Manab Zamin shows "প্রধানমন্ত্রীর সঙ্গে আবরার ফাহাদের পরিবারের সাক্ষাৎ" above the <h1> "রায় দ্রুত কার্যকরের দাবি", and its homepage shows only the former). Returns each such line alone and joined to the title.
  - Signature: `_headline_variants(soup: BeautifulSoup, title: str \| None) -> list[str]`

### backend/app/features/verification/pipeline/stages/s07_evidence_ranker.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s07_evidence_ranker.py>) · 213 lines

Semantic/keyword/domain relevance score, fuzzy-title bonus, optional cross-encoder tie-break ও top article selection।

**Class [EvidenceRankerStage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s07_evidence_ranker.py:43>)** · inherits `plain class`

- [EvidenceRankerStage.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s07_evidence_ranker.py:47>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, embedding_service: EmbeddingService) -> None`

- [EvidenceRankerStage.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s07_evidence_ranker.py:53>) — Semantic/keyword/domain relevance score, fuzzy-title bonus, optional cross-encoder tie-break ও top article selection।
  - Signature: `async execute(self, context: PipelineContext) -> PipelineContext`

- [EvidenceRankerStage._score_article()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s07_evidence_ranker.py:116>) — Code-এর দায়িত্ব-বর্ণনা: Best score over the page's headline variants (e.g. a kicker line printed above the title): a claim may quote any of them.
  - Signature: `async _score_article(self, article: RankedArticleSchema, claim_headline: str, claim_keywords: list[str], context: PipelineContext) -> float`

- [EvidenceRankerStage._score_title()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s07_evidence_ranker.py:132>) — এক title variant-এর semantic/keyword/domain/fuzzy overlap relevance score দেয়।
  - Signature: `async _score_title(self, article: RankedArticleSchema, title: str \| None, claim_headline: str, claim_keywords: list[str], context: PipelineContext) -> float`

- [EvidenceRankerStage._source_domain_bonus()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s07_evidence_ranker.py:186>) — Evidence publisher host থেকে source-domain ranking signal গণনা করে।
  - Signature: `_source_domain_bonus(self, context: PipelineContext, article: RankedArticleSchema) -> float`

- [EvidenceRankerStage._source_domain_bonus.extract_domain()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s07_evidence_ranker.py:196>) — Evidence publisher host থেকে source-domain ranking signal গণনা করে।
  - Signature: `extract_domain(url: str) -> str`

- [_sigmoid()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s07_evidence_ranker.py:212>) — Unbounded cross-encoder score-কে sigmoid scale-এ আনে।
  - Signature: `_sigmoid(x: float) -> float`

### backend/app/features/verification/pipeline/stages/s08_source_correspondence.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s08_source_correspondence.py>) · 209 lines

Measured similarity/keyword evidence ও search completion দিয়ে source decision; blocked better match হলে incomplete।

**Class [SourceCorrespondenceStage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s08_source_correspondence.py:56>)** · inherits `plain class`

- [SourceCorrespondenceStage.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s08_source_correspondence.py:60>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, embedding_service: EmbeddingService) -> None`

- [SourceCorrespondenceStage.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s08_source_correspondence.py:63>) — Measured similarity/keyword evidence ও search completion দিয়ে source decision; blocked better match হলে incomplete।
  - Signature: `async execute(self, context: PipelineContext) -> PipelineContext`

- [SourceCorrespondenceStage._blocked_match()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s08_source_correspondence.py:110>) — Code-এর দায়িত্ব-বর্ণনা: A search result whose page was never read (fetch blocked or extraction failed) but whose title corresponds to the claim better than the best article that WAS read (`better_than`, None = nothing read corresponds). Judged on the search title with the same rules as a fetched article. Without this, a blocked exact report lost to a weaker stand-in (false ALTERED) or to nothing (false NOT_FOUND).
  - Signature: `async _blocked_match(self, context: PipelineContext, thresholds, *, better_than: str \| None) -> str \| None`

- [SourceCorrespondenceStage._measure()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s08_source_correspondence.py:136>) — Code-এর দায়িত্ব-বর্ণনা: Measure the claim against `title` (and, with an article, the body passages that discuss the claim).
  - Signature: `async _measure(self, context: PipelineContext, article: RankedArticleSchema \| None, title: str \| None) -> dict[str, MetricDetail]`

- [SourceCorrespondenceStage._record_search()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s08_source_correspondence.py:176>) — Provider success/empty/failure ও adequacy-এর হিসাব analysis/context-এ রাখে।
  - Signature: `_record_search(context: PipelineContext) -> None`

- [_metric()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s08_source_correspondence.py:190>) — Source correspondence-এর metric availability ও decision input objects বানায়।
  - Signature: `_metric(detail: MetricDetail) -> Metric`

- [_inputs()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s08_source_correspondence.py:194>) — Source correspondence-এর metric availability ও decision input objects বানায়।
  - Signature: `_inputs(metrics: dict[str, MetricDetail]) -> CorrespondenceInputs`

- [_search_title()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s08_source_correspondence.py:202>) — Code-এর দায়িত্ব-বর্ণনা: Google News titles end with " - <publisher>"; drop that suffix.
  - Signature: `_search_title(snippet: str) -> str`

- [_strip_amp()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s08_source_correspondence.py:208>) — AMP URL variant-এর matching/canonicalization helper।
  - Signature: `_strip_amp(url: str) -> str`

### backend/app/features/verification/pipeline/stages/s09_headline_alteration.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s09_headline_alteration.py>) · 112 lines

Selected source TITLE-এর সঙ্গে submitted headline compare, detail/status persistable context-এ বসায়।

**Class [HeadlineAlterationStage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s09_headline_alteration.py:35>)** · inherits `plain class`

- [HeadlineAlterationStage.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s09_headline_alteration.py:39>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, comparator: HeadlineComparator) -> None`

- [HeadlineAlterationStage.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s09_headline_alteration.py:42>) — Selected source TITLE-এর সঙ্গে submitted headline compare, detail/status persistable context-এ বসায়।
  - Signature: `async execute(self, context: PipelineContext) -> PipelineContext`

- [HeadlineAlterationStage._no_comparison()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s09_headline_alteration.py:107>) — Headline compare সম্ভব না হলে কারণসহ explicit no-verdict state বসায়।
  - Signature: `_no_comparison(context: PipelineContext, claim_headline: str, status: HeadlineCheckStatus, reason: str) -> None`

### backend/app/features/verification/pipeline/stages/s10_body_similarity.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s10_body_similarity.py>) · 72 lines

Applicable body-vs-body চারটি score; headline verdict-এ প্রভাব নেই।

**Class [BodySimilarityStage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s10_body_similarity.py:23>)** · inherits `plain class`

- [BodySimilarityStage.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s10_body_similarity.py:27>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, embedding_service: EmbeddingService) -> None`

- [BodySimilarityStage.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s10_body_similarity.py:30>) — Applicable body-vs-body চারটি score; headline verdict-এ প্রভাব নেই।
  - Signature: `async execute(self, context: PipelineContext) -> PipelineContext`

### backend/app/features/verification/pipeline/stages/s11_date_verification.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s11_date_verification.py>) · 45 lines

Claimed publication day বনাম selected article datePublished; date analysis provenance।

**Class [DateVerificationStage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s11_date_verification.py:22>)** · inherits `plain class`

- [DateVerificationStage.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s11_date_verification.py:26>) — Claimed publication day বনাম selected article datePublished; date analysis provenance।
  - Signature: `async execute(self, context: PipelineContext) -> PipelineContext`

### backend/app/features/verification/pipeline/stages/s12_result_assembly.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s12_result_assembly.py>) · 226 lines

Independent findings, scope, reasoning এবং evidence/search strength সাজায়।

**Class [ResultAssemblyStage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s12_result_assembly.py:32>)** · inherits `plain class`

- [ResultAssemblyStage.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s12_result_assembly.py:36>) — Independent findings, scope, reasoning এবং evidence/search strength সাজায়।
  - Signature: `async execute(self, context: PipelineContext) -> PipelineContext`

- [ResultAssemblyStage._strength()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s12_result_assembly.py:76>) — Code-এর দায়িত্ব-বর্ণনা: CONFIRMED: mean of the correspondence measurements. NOT_FOUND: share of attempted search calls that completed (how thoroughly the absence was checked). INCOMPLETE: 0. Never a probability of truth.
  - Signature: `_strength(context: PipelineContext) -> float`

- [ResultAssemblyStage._source_scope()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s12_result_assembly.py:92>) — কোন source scope-এ evidence খোঁজা হয়েছে তার reproducible response detail বানায়।
  - Signature: `_source_scope(context: PipelineContext) -> SourceScopeDetails`

- [ResultAssemblyStage._reasoning()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s12_result_assembly.py:125>) — Independent findings-এর user-readable explanation বানায়।
  - Signature: `_reasoning(context: PipelineContext) -> str`

- [ResultAssemblyStage._verified_reasoning()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s12_result_assembly.py:179>) — Code-এর দায়িত্ব-বর্ণনা: VERIFIED_SOURCES mode: never implies the claimed/original outlet published anything - the comparison is with a verified-source article.
  - Signature: `_verified_reasoning(context: PipelineContext) -> str`

### backend/app/features/verification/pipeline/stages/s13_result_persistence.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s13_result_persistence.py>) · 260 lines

Own submission/result/evidence/search queries persist, preliminary notification ও cache pointer।

**Class [ResultPersistenceStage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s13_result_persistence.py:46>)** · inherits `plain class`

- [ResultPersistenceStage.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s13_result_persistence.py:50>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, submission_repo: SubmissionRepository, result_repo: ResultRepository, article_repo: RetrievedArticleRepository, cache_service: CacheService, session: AsyncSession \| None=None) -> None`

- [ResultPersistenceStage.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s13_result_persistence.py:64>) — Own submission/result/evidence/search queries persist, preliminary notification ও cache pointer।
  - Signature: `async execute(self, context: PipelineContext) -> PipelineContext`

- [ResultPersistenceStage.execute.metric()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s13_result_persistence.py:81>) — Persisted analysis-এর metric value নেয়; unavailable value-কে বানানো score বানায় না।
  - Signature: `metric(name: str) -> float \| None`

- [ResultPersistenceStage._write_cache_pointer()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s13_result_persistence.py:138>) — Saved reusable result-এর submission pointer Redis-এ লেখে।
  - Signature: `async _write_cache_pointer(self, context: PipelineContext, submission_id: uuid.UUID, result) -> None`

- [ResultPersistenceStage._notify()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s13_result_persistence.py:152>) — Automatic result ready হওয়ার personal notification চালায়।
  - Signature: `async _notify(self, submission: Submission, context: PipelineContext) -> None`

- [ResultPersistenceStage._upsert_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s13_result_persistence.py:162>) — Code-এর দায়িত্ব-বর্ণনা: (submission, already_done). Persists onto the submission this run was started for; a submission that merely shares an identity hash is never adopted (submissions carry owner/type/image provenance).
  - Signature: `async _upsert_submission(self, context: PipelineContext) -> tuple[Submission, bool]`

- [ResultPersistenceStage._increment_submitter_total_submissions()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s13_result_persistence.py:195>) — Submitter-এর cached submission counter বাড়ায়।
  - Signature: `async _increment_submitter_total_submissions(self, submitter_id: uuid.UUID) -> None`
  - Source contract: users.total_submissions cached counter - best effort only.

- [ResultPersistenceStage._persist_articles()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s13_result_persistence.py:204>) — Code-এর দায়িত্ব-বর্ণনা: Ranked articles; returns the DB id of the SELECTED source article (S08's choice). It is stored as `top_article_id`, which the result page and the expert view show first.
  - Signature: `async _persist_articles(self, context: PipelineContext, submission_id: uuid.UUID) -> uuid.UUID \| None`

- [ResultPersistenceStage._persist_search_queries()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/pipeline/stages/s13_result_persistence.py:246>) — Executed search-query/outcome history database-এ লেখে।
  - Signature: `async _persist_search_queries(self, context: PipelineContext, submission_id: uuid.UUID) -> None`

### backend/app/features/verification/presenter.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/presenter.py>) · 248 lines

Persisted result/analysis/evidence থেকে API response; legacy rows ও original expert outcome consistent করে।

- [_publisher_of()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/presenter.py:33>) — Code-এর দায়িত্ব-বর্ণনা: The publisher an evidence article belongs to: the matching eligible verified publisher (verified-sources mode) or its host.
  - Signature: `_publisher_of(url: str, scope, submission: Submission) -> str \| None`

- [resolve_scope()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/presenter.py:51>) — Code-এর দায়িত্ব-বর্ণনা: Photo cards are ALWAYS headline-only, whatever an old row says.
  - Signature: `resolve_scope(submission: Submission, result: VerificationResult) -> ClaimScope`

- [effective_expert_row()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/presenter.py:64>) — Code-এর দায়িত্ব-বর্ণনা: The row whose expert-finalized fields apply to this submission. A reused copy reads the original's review outcome live instead of snapshotting it, so finalization of the original shows up on every copy.
  - Signature: `async effective_expert_row(submission: Submission, result: VerificationResult, result_repo: ResultRepository) -> VerificationResult`

- [pick_expert_row()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/presenter.py:80>) — Code-এর দায়িত্ব-বর্ণনা: `original` is the result of `result.reused_from_submission_id` (or None). The original's review outcome applies once it has a final verdict.
  - Signature: `pick_expert_row(result: VerificationResult, original: VerificationResult \| None) -> VerificationResult`

- [effective_status()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/presenter.py:90>) — Submission ও reused original-এর final state অনুযায়ী displayed status resolve করে।
  - Signature: `effective_status(submission: Submission, original_status: SubmissionStatus \| None) -> SubmissionStatus`

- [is_headline_result()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/presenter.py:100>) — Code-এর দায়িত্ব-বর্ণনা: True for rows written by the Headline Alteration pipeline. Older rows carry a content-level verdict from a different comparison (headline AND body, "no conflict -> matched"); it is never relabelled as a headline verdict.
  - Signature: `is_headline_result(result: VerificationResult) -> bool`

- [parse_analysis()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/presenter.py:108>) — Code-এর দায়িত্ব-বর্ণনা: Validate the stored analysis blob, keeping every section that is still valid. A section written in an older shape (e.g. a pre-v4 headline detail) is dropped instead of hiding the whole result.
  - Signature: `parse_analysis(raw: dict \| None) -> AnalysisDetails \| None`

- [_decided_by_admin()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/presenter.py:133>) — Final decision admin decision হিসেবে recorded হয়েছে কি না resolve করে।
  - Signature: `async _decided_by_admin(result_repo: ResultRepository, submission_id) -> bool`

- [_headline_status()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/presenter.py:146>) — Persisted headline comparison থেকে public display status নেয়।
  - Signature: `_headline_status(result: VerificationResult) -> HeadlineCheckStatus \| None`

- [load_verification_response()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/presenter.py:153>) — Submission/result/selected evidence/analysis/original review outcome দিয়ে complete API response বানায়।
  - Signature: `async load_verification_response(submission: Submission, *, result_repo: ResultRepository, article_repo: RetrievedArticleRepository) -> VerificationResponse \| None`

### backend/app/features/verification/repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/repository.py>) · 113 lines

Feature `verification`। এই feature-এর database queries ও persistence operations; যেখানে BaseRepository inherit করেছে সেখানে common CRUD inherited।

**Class [ResultRepository](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/repository.py:16>)** · inherits `BaseRepository[VerificationResult]`

- [ResultRepository.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/repository.py:20>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, session: AsyncSession) -> None`

- [ResultRepository.get_by_submission_id()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/repository.py:23>) — Submission ID-র সঙ্গে যুক্ত result/record(s) query করে।
  - Signature: `async get_by_submission_id(self, submission_id: uuid.UUID) -> VerificationResult \| None`

- [ResultRepository.record_timings()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/repository.py:34>) — Executed stage, pipeline ও optional preprocessing timings stored analysis JSON-এ লেখে।
  - Signature: `async record_timings(self, submission_id: uuid.UUID, *, stage_ms: dict[str, int], pipeline_ms: int, preprocessing_ms: dict[str, int] \| None=None, cache_hit: bool=False) -> None`

- [ResultRepository.upsert_result()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/repository.py:56>) — Code-এর দায়িত্ব-বর্ণনা: Write the AUTOMATED snapshot for a submission. Only automated columns are written here. Expert-finalized columns (final_*, overall_verdict, finalized_at) belong to ExpertReviewService and are never touched, and `ai_consensus_label` is no longer written at all: the automated system casts no overall truth vote.
  - Signature: `async upsert_result(self, submission_id: uuid.UUID, *, source_status: SourceStatus \| None, content_status: ContentStatus \| None, date_status: DateStatus \| None, confidence: float, reasoning: str, headline_check_status: str \| None=None, headline_exact_match: bool \| None=None, body_comparison_status: str \| None=None, headline_similarity: float \| None=None, headline_keyword_coverage: float \| None=None, passage_keyword_coverage: float \| None=None, top_article_id: uuid.UUID \| None=None, ai_preliminary_label: str \| None=None, avg_verification_time_ms: int \| None=None, claim_scope: str \| None=None, pipeline_version: str \| None=None, analysis_details: dict \| None=None, reused_from_submission_id: uuid.UUID \| None=None) -> VerificationResult`

### backend/app/features/verification/reuse.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/reuse.py>) · 144 lines

Current compatible complete automated result reuse; target-এর ownership রাখে, expert state original থেকে পরে resolve হয়।

- [result_is_reusable()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/reuse.py:56>) — Code-এর দায়িত্ব-বর্ণনা: (reusable, reason). The reason is logged; it never reaches users.
  - Signature: `result_is_reusable(result: VerificationResult \| None, *, now: datetime \| None=None) -> tuple[bool, str]`

**Class [ResultReuseService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/reuse.py:80>)** · inherits `plain class`

- [ResultReuseService.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/reuse.py:81>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, submission_repo: SubmissionRepository, result_repo: ResultRepository) -> None`

- [ResultReuseService.find_reusable()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/reuse.py:87>) — Identical hash-এর candidates থেকে compatible complete reusable result বেছে নেয়।
  - Signature: `async find_reusable(self, content_hash: str, *, exclude_submission_id: uuid.UUID \| None=None) -> tuple[Submission, VerificationResult] \| None`

- [ResultReuseService.materialize()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/reuse.py:100>) — Code-এর দায়িত্ব-বর্ণনা: Copy the automated snapshot onto `target` (idempotent).
  - Signature: `async materialize(self, *, source: Submission, source_result: VerificationResult, target: Submission) -> VerificationResult`

### backend/app/features/verification/router.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/router.py>) · 197 lines

Feature `verification`। এই feature-এর HTTP paths, request/response schema, dependencies ও permission guard define করে; handler সংশ্লিষ্ট service/repository-তে কাজ পাঠায়।

- [verify_claim()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/router.py:47>) — Synchronous verification service চালিয়ে completed response ফেরত দেয়।
  - Signature: `async verify_claim(request: VerificationRequest, service: VerificationService=Depends(get_verification_service), current_user: User \| None=Depends(get_current_user_optional)) -> VerificationResponse`

- [verify_claim_async()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/router.py:94>) — Claim register/enqueue বা reuse করে accepted submission response দেয়।
  - Signature: `async verify_claim_async(request: VerificationRequest, http_request: Request, service: VerificationService=Depends(get_verification_service), current_user: User \| None=Depends(get_current_user_optional)) -> VerificationQueuedResponse`

- [get_verification_result()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/router.py:138>) — Saved structured/photo result reconstruct করে ফেরত দেয়; feature-specific response shape ব্যবহার হয়।
  - Signature: `async get_verification_result(submission_id: uuid.UUID, service: VerificationService=Depends(get_verification_service), current_user: User \| None=Depends(get_current_user_optional)) -> VerificationResponse`

- [get_verification_status()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/router.py:162>) — Access-checked submission progress এবং result readiness দেয়।
  - Signature: `async get_verification_status(submission_id: uuid.UUID, submission_repo: SubmissionRepository=Depends(get_submission_repo), service: VerificationService=Depends(get_verification_service), current_user: User \| None=Depends(get_current_user_optional)) -> VerificationStatusResponse`

### backend/app/features/verification/schemas.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py>) · 454 lines

Feature `verification`। এই feature-এর Pydantic request/response structures ও validation define করে; এগুলো database table নয়।

**Class [NLIScoresSchema](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:23>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `entailment` | `float` | Field(..., ge=0.0, le=1.0, description='NLI entailment probability') |
| `contradiction` | `float` | Field(..., ge=0.0, le=1.0, description='NLI contradiction probability') |
| `neutral` | `float` | Field(..., ge=0.0, le=1.0, description='NLI neutral probability') |

**Class [MetricDetail](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:34>)** · inherits `BaseModel`

দায়িত্ব/contract: A source-correspondence measurement plus the state that explains it. A null value is "no measurement" (see `state`), never 0.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `state` | `MetricState` | required / instance-assigned |
| `value` | `float \| None` | None |
| `reason` | `str \| None` | None |
| `details` | `dict` | Field(default_factory=dict) |

**Class [SearchAccounting](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:44>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `attempted` | `int` | 0 |
| `success` | `int` | 0 |
| `success_empty` | `int` | 0 |
| `failed` | `int` | 0 |
| `skipped` | `int` | 0 |
| `cached` | `int` | 0 |
| `adequate` | `bool \| None` | Field(default=None, description='True only when enough provider calls completed to treat an empty result as a real negative.') |
| `providers` | `dict[str, dict[str, int]]` | Field(default_factory=dict) |
| `redirect_rejected` | `int` | 0 |

**Class [DateAnalysis](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:59>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `claimed_date` | `date \| None` | None |
| `article_date` | `date \| None` | Field(default=None, description='datePublished as a calendar day in Asia/Dhaka.') |
| `article_published_at` | `datetime \| None` | None |
| `provenance` | `str \| None` | Field(default=None, description="Where the article's publication date came from (json_ld.datePublished, meta.article:published_time, selector, ...). dateModified and crawl dates are never used.") |
| `tz_assumed` | `bool` | False |
| `timezone` | `str` | 'Asia/Dhaka' |

**Class [HeadlineDifference](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:73>)** · inherits `BaseModel`

দায়িত্ব/contract: One material difference between the claim headline and the source title.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `kind` | `str` | Field(description='numbers \| date \| negation \| modality \| scope \| subject_object \| attribution \| denial \| entity \| main_point') |
| `detail` | `str` | required / instance-assigned |
| `claim_text` | `str` | required / instance-assigned |
| `source_text` | `str` | required / instance-assigned |

**Class [HeadlineSemanticAssessment](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:84>)** · inherits `BaseModel`

দায়িত্ব/contract: Local-model evidence for a non-exact comparison (title vs headline only).

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `available` | `bool` | required / instance-assigned |
| `entailment_title_to_claim` | `float \| None` | Field(default=None, ge=0.0, le=1.0) |
| `contradiction_title_to_claim` | `float \| None` | Field(default=None, ge=0.0, le=1.0) |
| `entailment_claim_to_title` | `float \| None` | Field(default=None, ge=0.0, le=1.0) |
| `contradiction_claim_to_title` | `float \| None` | Field(default=None, ge=0.0, le=1.0) |
| `embedding_cosine` | `float \| None` | Field(default=None, ge=-1.0, le=1.0, description='LaBSE cosine of headline vs title (raw, -1..1).') |
| `reason` | `str \| None` | None |

**Class [HeadlineAlterationDetail](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:98>)** · inherits `BaseModel`

দায়িত্ব/contract: Headline Alteration — the claim headline compared ONLY with the selected source article's title (never its body). `verdict` is MATCHED, ALTERED or null; when null, `status` says why (source not found, search incomplete, title missing, model unavailable, undetermined).

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `status` | `HeadlineCheckStatus` | required / instance-assigned |
| `verdict` | `ContentStatus \| None` | None |
| `reason` | `str` | Field(description='Short, evidence-based basis for the verdict or for its absence.') |
| `exact_match` | `bool` | Field(default=False, description='True when the verdict was decided by an exact match, before any alteration analysis ran.') |
| `basis` | `str` | Field(default='none', description='exact \| same_words \| semantic_equivalence \| material_difference \| semantic_divergence \| none') |
| `claim_headline` | `str` | required / instance-assigned |
| `source_title` | `str \| None` | None |
| `source_publisher` | `str \| None` | None |
| `source_url` | `str \| None` | None |
| `differences` | `list[HeadlineDifference]` | Field(default_factory=list) |
| `semantic` | `HeadlineSemanticAssessment \| None` | None |
| `ner_available` | `bool` | False |
| `method` | `str \| None` | None |

**Class [BodySimilarityMetric](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:125>)** · inherits `BaseModel`

দায়িত্ব/contract: One claim-body vs source-body similarity measurement. `value` is the displayed 0-1 score (null when unavailable - never a default 0); `raw_value` keeps the metric's raw output (semantic cosine may be negative); `reason` explains unavailability.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `available` | `bool` | required / instance-assigned |
| `value` | `float \| None` | Field(default=None, ge=0.0, le=1.0) |
| `raw_value` | `float \| None` | None |
| `reason` | `str \| None` | None |
| `details` | `dict` | Field(default_factory=dict) |

**Class [BodySimilarityReport](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:138>)** · inherits `BaseModel`

দায়িত্ব/contract: Claim body vs source body - similarity MEASUREMENTS only, never a truth, alteration or contradiction verdict, and never an input to the Headline Alteration verdict.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `status` | `BodyComparisonStatus` | required / instance-assigned |
| `reason` | `str \| None` | None |
| `tfidf_cosine` | `BodySimilarityMetric \| None` | None |
| `jaccard` | `BodySimilarityMetric \| None` | None |
| `normalized_levenshtein` | `BodySimilarityMetric \| None` | None |
| `semantic_cosine` | `BodySimilarityMetric \| None` | None |
| `claim_chars` | `int \| None` | None |
| `source_chars` | `int \| None` | None |

**Class [ExecutionTimings](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:153>)** · inherits `BaseModel`

দায়িত্ব/contract: Measured wall times for this execution, in milliseconds. Pipeline time excludes photo preprocessing, queue wait and the final transaction commit. Missing stages were skipped, not measured as zero.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `stage_ms` | `dict[str, int]` | Field(default_factory=dict) |
| `preprocessing_ms` | `dict[str, int]` | Field(default_factory=dict) |
| `pipeline_ms` | `int` | required / instance-assigned |
| `cache_hit` | `bool` | False |

**Class [SourceScopeDetails](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:166>)** · inherits `BaseModel`

দায়িত্ব/contract: How the evidence scope was chosen (absent on older results, which are claimed-source results).

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `verification_mode` | `str` | Field(description='CLAIMED_SOURCE \| VERIFIED_SOURCES') |
| `resolution_reason` | `str \| None` | Field(default=None, description='SOURCE_SELECTED \| SOURCE_DETECTED \| SOURCE_NOT_SUPPLIED \| SOURCE_NOT_DETECTED \| SOURCE_UNRECOGNIZED \| SOURCE_INACTIVE') |
| `raw_source_text` | `str \| None` | Field(default=None, description='The source text as given/detected - provenance only, never an evidence scope.') |
| `claimed_source` | `str \| None` | None |
| `scope_fingerprint` | `str \| None` | None |
| `eligible_publishers` | `list[str]` | Field(default_factory=list) |
| `evidence_publishers` | `list[str]` | Field(default_factory=list) |
| `primary_article_url` | `str \| None` | None |
| `primary_publisher` | `str \| None` | None |
| `incomplete_reason` | `str \| None` | None |

**Class [AnalysisDetails](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:187>)** · inherits `BaseModel`

দায়িত্ব/contract: Everything needed to explain and reproduce a result after Redis expiry.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `pipeline_version` | `str \| None` | None |
| `claim_scope` | `ClaimScope \| None` | None |
| `metrics` | `dict[str, MetricDetail]` | Field(default_factory=dict, description='Source-correspondence measurements.') |
| `search` | `SearchAccounting \| None` | None |
| `source_basis` | `list[str]` | Field(default_factory=list) |
| `headline_alteration` | `HeadlineAlterationDetail \| None` | None |
| `body_similarity` | `BodySimilarityReport \| None` | None |
| `date` | `DateAnalysis \| None` | None |
| `stage_errors` | `dict[str, str]` | Field(default_factory=dict) |
| `timings` | `ExecutionTimings \| None` | None |
| `source_scope` | `SourceScopeDetails \| None` | None |

**Class [VerificationRequest](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:205>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `headline` | `str` | Field(..., min_length=5, max_length=2000, description='The article headline being claimed.', examples=['বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন পাস হয়েছে']) |
| `body_text` | `str \| None` | Field(default=None, max_length=50000) |
| `claimed_source_text` | `str \| None` | Field(default=None, max_length=255, description='The outlet the claim names. Optional: when missing, blank, unrecognised or inactive, the claim is checked against the active verified sources instead.') |
| `published_date` | `date \| None` | Field(default=None, examples=['2024-03-15']) |

- [VerificationRequest._strip_headline()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:227>) — Input text-এর whitespace/empty values normalize ও field constraints enforce করে।
  - Signature: `_strip_headline(cls, v: str) -> str`

- [VerificationRequest._strip_claimed_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:235>) — Input text-এর whitespace/empty values normalize ও field constraints enforce করে।
  - Signature: `_strip_claimed_source(cls, v: str \| None) -> str \| None`

- [VerificationRequest._strip_body_text()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:243>) — Input text-এর whitespace/empty values normalize ও field constraints enforce করে।
  - Signature: `_strip_body_text(cls, v: str \| None) -> str \| None`

**Class [VerificationResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:261>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `uuid.UUID` | required / instance-assigned |
| `overall_verdict` | `OverallVerdict \| None` | Field(default=None, description='The expert-finalized Overall verdict (Fake/Real/Misleading/Altered). The automated system never computes this — it is NULL until expert review finalizes the claim, full stop. There is no AI-implied value.') |
| `is_finalized` | `bool` | Field(default=False, description='True once expert review has finalized overall_verdict.') |
| `decided_by_admin` | `bool` | Field(default=False, description='True when an administrator made the final decision on an escalated claim.') |
| `was_overridden` | `bool` | Field(default=False, description="Deprecated, always false: reviewers' supplementary assessments no longer replace the preliminary findings, which are always the AI's own.") |
| `ai_source_status` | `SourceStatus \| None` | Field(default=None, description="The AI's own original call — immutable, never changed by expert review.") |
| `ai_content_status` | `ContentStatus \| None` | Field(default=None) |
| `ai_date_status` | `DateStatus \| None` | Field(default=None) |
| `source_status` | `SourceStatus` | Field(..., description='Was a relevant article found in the claimed source? CONFIRMED is shown as Found, NOT_FOUND as Not Found ("Not found in claimed source"). The AI\'s preliminary finding.') |
| `content_status` | `ContentStatus \| None` | Field(default=None, description='Headline Alteration verdict (MATCHED \| ALTERED): the claim headline compared with the source title only. Null when no verdict was reached - see headline_check_status for why.') |
| `headline_status` | `HeadlineAlterationStatus \| None` | Field(default=None, description='Display status of the Headline Alteration verdict: EXACT_MATCHED \| MEANING_PRESERVED (both are content_status MATCHED) \| ALTERED.') |
| `headline_check_status` | `HeadlineCheckStatus \| None` | Field(default=None, description='Processing/availability status of the Headline Alteration check (separate from the verdict).') |
| `claimed_published_date` | `date \| None` | Field(default=None, description='The publication date the submitter claimed. Date comparison is shown only when this is set.') |
| `date_status` | `DateStatus \| None` | Field(default=None, description="Whether the claimed publication date matches the source article's actual date. Only set when both dates are known; a mismatch does not imply the content itself is false.") |
| `confidence` | `float` | Field(..., ge=0.0, le=1.0, description='Source-correspondence strength (mean of the correspondence measurements). Not a probability of truth.') |
| `reasoning` | `str` | required / instance-assigned |
| `matched_articles` | `list[RankedArticleSchema]` | Field(default_factory=list) |
| `normalized_source` | `str \| None` | None |
| `cached` | `bool` | False |
| `processing_time_ms` | `int \| None` | None |
| `created_at` | `datetime` | required / instance-assigned |
| `claim_scope` | `ClaimScope \| None` | Field(default=None, description='HEADLINE_ONLY (always for photo cards) or HEADLINE_WITH_BODY.') |
| `review_pending` | `bool` | Field(default=True, description='True until expert review finalizes the overall verdict; the UI must not show a truth badge while True.') |
| `confidence_meaning` | `str` | Field(default='Source-correspondence strength: the mean of the headline/title similarity and keyword-coverage measurements used to decide whether the claimed outlet carried this report. It is not the probability that the claim is true.') |
| `pipeline_version` | `str \| None` | None |
| `legacy_result` | `bool` | Field(default=False, description='True for a result stored by the pre-Headline-Alteration pipeline. Its old content-level verdict is NOT shown as a headline verdict (ai_content_status is null for such rows).') |
| `analysis` | `AnalysisDetails \| None` | None |
| `verification_mode` | `str` | Field(default='CLAIMED_SOURCE', description='CLAIMED_SOURCE: searched only the claimed outlet. VERIFIED_SOURCES: no usable claimed outlet, so the active verified sources were searched; CONFIRMED then means a corresponding report was found in a verified source, not that the claimed outlet published it.') |
| `source_resolution_reason` | `str \| None` | None |

**Class [VerificationQueuedResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:402>)** · inherits `BaseModel`

দায়িত্ব/contract: Acknowledgement for a claim accepted for background verification. The pipeline takes up to a minute or so, which is far too long to hold a user on the form. The claim is registered immediately and this identifier is what the caller polls (or revisits from their history) for the result.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `uuid.UUID` | required / instance-assigned |
| `status` | `SubmissionStatus` | required / instance-assigned |
| `cached` | `bool` | Field(default=False, description='True when this exact claim had already been verified and the stored result is being reused instead of re-running the pipeline.') |

**Class [VerificationStatusResponse](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/schemas.py:431>)** · inherits `BaseModel`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `submission_id` | `uuid.UUID` | required / instance-assigned |
| `status` | `SubmissionStatus` | required / instance-assigned |
| `phase` | `str \| None` | Field(default=None, description='QUEUED \| EXTRACTING \| VERIFYING \| DONE \| FAILED') |
| `result` | `VerificationResponse \| None` | None |
| `error` | `str \| None` | Field(default=None, description='User-presentable reason when status is FAILED') |
| `queued_at` | `datetime` | required / instance-assigned |
| `updated_at` | `datetime` | required / instance-assigned |

### backend/app/features/verification/service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/service.py>) · 316 lines

Source claim-এর sync verification/async registration, identity locking/reuse ও stored result retrieval।

- [claim_scope_for()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/service.py:35>) — Nonempty submitted body থাকলে HEADLINE_WITH_BODY, নইলে HEADLINE_ONLY দেয়।
  - Signature: `claim_scope_for(body_text: str \| None) -> ClaimScope`

**Class [VerificationService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/service.py:43>)** · inherits `plain class`

- [VerificationService.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/service.py:45>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, submission_repo: SubmissionRepository, result_repo: ResultRepository, article_repo: RetrievedArticleRepository, source_repo: SourceRepository, cache_service: CacheService, embedding_service: EmbeddingService, ner_service: NERService, nli_service: NLIService, http_client: httpx.AsyncClient) -> None`

- [VerificationService.verify()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/service.py:70>) — Source resolution, context, orchestrator, persistence/reuse ও response reconstruction দিয়ে full verification চালায়।
  - Signature: `async verify(self, request: VerificationRequest, *, submitter_id: uuid.UUID \| None=None, submission_id: uuid.UUID \| None=None) -> VerificationResponse`

- [VerificationService.run_for_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/service.py:123>) — Code-এর দায়িত্ব-বর্ণনা: Background-job entry point: everything comes from the stored submission row, nothing from a request.
  - Signature: `async run_for_submission(self, submission_id: uuid.UUID) -> VerificationResponse`

- [VerificationService._submission_for()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/service.py:137>) — Code-এর দায়িত্ব-বর্ণনা: The requester's own submission, with its automated result.
  - Signature: `async _submission_for(self, context: PipelineContext, request: VerificationRequest, submitter_id: uuid.UUID \| None, submission_id: uuid.UUID \| None) -> Submission`

- [VerificationService.register_claim()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/service.py:180>) — Code-এর দায়িত্ব-বর্ণনা: Accept a claim for background verification. Returns ``(submission_id, status, served_from_cache)``. The submission and its durable job row are committed together before returning, so an accepted claim can never be lost or stranded. A claim that was already checked is never verified again: if an identical, complete verification still exists in the database the requester gets their OWN submission carrying a copy of its automated result (no job queued, no new evidence search). Reuse never shares a submission across owners; only the same submitter's identical in-flight claim is handed back. A deleted submission/result is gone from the database and therefore never reused.
  - Signature: `async register_claim(self, request: VerificationRequest, *, submitter_id: uuid.UUID \| None=None) -> tuple[uuid.UUID, SubmissionStatus, bool]`

- [VerificationService._lock_identity()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/service.py:261>) — PostgreSQL advisory transaction lock দিয়ে same-identity concurrent registration serialize করে।
  - Signature: `async _lock_identity(self, content_hash: str) -> None`

- [VerificationService._create_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/service.py:273>) — এই method/owner/input-এর নিজস্ব Submission record তৈরি করে।
  - Signature: `async _create_submission(self, request: VerificationRequest, submitter_id: uuid.UUID \| None, content_hash: str, status: SubmissionStatus) -> Submission`

- [VerificationService.get_result()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/service.py:295>) — Saved structured/photo result reconstruct করে ফেরত দেয়; feature-specific response shape ব্যবহার হয়।
  - Signature: `async get_result(self, submission_id: uuid.UUID) -> VerificationResponse \| None`

- [VerificationService._build_stages()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/service.py:305>) — প্রয়োজনীয় dependencies দিয়ে ordered pipeline stage instances তৈরি করে।
  - Signature: `_build_stages(self) -> list`

### backend/app/features/verification/source_policy.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/source_policy.py>) · 185 lines

CLAIMED_SOURCE বনাম VERIFIED_SOURCES scope resolution; active publisher/domain fingerprint ও fallback policy।

- [fallback_enabled()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/source_policy.py:48>) — Verified-source fallback feature configuration চালু কি না জানায়।
  - Signature: `fallback_enabled() -> bool`

**Class [SourceResolution](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/source_policy.py:53>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `mode` | `str` | required / instance-assigned |
| `canonical` | `str \| None` | required / instance-assigned |
| `reason` | `str` | required / instance-assigned |
| `raw_text` | `str \| None` | None |

- [SourceResolution.is_fallback()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/source_policy.py:60>) — Current source resolution VERIFIED_SOURCES mode কি না জানায়।
  - Signature: `is_fallback(self) -> bool`

**Class [VerifiedPublisher](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/source_policy.py:65>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `canonical` | `str` | required / instance-assigned |
| `name` | `str` | required / instance-assigned |
| `domains` | `list[str]` | required / instance-assigned |
| `config` | `dict` | required / instance-assigned |

- [VerifiedPublisher.to_summary()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/source_policy.py:71>) — এই result/value object-এর serializable dictionary representation দেয়।
  - Signature: `to_summary(self) -> dict`

**Class [VerifiedScope](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/source_policy.py:76>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `publishers` | `list[VerifiedPublisher]` | field(default_factory=list) |
| `fingerprint` | `str` | '' |

- [VerifiedScope.empty()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/source_policy.py:81>) — Verified publisher scope খালি কি না বা তার distinct domains দেয়।
  - Signature: `empty(self) -> bool`

- [VerifiedScope.all_domains()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/source_policy.py:85>) — Verified publisher scope খালি কি না বা তার distinct domains দেয়।
  - Signature: `all_domains(self) -> list[str]`

- [VerifiedScope.publisher_for_host()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/source_policy.py:93>) — URL/host eligible verified publisher-এর কোনটির অধীনে পড়ে তা resolve করে।
  - Signature: `publisher_for_host(self, host: str) -> VerifiedPublisher \| None`

- [VerifiedScope.publisher_for_url()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/source_policy.py:101>) — URL/host eligible verified publisher-এর কোনটির অধীনে পড়ে তা resolve করে।
  - Signature: `publisher_for_url(self, url: str) -> VerifiedPublisher \| None`

- [source_config_for()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/source_policy.py:111>) — Code-এর দায়িত্ব-বর্ণনা: The per-outlet configuration S04-S06 use (selectors, allowed hosts).
  - Signature: `source_config_for(record) -> dict`

- [resolve_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/source_policy.py:133>) — Canonical name/alias অনুযায়ী publisher resolve বা policy অনুযায়ী source mode নির্ধারণ করে।
  - Signature: `async resolve_source(raw_text: str \| None, source_repo: SourceRepository, *, selected_reason: str=REASON_SELECTED, missing_reason: str=REASON_NOT_SUPPLIED) -> SourceResolution`
  - Source contract: Decide the verification mode for a claimed source text.

- [load_verified_scope()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/source_policy.py:156>) — Code-এর দায়িত্ব-বর্ণনা: Active verified publishers with their allowed domains and selectors. An empty registry is an empty scope - never an unrestricted search.
  - Signature: `async load_verified_scope(source_repo: SourceRepository) -> VerifiedScope`

- [verified_identity_key()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/source_policy.py:179>) — Code-এর দায়িত্ব-বর্ণনা: Stands in for the canonical source in the claim identity.
  - Signature: `verified_identity_key(scope: VerifiedScope) -> str`

- [is_verified_identity_key()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/source_policy.py:184>) — Identity string verified-source scope fingerprint কি না পরীক্ষা করে।
  - Signature: `is_verified_identity_key(value: str \| None) -> bool`

### backend/app/features/verification/verdict_compat.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/verdict_compat.py>) · 39 lines

Structured findings-এর concise display label; legacy UI compatibility।

- [format_verdict_display()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/verification/verdict_compat.py:22>) — Code-এর দায়িত্ব-বর্ণনা: Human-readable one-line summary for the expert queue's "AI said" column.
  - Signature: `format_verdict_display(source_status: SourceStatus \| None, headline_status: HeadlineAlterationStatus \| None, date_status: DateStatus \| None=None) -> str \| None`

### backend/app/main.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/main.py>) · 66 lines

FastAPI app তৈরি, middleware/router/error handler register এবং ORM registry import। মূল function create_app(); module-level app-ই Uvicorn চালায়।

- [create_app()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/main.py:30>) — FastAPI app, middleware, API routes ও exception handlers একত্রে তৈরি করে।
  - Signature: `create_app() -> FastAPI`

### backend/app/shared/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/__init__.py>) · 0 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/shared/base_model.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_model.py>) · 50 lines

SQLAlchemy Base এবং UUID/timestamp/repr mixins। অন্য entities এগুলো inherit করে।

**Class [Base](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_model.py:11>)** · inherits `DeclarativeBase`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `type_annotation_map` | `dict` | {} |

**Class [UUIDMixin](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_model.py:16>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `id` | `Mapped[uuid.UUID]` | mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False, comment='Primary key — UUID v4 generated in Python before INSERT') |

**Class [TimestampMixin](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_model.py:27>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `created_at` | `Mapped[datetime]` | mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True, comment='Row creation timestamp (UTC, set by DB on INSERT)') |
| `updated_at` | `Mapped[datetime]` | mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment='Row last-update timestamp (UTC, auto-updated by DB on UPDATE)') |

**Class [ReprMixin](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_model.py:46>)** · inherits `plain class`

- [ReprMixin.__repr__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_model.py:48>) — Debugging-এর জন্য object-এর সংক্ষিপ্ত text representation দেয়।
  - Signature: `__repr__(self) -> str`

### backend/app/shared/base_repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_repository.py>) · 140 lines

Generic database CRUD ও page-এর submission IDs অনুযায়ী batch row loading।

- [rows_by_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_repository.py:20>) — Code-এর দায়িত্ব-বর্ণনা: {submission_id: row} for a page of submissions, in one query. For tables holding at most one row per submission (results, analyses, extractions) - avoids one query per listed submission.
  - Signature: `async rows_by_submission(session: AsyncSession, model: type, submission_ids: list) -> dict`

**Class [BaseRepository](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_repository.py:32>)** · inherits `Generic[ModelT]`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `model_class` | `type[ModelT]` | required / instance-assigned |

- [BaseRepository.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_repository.py:36>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, session: AsyncSession) -> None`

- [BaseRepository.get_by_id()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_repository.py:39>) — ID অনুযায়ী database record আনে; না থাকলে not-found error দেয়।
  - Signature: `async get_by_id(self, record_id: uuid.UUID) -> ModelT`

- [BaseRepository.get_by_id_or_none()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_repository.py:48>) — ID অনুযায়ী record আনে; অনুপস্থিত হলে None দেয়।
  - Signature: `async get_by_id_or_none(self, record_id: uuid.UUID) -> ModelT \| None`

- [BaseRepository.list_all()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_repository.py:51>) — নির্ধারিত ordering/pagination অনুযায়ী records আনে।
  - Signature: `async list_all(self, *, limit: int=20, offset: int=0, order_by: Any=None) -> list[ModelT]`

- [BaseRepository.count()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_repository.py:65>) — সংশ্লিষ্ট records-এর total count বের করে।
  - Signature: `async count(self) -> int`

- [BaseRepository.create()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_repository.py:70>) — নতুন entity/entities session-এ যোগ করে persistence/flush করে।
  - Signature: `async create(self, instance: ModelT) -> ModelT`

- [BaseRepository.bulk_create()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_repository.py:88>) — নতুন entity/entities session-এ যোগ করে persistence/flush করে।
  - Signature: `async bulk_create(self, instances: list[ModelT]) -> list[ModelT]`

- [BaseRepository.update()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_repository.py:109>) — প্রদত্ত fields entity-তে বদলে database session flush করে।
  - Signature: `async update(self, instance: ModelT, **fields: Any) -> ModelT`

- [BaseRepository.delete()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_repository.py:130>) — নির্দিষ্ট entity/ID-এর row delete করে।
  - Signature: `async delete(self, instance: ModelT) -> None`

- [BaseRepository.delete_by_id()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/base_repository.py:138>) — নির্দিষ্ট entity/ID-এর row delete করে।
  - Signature: `async delete_by_id(self, record_id: uuid.UUID) -> None`

### backend/app/shared/dependencies.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/dependencies.py>) · 105 lines

FastAPI Depends providers: request session, repositories, app.state clients/models এবং services assemble করে।

- [get_async_session()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/dependencies.py:24>) — Request database session দেয়; সফল হলে commit, exception হলে rollback; shared wrapper-এ মূল provider-এ delegate করে।
  - Signature: `async get_async_session() -> AsyncGenerator[AsyncSession, None]`

- [get_submission_repo()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/dependencies.py:34>) — বর্তমান database session দিয়ে উপযুক্ত repository তৈরি করে।
  - Signature: `async get_submission_repo(session: AsyncSession=Depends(get_async_session)) -> SubmissionRepository`

- [get_result_repo()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/dependencies.py:40>) — বর্তমান database session দিয়ে উপযুক্ত repository তৈরি করে।
  - Signature: `async get_result_repo(session: AsyncSession=Depends(get_async_session)) -> ResultRepository`

- [get_article_repo()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/dependencies.py:46>) — বর্তমান database session দিয়ে উপযুক্ত repository তৈরি করে।
  - Signature: `async get_article_repo(session: AsyncSession=Depends(get_async_session)) -> RetrievedArticleRepository`

- [get_source_repo()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/dependencies.py:52>) — বর্তমান database session দিয়ে উপযুক্ত repository তৈরি করে।
  - Signature: `async get_source_repo(session: AsyncSession=Depends(get_async_session)) -> SourceRepository`

- [get_cache_service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/dependencies.py:58>) — Application state থেকে shared client/model/storage service সরবরাহ করে।
  - Signature: `get_cache_service(request: Request) -> CacheService`

- [get_embedding_service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/dependencies.py:62>) — Application state থেকে shared client/model/storage service সরবরাহ করে।
  - Signature: `get_embedding_service(request: Request) -> EmbeddingService`

- [get_ner_service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/dependencies.py:66>) — Application state থেকে shared client/model/storage service সরবরাহ করে।
  - Signature: `get_ner_service(request: Request) -> NERService`

- [get_nli_service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/dependencies.py:70>) — Application state থেকে shared client/model/storage service সরবরাহ করে।
  - Signature: `get_nli_service(request: Request) -> NLIService`

- [get_http_client()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/dependencies.py:74>) — Application state থেকে shared client/model/storage service সরবরাহ করে।
  - Signature: `get_http_client(request: Request) -> httpx.AsyncClient`

- [get_verification_service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/dependencies.py:78>) — FastAPI dependency হিসেবে এই feature-এর service প্রয়োজনীয় repository/shared resources দিয়ে তৈরি করে।
  - Signature: `async get_verification_service(submission_repo: SubmissionRepository=Depends(get_submission_repo), result_repo: ResultRepository=Depends(get_result_repo), article_repo: RetrievedArticleRepository=Depends(get_article_repo), source_repo: SourceRepository=Depends(get_source_repo), cache_service: CacheService=Depends(get_cache_service), embedding_service: EmbeddingService=Depends(get_embedding_service), ner_service: NERService=Depends(get_ner_service), nli_service: NLIService=Depends(get_nli_service), http_client: httpx.AsyncClient=Depends(get_http_client)) -> VerificationService`

- [get_source_service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/dependencies.py:102>) — FastAPI dependency হিসেবে এই feature-এর service প্রয়োজনীয় repository/shared resources দিয়ে তৈরি করে।
  - Signature: `async get_source_service(source_repo: SourceRepository=Depends(get_source_repo)) -> SourceService`

### backend/app/shared/email_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/email_service.py>) · 94 lines

SMTP দিয়ে password-reset OTP ও final-result email পাঠায়; blocking mail operation executor-এ চালায়।

**Class [EmailService](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/email_service.py:16>)** · inherits `plain class`

দায়িত্ব/contract: Thin SMTP wrapper for transactional email (currently: password-reset OTPs). When `EMAIL_SMTP_HOST` is unset, no real email is sent — the OTP is logged instead so the flow stays testable in local/dev environments without SMTP credentials.

- [EmailService.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/email_service.py:25>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self) -> None`

- [EmailService.send_otp_email()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/email_service.py:28>) — Password-reset OTP email প্রস্তুত ও পাঠায়; unconfigured development behavior আছে।
  - Signature: `async send_otp_email(self, *, to_email: str, otp: str, purpose: str='password_reset') -> None`

- [EmailService.send_result_email()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/email_service.py:61>) — Submitter-এর final verdict ও result link-সহ email পাঠায়।
  - Signature: `async send_result_email(self, *, to_email: str, submission_id: str, headline: str, verdict: str) -> None`

- [EmailService._send_sync()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/email_service.py:75>) — SMTP connection/auth/TLS/message-send-এর blocking operation চালায়।
  - Signature: `_send_sync(self, to_email: str, subject: str, body: str) -> None`

### backend/app/shared/models_registry.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/models_registry.py>) · 51 lines

সব ORM model import করে relationship registry populate করে; function ছাড়াই import side effect গুরুত্বপূর্ণ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/shared/status_labels.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/status_labels.py>) · 68 lines

Internal statuses ও preliminary AI prediction-এর user-facing label mapping।

- [ai_decision_label()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/status_labels.py:58>) — Code-এর দায়িত্ব-বর্ণনা: `fake` -> Likely Fake; `non-fake` (or any non-fake class) -> Likely Real. This is the model's preliminary call, never an expert verdict.
  - Signature: `ai_decision_label(prediction: MultimodalPredictionLabel \| str \| None) -> str \| None`

### backend/app/shared/utils/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/__init__.py>) · 0 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/shared/utils/article_url_heuristics.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/article_url_heuristics.py>) · 98 lines

Search result article page নাকি tag/category/listing তা URL shape/publisher patterns দিয়ে আলাদা করে।

- [_segment_looks_like_id()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/article_url_heuristics.py:47>) — URL path segment article/content identifier-এর মতো কি না দেখে।
  - Signature: `_segment_looks_like_id(segment: str) -> bool`

- [looks_like_article_url()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/article_url_heuristics.py:59>) — Code-এর দায়িত্ব-বর্ণনা: Structural fallback check: does this URL look like a specific article rather than a listing/category/tag/nav page? Looks for a `/YYYY/MM/DD/` date segment, or any path segment that reads as an opaque content ID (a run of 4+ digits, a `word-1234` slug, or an 8+ character alphanumeric hash-like slug) — patterns shared by nearly every Bangla news CMS regardless of how the rest of the URL is shaped.
  - Signature: `looks_like_article_url(url: str) -> bool`

- [is_probable_article()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/article_url_heuristics.py:80>) — Code-এর দায়িত্ব-বর্ণনা: Combined check used by search-result filtering. 1. Always reject known non-article URL shapes (tags, feeds, search pages, etc.) — a source's custom patterns should never override this. 2. If the source has custom `article_url_patterns` and one matches, accept immediately (high-confidence, curator-verified signal). 3. Otherwise fall back to the structural heuristic above, so a stale or missing pattern list degrades gracefully instead of rejecting every candidate for that source.
  - Signature: `is_probable_article(url: str, source_patterns: list[str] \| None) -> bool`

### backend/app/shared/utils/bangla_normalizer.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/bangla_normalizer.py>) · 128 lines

Unicode, whitespace, punctuation, বাংলা digits ও source-name/domain normalization।

- [normalize_unicode()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/bangla_normalizer.py:43>) — Function নাম অনুযায়ী Unicode/spacing/punctuation/digits/source text বা combined Bangla normalization করে।
  - Signature: `normalize_unicode(text: str) -> str`

- [normalize_whitespace()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/bangla_normalizer.py:51>) — Function নাম অনুযায়ী Unicode/spacing/punctuation/digits/source text বা combined Bangla normalization করে।
  - Signature: `normalize_whitespace(text: str) -> str`

- [normalize_punctuation()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/bangla_normalizer.py:55>) — Function নাম অনুযায়ী Unicode/spacing/punctuation/digits/source text বা combined Bangla normalization করে।
  - Signature: `normalize_punctuation(text: str) -> str`

- [normalize_bangla_digits()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/bangla_normalizer.py:59>) — Function নাম অনুযায়ী Unicode/spacing/punctuation/digits/source text বা combined Bangla normalization করে।
  - Signature: `normalize_bangla_digits(text: str) -> str`

- [normalize_bangla_text()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/bangla_normalizer.py:63>) — Function নাম অনুযায়ী Unicode/spacing/punctuation/digits/source text বা combined Bangla normalization করে।
  - Signature: `normalize_bangla_text(text: str, *, normalize_digits: bool=False) -> str`

- [normalize_source_name()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/bangla_normalizer.py:72>) — Function নাম অনুযায়ী Unicode/spacing/punctuation/digits/source text বা combined Bangla normalization করে।
  - Signature: `normalize_source_name(raw_source: str) -> str \| None`

- [_looks_like_domain()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/bangla_normalizer.py:100>) — Input URL/bare-domain কিনা চিহ্নিত করে canonical host বের করে।
  - Signature: `_looks_like_domain(text: str) -> bool`

- [extract_canonical_domain()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/bangla_normalizer.py:108>) — Input URL/bare-domain কিনা চিহ্নিত করে canonical host বের করে।
  - Signature: `extract_canonical_domain(url_or_domain: str) -> str \| None`

### backend/app/shared/utils/dates.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/dates.py>) · 83 lines

Publication date/time parse করে Asia/Dhaka calendar day, timezone assumption ও provenance-সংশ্লিষ্ট data দেয়।

**Class [ParsedPublication](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/dates.py:36>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `local_date` | `date` | required / instance-assigned |
| `published_at` | `datetime \| None` | required / instance-assigned |
| `has_time` | `bool` | required / instance-assigned |
| `tz_assumed` | `bool` | required / instance-assigned |

- [_offset()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/dates.py:43>) — Parsed date/time timezone offset normalize করে।
  - Signature: `_offset(token: str \| None) -> timezone \| None`

- [parse_publication()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/dates.py:53>) — Code-এর দায়িত্ব-বর্ণনা: Parse a publication timestamp/date string; None if unparseable.
  - Signature: `parse_publication(raw: str \| None) -> ParsedPublication \| None`

### backend/app/shared/utils/domains.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/domains.py>) · 34 lines

Registered source-এর allowed hosts/subdomains যাচাই; অন্য site-এর evidence ঢোকা ঠেকায়।

- [_host()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/domains.py:8>) — URL/domain text থেকে normalized hostname বানায়।
  - Signature: `_host(value: str) -> str`

- [allowed_domains_for()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/domains.py:18>) — Code-এর দায়িত্ব-বর্ণনা: The canonical domain plus any other registered channel for the source (its base_url host and domain-looking aliases).
  - Signature: `allowed_domains_for(normalized_source: str \| None, source_config: dict \| None) -> list[str]`

- [is_allowed_host()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/domains.py:29>) — Code-এর দায়িত্ব-বর্ণনা: True when `host` is, or is a subdomain of, an allowed domain.
  - Signature: `is_allowed_host(host: str, allowed: list[str]) -> bool`

### backend/app/shared/utils/hashing.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/hashing.py>) · 149 lines

Claim/text/URL/search cache-এর deterministic SHA-256 identity; body/scope/date/pipeline/model context identity-তে থাকে।

- [_prepare()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/hashing.py:14>) — Normalized bytes/text/URL থেকে deterministic SHA-256 identity বানানোর helper।
  - Signature: `_prepare(text: str) -> str`

- [sha256_hex()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/hashing.py:18>) — Normalized bytes/text/URL থেকে deterministic SHA-256 identity বানানোর helper।
  - Signature: `sha256_hex(value: str) -> str`

- [_canon_text()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/hashing.py:22>) — Code-এর দায়িত্ব-বর্ণনা: The one text normalisation used for claim identity. Idempotent, so a caller may pass raw or already-normalised text and get the same hash.
  - Signature: `_canon_text(text: str \| None) -> str`

- [claim_identity_payload()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/hashing.py:32>) — Code-এর দায়িত্ব-বর্ণনা: The structured fields that make two verification runs interchangeable. A complete result may only be reused when every one of these is equal: normalised headline, normalised submitted body (only when the scope includes one), canonical claimed source, claimed publication date, claim scope, and the pipeline/model version.
  - Signature: `claim_identity_payload(headline: str, claimed_source: str, claim_scope: 'ClaimScope', *, body: str \| None=None, published_date: 'date \| str \| None'=None, version: str \| None=None) -> dict`

- [compute_claim_hash()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/hashing.py:65>) — Code-এর দায়িত্ব-বর্ণনা: Identity of a claim for caching/deduplication — deterministic structured serialisation (sorted-key JSON), never ambiguous string concatenation. This is the single identity function: S01, the async registration path, S02 (Redis + DB), S12 write-back and the photo-card flow all call it.
  - Signature: `compute_claim_hash(headline: str, claimed_source: str, claim_scope: 'ClaimScope', *, body: str \| None=None, published_date: 'date \| str \| None'=None, version: str \| None=None) -> str`

- [compute_url_hash()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/hashing.py:90>) — Normalized bytes/text/URL থেকে deterministic SHA-256 identity বানানোর helper।
  - Signature: `compute_url_hash(url: str) -> str`

- [compute_text_hash()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/hashing.py:96>) — Normalized bytes/text/URL থেকে deterministic SHA-256 identity বানানোর helper।
  - Signature: `compute_text_hash(text: str) -> str`

- [compute_search_query_hash()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/hashing.py:100>) — Code-এর দায়িত্ব-বর্ণনা: Search-result cache key. The date is part of the key because a date-bound query is only valid for the date it was issued with.
  - Signature: `compute_search_query_hash(provider: str, query: str, published_date: 'date \| None'=None) -> str`

- [_strip_tracking_params()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/hashing.py:136>) — URL থেকে tracking-only query parameters বাদ দেয়।
  - Signature: `_strip_tracking_params(url: str) -> str`

### backend/app/shared/utils/headline_preview.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/headline_preview.py>) · 18 lines

Headline-এর প্রথম কয়েকটি শব্দ থেকে consistent preview বানায়।

- [headline_preview()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/headline_preview.py:10>) — Code-এর দায়িত্ব-বর্ণনা: The first `words` whitespace-separated words of `headline`, followed by "..." only when more words exist. Works for Bangla and English alike: `str.split()` splits on every Unicode whitespace character (including no-break spaces) and collapses runs of it. Returns "" for a blank headline.
  - Signature: `headline_preview(headline: str \| None, words: int=PREVIEW_WORDS) -> str`

### backend/app/shared/utils/keyword_extractor.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_extractor.py>) · 226 lines

YAKE/headline keyword ও frequency fallback; retrieval overlap score।

- [_get_yake_extractor()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_extractor.py:139>) — YAKE keyword extractor তৈরি/ব্যবহার করে ranked keywords নেয়।
  - Signature: `_get_yake_extractor(language: str, max_ngram_size: int, dedup_threshold: float, num_keywords: int) -> yake.KeywordExtractor`

- [extract_keywords_yake()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_extractor.py:156>) — YAKE keyword extractor তৈরি/ব্যবহার করে ranked keywords নেয়।
  - Signature: `extract_keywords_yake(text: str, *, language: str='bn', max_ngram_size: int=2, dedup_threshold: float=0.9, num_keywords: int=10) -> list[str]`

- [extract_headline_keywords()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_extractor.py:180>) — Headline-এর useful content keywords সংগ্রহ করে।
  - Signature: `extract_headline_keywords(headline: str, *, top_n: int=6) -> list[str]`

- [compute_keyword_overlap()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_extractor.py:192>) — দুই keyword collection-এর overlap ratio হিসাব করে।
  - Signature: `compute_keyword_overlap(keywords_a: list[str], keywords_b: list[str]) -> float`

- [_fallback_frequency_keywords()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_extractor.py:212>) — Primary keyword extraction না চললে token frequency-ভিত্তিক keywords নেয়।
  - Signature: `_fallback_frequency_keywords(text: str, *, top_n: int=10, min_len: int=2) -> list[str]`

### backend/app/shared/utils/keyword_search.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_search.py>) · 114 lines

Bangla-aware multi-keyword SQL filtering/ranking, Unicode spellings ও LIKE escaping।

- [normalize_query()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_search.py:30>) — Search query Unicode/whitespace normalize করে।
  - Signature: `normalize_query(text: str \| None) -> str`

- [split_keywords()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_search.py:34>) — Code-এর দায়িত্ব-বর্ণনা: Unique meaningful keywords, in query order.
  - Signature: `split_keywords(text: str \| None) -> list[str]`

- [escape_like()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_search.py:53>) — SQL LIKE-এর special characters escape করে literal search নিরাপদ/সঠিক রাখে।
  - Signature: `escape_like(term: str) -> str`

- [spellings()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_search.py:63>) — Code-এর দায়িত্ব-বর্ণনা: The term as typed in NFC, plus its precomposed-nukta spelling if different.
  - Signature: `spellings(term: str) -> list[str]`

- [_contains()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_search.py:72>) — Token-sequence/window অথবা SQL substring matching-এর local helper; সংশ্লিষ্ট class/file অনুযায়ী ব্যবহার হয়।
  - Signature: `_contains(column, term: str) -> ColumnElement[bool]`

**Class [KeywordSearch](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_search.py:76>)** · inherits `plain class`

দায়িত্ব/contract: `condition` filters (OR of keywords over the columns, or None when the query has no usable keyword); `order_by` ranks matches.

- [KeywordSearch.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_search.py:80>) — এই object-এর dependencies/configuration ধরে এবং প্রয়োজনীয় initial state তৈরি করে।
  - Signature: `__init__(self, query: str \| None, columns: list, *, headline_column=None) -> None`

- [KeywordSearch.active()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_search.py:88>) — Keyword query-তে meaningful search terms আছে কি না জানায়।
  - Signature: `active(self) -> bool`

- [KeywordSearch._any_column()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_search.py:91>) — Search keywords দিয়ে SQL column conditions/relevance ordering তৈরি করে।
  - Signature: `_any_column(self, term: str) -> ColumnElement[bool]`

- [KeywordSearch.condition()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_search.py:95>) — Search keywords দিয়ে SQL column conditions/relevance ordering তৈরি করে।
  - Signature: `condition(self) -> ColumnElement[bool] \| None`

- [KeywordSearch.order_by()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/keyword_search.py:100>) — Search keywords দিয়ে SQL column conditions/relevance ordering তৈরি করে।
  - Signature: `order_by(self) -> list`

### backend/app/shared/utils/text_cleaner.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/text_cleaner.py>) · 135 lines

Scraped article-এর noise/boilerplate/whitespace পরিষ্কার, title clean ও NLI-length truncation।

- [clean_extracted_text()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/text_cleaner.py:53>) — Scraped body/title-এর noise/boilerplate ও whitespace পরিষ্কার করে।
  - Signature: `clean_extracted_text(text: str, *, remove_boilerplate: bool=True, min_length: int \| None=None) -> str \| None`

- [clean_title()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/text_cleaner.py:81>) — Scraped body/title-এর noise/boilerplate ও whitespace পরিষ্কার করে।
  - Signature: `clean_title(title: str \| None) -> str \| None`

- [truncate_for_nli()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/text_cleaner.py:92>) — Model input character budget অনুযায়ী text ছোট করে।
  - Signature: `truncate_for_nli(text: str, *, max_chars: int=1500) -> str`

- [_remove_boilerplate()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/text_cleaner.py:110>) — Scraped body/title-এর noise/boilerplate ও whitespace পরিষ্কার করে।
  - Signature: `_remove_boilerplate(text: str) -> str`

- [_normalise_whitespace()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/shared/utils/text_cleaner.py:129>) — Scraped body/title-এর noise/boilerplate ও whitespace পরিষ্কার করে।
  - Signature: `_normalise_whitespace(text: str) -> str`

### backend/run.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/run.py>) · 10 lines

Uvicorn দিয়ে app.main:app launch; Windows event-loop/server configuration। Module-level main block চলে; নিচে declarations আছে।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/scripts/fix_source_configs.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/fix_source_configs.py>) · 189 lines

One-off maintenance script: repairs verified_sources rows whose article_url_patterns / body_selectors / internal_search_url drifted out of sync with the live site after a redesign. See the investigation notes in the accompanying commit/PR description for how each fix was verified against the live site. prothomalo.com is deliberately not touched. Usage: python scripts/fix_source_configs.py

- [main()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/fix_source_configs.py:25>) — Maintenance script-এর operation orchestration/CLI entry point।
  - Signature: `async main() -> None`

- [_update()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/fix_source_configs.py:45>) — Source record-এর supplied configuration fields update করে।
  - Signature: `async _update(conn: asyncpg.Connection, canonical_name: str, *, article_url_patterns: list[str] \| None=None, body_selectors: list[str] \| None=None, internal_search_url: str \| object=...) -> None`

- [_fix_mzamin()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/fix_source_configs.py:80>) — নির্দিষ্ট publisher-এর stored selectors/search configuration সংশোধন করে।
  - Signature: `async _fix_mzamin(conn: asyncpg.Connection) -> None`

- [_fix_kalerkantho()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/fix_source_configs.py:95>) — নির্দিষ্ট publisher-এর stored selectors/search configuration সংশোধন করে।
  - Signature: `async _fix_kalerkantho(conn: asyncpg.Connection) -> None`

- [_fix_jugantor()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/fix_source_configs.py:113>) — নির্দিষ্ট publisher-এর stored selectors/search configuration সংশোধন করে।
  - Signature: `async _fix_jugantor(conn: asyncpg.Connection) -> None`

- [_fix_dailystar()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/fix_source_configs.py:134>) — নির্দিষ্ট publisher-এর stored selectors/search configuration সংশোধন করে।
  - Signature: `async _fix_dailystar(conn: asyncpg.Connection) -> None`

- [_fix_ittefaq()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/fix_source_configs.py:143>) — নির্দিষ্ট publisher-এর stored selectors/search configuration সংশোধন করে।
  - Signature: `async _fix_ittefaq(conn: asyncpg.Connection) -> None`

- [_fix_dailyinqilab()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/fix_source_configs.py:158>) — নির্দিষ্ট publisher-এর stored selectors/search configuration সংশোধন করে।
  - Signature: `async _fix_dailyinqilab(conn: asyncpg.Connection) -> None`

- [_fix_dailynayadiganta()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/fix_source_configs.py:172>) — নির্দিষ্ট publisher-এর stored selectors/search configuration সংশোধন করে।
  - Signature: `async _fix_dailynayadiganta(conn: asyncpg.Connection) -> None`

### backend/scripts/report_verification_timings.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/report_verification_timings.py>) · 90 lines

Read-only timing report. Run from backend: python scripts/report_verification_timings.py. No claims are rerun and no user text or account data is included.

- [report()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/report_verification_timings.py:21>) — Stored verification timings থেকে read-only report তৈরি করে।
  - Signature: `async report(limit: int) -> str`

### backend/scripts/reset_operational_data.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/reset_operational_data.py>) · 164 lines

Explicit, backed-up maintenance reset for the 2026-10-03 schema cleanup. Stop all API/worker processes first. Run from backend with --apply. A database override allows rehearsal on a restored copy. No source/weight/config seeding.

- [snapshot()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/reset_operational_data.py:43>) — Operational tables-এর reset-পূর্ব snapshot সংগ্রহ করে।
  - Signature: `snapshot(connection, table)`

- [backup()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/reset_operational_data.py:67>) — Reset-পূর্ব data backup file তৈরি করে।
  - Signature: `backup(url, destination)`

- [main()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/reset_operational_data.py:85>) — Maintenance script-এর operation orchestration/CLI entry point।
  - Signature: `main()`

### backend/scripts/seed_verified_sources.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/seed_verified_sources.py>) · 90 lines

Registered publisher configuration থেকে verified source database seed/update করার maintenance script।

- [seed_verified_sources()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/scripts/seed_verified_sources.py:19>) — Configured verified publisher rows seed/update করে।
  - Signature: `async seed_verified_sources() -> None`

## Migrations: historical schema/data changes

### backend/app/db/migrations/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/__init__.py>) · 0 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

### backend/app/db/migrations/env.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/env.py>) · 72 lines

Alembic environment, metadata ও offline/online migration connection wiring।

- [run_migrations_offline()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/env.py:28>) — Alembic offline mode-এ migration চালায়।
  - Signature: `run_migrations_offline() -> None`

- [run_migrations_online()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/env.py:45>) — Alembic online mode-এ migration চালায়।
  - Signature: `run_migrations_online() -> None`

### backend/app/db/migrations/versions/20260607_1047_c64e7a11f599_initial_schema.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260607_1047_c64e7a11f599_initial_schema.py>) · 755 lines

Alembic schema/data migration: 20260607_1047_c64e7a11f599_initial_schema। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260607_1047_c64e7a11f599_initial_schema.py:11>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260607_1047_c64e7a11f599_initial_schema.py:676>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20260608_1535_31eca564c430_add_searxng_to_search_provider_enum.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260608_1535_31eca564c430_add_searxng_to_search_provider_enum.py>) · 17 lines

Alembic schema/data migration: 20260608_1535_31eca564c430_add_searxng_to_search_provider_enum। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260608_1535_31eca564c430_add_searxng_to_search_provider_enum.py:10>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260608_1535_31eca564c430_add_searxng_to_search_provider_enum.py:15>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20260608_1554_c8bfea04d45d_add_new_search_providers.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260608_1554_c8bfea04d45d_add_new_search_providers.py>) · 22 lines

Alembic schema/data migration: 20260608_1554_c8bfea04d45d_add_new_search_providers। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260608_1554_c8bfea04d45d_add_new_search_providers.py:10>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260608_1554_c8bfea04d45d_add_new_search_providers.py:21>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20260615_1221_rename_and_add_scraping.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260615_1221_rename_and_add_scraping.py>) · 111 lines

Alembic schema/data migration: 20260615_1221_rename_and_add_scraping। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260615_1221_rename_and_add_scraping.py:11>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260615_1221_rename_and_add_scraping.py:75>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20260623_0900_a1b2c3d4e5f6_add_multimodal_predictions.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260623_0900_a1b2c3d4e5f6_add_multimodal_predictions.py>) · 125 lines

Alembic schema/data migration: 20260623_0900_a1b2c3d4e5f6_add_multimodal_predictions। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260623_0900_a1b2c3d4e5f6_add_multimodal_predictions.py:11>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260623_0900_a1b2c3d4e5f6_add_multimodal_predictions.py:118>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20260706_2325_3e7f64e4c47d_add_missing_tables.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260706_2325_3e7f64e4c47d_add_missing_tables.py>) · 665 lines

Alembic schema/data migration: 20260706_2325_3e7f64e4c47d_add_missing_tables। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260706_2325_3e7f64e4c47d_add_missing_tables.py:11>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260706_2325_3e7f64e4c47d_add_missing_tables.py:534>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20260706_2345_f89542b9b55a_add_site_restricted_to_query_type_enum.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260706_2345_f89542b9b55a_add_site_restricted_to_query_type_enum.py>) · 15 lines

Alembic schema/data migration: 20260706_2345_f89542b9b55a_add_site_restricted_to_query_type_enum। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260706_2345_f89542b9b55a_add_site_restricted_to_query_type_enum.py:10>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260706_2345_f89542b9b55a_add_site_restricted_to_query_type_enum.py:14>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20260707_1200_seed_admin_user_001.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260707_1200_seed_admin_user_001.py>) · 51 lines

Alembic schema/data migration: 20260707_1200_seed_admin_user_001। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260707_1200_seed_admin_user_001.py:19>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260707_1200_seed_admin_user_001.py:46>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20260707_2130_be6f76179d91_add_internal_site_to_search_provider_.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260707_2130_be6f76179d91_add_internal_site_to_search_provider_.py>) · 18 lines

Alembic schema/data migration: 20260707_2130_be6f76179d91_add_internal_site_to_search_provider_। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260707_2130_be6f76179d91_add_internal_site_to_search_provider_.py:10>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260707_2130_be6f76179d91_add_internal_site_to_search_provider_.py:17>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20260728_1014_140d46863ca2_add_source_fields.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260728_1014_140d46863ca2_add_source_fields.py>) · 47 lines

Alembic schema/data migration: 20260728_1014_140d46863ca2_add_source_fields। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260728_1014_140d46863ca2_add_source_fields.py:10>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260728_1014_140d46863ca2_add_source_fields.py:43>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20260806_1314_9624a66f7531_add_pdf_schema_tables.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260806_1314_9624a66f7531_add_pdf_schema_tables.py>) · 271 lines

Alembic schema/data migration: Add DatabaseDescription.pdf schema — submissions, source_evidence_queries, retrieved_articles_v2, ocr_extractions, multimodal_analysis, verification_results_v2, credibility_weight_tiers, expert_profiles, expert_reviews_v2, and additive columns on users. Additive-only migration: every table here is new. The `_v2` suffix on retrieved_articles/verification_results/expert_reviews avoids colliding with the legacy tables of the same (unsuffixed) name, which the live verification pipeline keeps using untouched. Nothing in `verified_sources` is touched by this migration.। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260806_1314_9624a66f7531_add_pdf_schema_tables.py:22>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260806_1314_9624a66f7531_add_pdf_schema_tables.py:218>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20260806_1415_9ed4fe39e0e9_cutover_backfill_pdf_schema.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260806_1415_9ed4fe39e0e9_cutover_backfill_pdf_schema.py>) · 290 lines

Alembic schema/data migration: Cut over to the PDF schema: backfill legacy data into the new tables (reusing primary keys so existing /verify/{id} and /multimodal/predict/{id} links keep resolving), repoint verification_logs at submissions, add the multimodal dedup column, and seed default credibility weight tiers. Legacy tables (verified_claims, search_queries, retrieved_articles, verification_results, expert_reviews, credibility_scores, multimodal_predictions) are left untouched with their data — only read from, never modified or dropped. verified_sources is not touched at all.। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260806_1415_9ed4fe39e0e9_cutover_backfill_pdf_schema.py:21>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260806_1415_9ed4fe39e0e9_cutover_backfill_pdf_schema.py:227>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20260930_1800_b3f1c9a2d4e7_add_3d_verdict_model.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260930_1800_b3f1c9a2d4e7_add_3d_verdict_model.py>) · 185 lines

Alembic schema/data migration: Replace the single TRUE/FALSE/PARTIALLY_TRUE/NOT_FOUND_IN_CLAIMED_SOURCE verdict with a 3-dimensional model on verification_results_v2: source_status (CONFIRMED | NOT_FOUND) content_status (MATCHED | ALTERED, set only when source is CONFIRMED) date_status (MATCHED | MISMATCHED, set only when both dates are known) final_label is renamed to ai_consensus_label and kept: it now serves only as the single-category input the pre-existing expert-review weighted-consensus vote expects (see app/features/verification/verdict_compat.py), not as the verdict returned to end users. Existing rows are backfilled from their old final_label value so no verification history is lost; date_status cannot be backfilled (the source article's publication date was not persisted separately before this migration) and … (পূর্ণ docstring source-এ)। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260930_1800_b3f1c9a2d4e7_add_3d_verdict_model.py:42>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20260930_1800_b3f1c9a2d4e7_add_3d_verdict_model.py:145>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20261001_0900_c4a2d8f1e9b3_structured_expert_votes.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_0900_c4a2d8f1e9b3_structured_expert_votes.py>) · 151 lines

Alembic schema/data migration: 20261001_0900_c4a2d8f1e9b3_structured_expert_votes। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_0900_c4a2d8f1e9b3_structured_expert_votes.py:16>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_0900_c4a2d8f1e9b3_structured_expert_votes.py:112>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20261001_1400_d7e3b5f0a1c6_overall_verdict_and_voting_config.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_1400_d7e3b5f0a1c6_overall_verdict_and_voting_config.py>) · 184 lines

Alembic schema/data migration: Add the Overall verdict dimension (FAKE | REAL | MISLEADING | ALTERED) that experts vote on for EVERY submission type, independent of the (Source, Content, Date) structured vote that additionally exists for SOURCE_BASED / PHOTO_CARD claims: expert_reviews_v2.vote_overall_verdict / ai_overall_verdict — NOT NULL, all types. vote_source_status / ai_source_status are relaxed to nullable since MULTIMODAL votes never set them. verification_results_v2.overall_verdict — nullable; written only once expert review finalizes a SOURCE_BASED/PHOTO_CARD claim. multimodal_analysis.expert_overall_verdict — nullable; written only once expert review finalizes a MULTIMODAL claim (which, before this migration, had no expert-review step at all). Also adds voting_config, a single-row admin-configurable table hol… (পূর্ণ docstring source-এ)। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_1400_d7e3b5f0a1c6_overall_verdict_and_voting_config.py:42>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_1400_d7e3b5f0a1c6_overall_verdict_and_voting_config.py:167>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20261001_1800_e2f4c7a9b3d1_voting_engine_foundations.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_1800_e2f4c7a9b3d1_voting_engine_foundations.py>) · 196 lines

Alembic schema/data migration: Phase 1/2 foundations for the full voting engine spec: verification_results_v2: Adds final_source_status / final_content_status / final_date_status / finalized_at. Before this migration, ExpertReviewService._finalize_submission overwrote source_status/content_status/date_status directly with the expert consensus, destroying the AI's original call — there is no way to recover that lost original value for already-finalized rows, but a check confirmed zero SOURCE_BASED/PHOTO_CARD submissions have been finalized under the old code (the only 5 existing FINALIZED rows are pre-existing MULTIMODAL ones, whose prediction field was never touched), so no backfill is needed. Going forward, source_status/content_status/ date_status are an immutable AI snapshot and final_* holds the expert consensus onc… (পূর্ণ docstring source-এ)। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_1800_e2f4c7a9b3d1_voting_engine_foundations.py:47>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_1800_e2f4c7a9b3d1_voting_engine_foundations.py:174>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20261001_2000_f8a1d3c5e7b2_no_automated_overall_verdict.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_2000_f8a1d3c5e7b2_no_automated_overall_verdict.py>) · 42 lines

Alembic schema/data migration: Business-rule correction: the automated system never decides an Overall verdict (Fake/Real/Misleading/Altered) for SOURCE_BASED or PHOTO_CARD claims. It only ever produces the three structured checks (source_status/ content_status/date_status) — Overall is exclusively an expert-review outcome for those two types, with no AI-implied default to vote-tie-break toward or display as a preliminary suggestion. expert_reviews_v2.ai_overall_verdict was NOT NULL (a derived "AI-implied Overall" was snapshotted on every vote, for every submission type). It is relaxed to nullable here: MULTIMODAL votes continue to populate it (that model's binary FAKE/NON_FAKE call is a separate, pre-existing, unaffected design), while SOURCE_BASED/PHOTO_CARD votes going forward leave it NULL. No backfill: existing SOU… (পূর্ণ docstring source-এ)। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_2000_f8a1d3c5e7b2_no_automated_overall_verdict.py:32>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_2000_f8a1d3c5e7b2_no_automated_overall_verdict.py:36>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20261001_2200_a3c6e9f1b4d8_add_incomplete_check_state.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_2200_a3c6e9f1b4d8_add_incomplete_check_state.py>) · 47 lines

Alembic schema/data migration: Add INCOMPLETE as a third value to source_status_enum / content_status_enum / date_status_enum. Business rule: a search/retrieval/extraction failure must never be reported as a confident negative result. Previously, source_status could only be CONFIRMED or NOT_FOUND — a total search-provider outage and a clean, thorough, genuinely-empty search were indistinguishable, and both collapsed to NOT_FOUND. INCOMPLETE now represents "the check could not be completed", distinct from "the check completed and found nothing" (NOT_FOUND) or "the check completed and found something" (CONFIRMED/MATCHED/MISMATCHED). content_status/date_status gain the same third value for the analogous reason: evidence needed to compare content, or to compare dates, may itself be unavailable (unextractable article body, m… (পূর্ণ docstring source-এ)। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_2200_a3c6e9f1b4d8_add_incomplete_check_state.py:34>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_2200_a3c6e9f1b4d8_add_incomplete_check_state.py:40>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20261001_2330_b7d2e4f6a8c1_add_manipulation_flags_column.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_2330_b7d2e4f6a8c1_add_manipulation_flags_column.py>) · 42 lines

Alembic schema/data migration: Durably persist S10's manipulation-detection result. manipulation_flags (the 4 booleans plus the newly-added alteration-detail lists — which claimed numbers weren't found in the article and the closest number it did contain, which same-type entities were substituted) previously lived only in the Redis result cache, written by PersistenceStage._update_redis_cache. Once that cache entry's TTL expired, GET /verify/{id} and the photo-card equivalent would silently fall back to an all-False ManipulationFlagsSchema() — an older claim would appear to have no detected manipulation even when the original run found some, with nothing for an expert reviewing it later to see. This column is the durable, authoritative source going forward; the Redis cache remains a fast-path best-effort read for a resu… (পূর্ণ docstring source-এ)। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_2330_b7d2e4f6a8c1_add_manipulation_flags_column.py:34>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261001_2330_b7d2e4f6a8c1_add_manipulation_flags_column.py:41>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20261002_0100_c9e1f3a5b7d4_photocard_extraction_provenance.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261002_0100_c9e1f3a5b7d4_photocard_extraction_provenance.py>) · 54 lines

Alembic schema/data migration: Record photo-card extraction provenance on ocr_extractions. The unattended Gemini extraction flow (gemini_extractor.py) needs somewhere to record which extractor actually produced the final headline (Gemini vs the existing deterministic fallback), the Gemini model version used, any extraction-time warnings, and any image-detected source/date text — kept separately from the user's own claimed_source_text/published_date on submissions, since those user-provided values are the verification targets and must never be silently overwritten by what the card's own text implies. A conflict between the two is recorded in extraction_warnings, not resolved. No backfill: historical rows predate this flow and have nothing to recover for these columns; they read back as NULL.। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261002_0100_c9e1f3a5b7d4_photocard_extraction_provenance.py:30>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261002_0100_c9e1f3a5b7d4_photocard_extraction_provenance.py:49>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20261002_1200_d1a7c3e5f9b2_scope_aware_results_and_jobs.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261002_1200_d1a7c3e5f9b2_scope_aware_results_and_jobs.py>) · 154 lines

Alembic schema/data migration: Scope-aware component scores, durable result analysis, and durable jobs. * verification_results_v2 gains the applicable component scores that used to live only in Redis (headline/body/passage similarity, keyword coverages), the claim scope and pipeline version they were computed under, and an `analysis_details` JSONB with metric states, check states, selected evidence, NLI output, search accounting and date provenance. Results can therefore be shown identically right after verification, after navigating away, after Redis expiry, and via the database cache fallback. * `pipeline_version` / `claim_scope` are NULL on historical rows. Those rows are kept (nothing is deleted or rewritten) but are never served as fresh results: the pipeline version is part of claim identity, so identity hashes co… (পূর্ণ docstring source-এ)। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261002_1200_d1a7c3e5f9b2_scope_aware_results_and_jobs.py:42>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261002_1200_d1a7c3e5f9b2_scope_aware_results_and_jobs.py:134>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20261003_1200_a6d9e2f4b8c0_retire_legacy_schema.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261003_1200_a6d9e2f4b8c0_retire_legacy_schema.py>) · 54 lines

Alembic schema/data migration: Retire the legacy claim schema and use canonical submission table names. No writes or schema changes to verified_sources or credibility_weight_tiers. Destructive legacy-table removal requires a restorable backup. Operational data reset is a separate, explicit maintenance operation, not a startup task.। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261003_1200_a6d9e2f4b8c0_retire_legacy_schema.py:17>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261003_1200_a6d9e2f4b8c0_retire_legacy_schema.py:53>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20261004_1500_b2f8a4d6c9e1_personal_result_delivery.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261004_1500_b2f8a4d6c9e1_personal_result_delivery.py>) · 51 lines

Alembic schema/data migration: Uncalculated expert credibility and durable personal result delivery.। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261004_1500_b2f8a4d6c9e1_personal_result_delivery.py:12>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261004_1500_b2f8a4d6c9e1_personal_result_delivery.py:46>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20261005_1200_c7e2a9d4f1b3_headline_alteration_and_body_scores.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261005_1200_c7e2a9d4f1b3_headline_alteration_and_body_scores.py>) · 158 lines

Alembic schema/data migration: Headline Alteration + body similarity scores; Gemini-first photo-card extraction. 1. Purges every submission and the data that exists only because of a submission: verification results/jobs, retrieved articles, search queries, OCR/extraction records, expert reviews, multimodal analyses, result deliveries and the submission notifications. Results computed by the old comparison logic must not survive as if they were Headline Alteration results. Users, verified sources, voting configuration, credibility tiers, expert profiles, tokens and every other table are NOT touched. 2. content_status_enum loses INCOMPLETE: the headline verdict is only MATCHED or ALTERED (a missing verdict is NULL + headline_check_status). 3. verification_results: drops the retired score columns (semantic/entity/ contrad… (পূর্ণ docstring source-এ)। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [_purge_submission_data()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261005_1200_c7e2a9d4f1b3_headline_alteration_and_body_scores.py:64>) — এই historical migration-এ submissions ও dependent operational records মুছে পুরোনো comparison results সরায়; account/source configuration রাখে।

- [_recreate_content_enum()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261005_1200_c7e2a9d4f1b3_headline_alteration_and_body_scores.py:86>) — Content-status enum পুনর্গঠন করে সংশ্লিষ্ট columns নতুন enum type-এ cast করে।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261005_1200_c7e2a9d4f1b3_headline_alteration_and_body_scores.py:97>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261005_1200_c7e2a9d4f1b3_headline_alteration_and_body_scores.py:135>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20261006_0900_d4b8e1f7a2c5_overall_vote_escalation_and_status_labels.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261006_0900_d4b8e1f7a2c5_overall_vote_escalation_and_status_labels.py>) · 158 lines

Alembic schema/data migration: Overall-vote-only decisions, admin escalation, headline status backfill. 1. voting_config.max_tier_weight is dropped — the Max Tier Weight Cap no longer exists anywhere (UI, validation, weighting). 2. expert_reviews.is_admin_decision (default false): marks an administrator's final decision on an ESCALATED claim. 3. submissions.escalated_at: when expert review escalated the claim. Rows already ESCALATED get their last update time as a best estimate. 4. verification_results.headline_exact_match is backfilled for MATCHED rows where it is NULL, so they can be shown as Exact Matched / Meaning Preserved. Exactness is decided only from stored text with the same normalisation as the comparator's exact-match shortcut (NFC, zero-width characters removed, whitespace collapsed, one trailing ।.!? remov… (পূর্ণ docstring source-এ)। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [_exact_key()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261006_0900_d4b8e1f7a2c5_overall_vote_escalation_and_status_labels.py:48>) — Historical exact-match backfill-এর জন্য conservative Unicode/spacing/trailing punctuation normalization করে।

- [_preview()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261006_0900_d4b8e1f7a2c5_overall_vote_escalation_and_status_labels.py:56>) — Historical notification rewrite-এর জন্য পাঁচ শব্দের headline preview তৈরি করে।

- [_backfill_exact_match()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261006_0900_d4b8e1f7a2c5_overall_vote_escalation_and_status_labels.py:62>) — আগের MATCHED rows-এর stored text/analysis থেকে exact-match flag backfill করে।

- [_rewrite_generic_notifications()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261006_0900_d4b8e1f7a2c5_overall_vote_escalation_and_status_labels.py:96>) — পুরোনো generic result notification body-কে সংশ্লিষ্ট headline preview দিয়ে update করে।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261006_0900_d4b8e1f7a2c5_overall_vote_escalation_and_status_labels.py:115>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261006_0900_d4b8e1f7a2c5_overall_vote_escalation_and_status_labels.py:147>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20261006_1800_e5c9a3f7b1d2_photocard_extractions.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261006_1800_e5c9a3f7b1d2_photocard_extractions.py>) · 154 lines

Alembic schema/data migration: Gemini-only photo-card extraction: ocr_extractions -> photocard_extractions. Photo cards are now submitted as an image only. Gemini reads the headline, identifies the claimed outlet among the active verified sources and reads the printed date; those values are stored ONCE, on the submission itself (headline, claimed_source_id / claimed_source_text, published_date). There is no OCR path any more. 1. The table is renamed to ``photocard_extractions`` (its primary key, foreign key and indexes are renamed with it). 2. OCR-specific and duplicate columns are dropped: raw_extracted_text, confirmed_text, ocr_confidence (+ its CHECK), ocr_engine, is_confirmed, fallback_used, extraction_warnings, extractor_used, detected_source_text, detected_date_text. 3. extraction_model_version -> model_version, e… (পূর্ণ docstring source-এ)। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261006_1800_e5c9a3f7b1d2_photocard_extractions.py:50>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261006_1800_e5c9a3f7b1d2_photocard_extractions.py:113>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/20261007_1200_f3b7d1e9a2c4_drop_unused_user_fields.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261007_1200_f3b7d1e9a2c4_drop_unused_user_fields.py>) · 61 lines

Alembic schema/data migration: Drop unused user profile columns and the user_profiles table. users: bio, phone, avatar_url, is_verified, is_email_verified, oauth_provider and oauth_subject were never read by any feature (no OAuth or email-verification flow exists; the settings page no longer edits a bio/phone/avatar). user_profiles only held a duplicate bio/avatar_url and a verification_count that was never incremented. Downgrade recreates the columns/table empty (values are not restorable). Revision ID: f3b7d1e9a2c4 Revises: e5c9a3f7b1d2 Create Date: 2026-10-07 12:00:00। upgrade() forward পরিবর্তন; downgrade() implementation অনুযায়ী reverse/unsupported transition। Historical schema বর্তমান ORM-এর সমান ধরে নেবে না।

- [upgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261007_1200_f3b7d1e9a2c4_drop_unused_user_fields.py:31>) — এই migration-এর forward schema/data changes প্রয়োগ করে।

- [downgrade()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/20261007_1200_f3b7d1e9a2c4_drop_unused_user_fields.py:37>) — এই migration-এর reverse behavior define করে; কিছু historical/data-destructive change পুরোপুরি reversible নয়।

### backend/app/db/migrations/versions/__init__.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/versions/__init__.py>) · 0 lines

Python package marker। সরাসরি runtime function/class নেই; package organization-এর অংশ।

Declared class/function নেই। Module-level imports/configuration/constants-ই এই file-এর কাজ।

## Tests: fixtures, helpers ও scenario index

### backend/tests/conftest.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/conftest.py>) · 39 lines

Pytest fixtures/shared setup: test database, mocked services বা dependency configuration। নিচে প্রতিটি fixture/helper-এর নাম আছে।

- [_jsonb_sqlite()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/conftest.py:33>) — Test setup/fake/helper:  jsonb sqlite; test dependencies বা expected input/output প্রস্তুত করে।

- [_array_sqlite()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/conftest.py:38>) — Test setup/fake/helper:  array sqlite; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/helpers/db.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/db.py>) · 196 lines

Tests-এর reusable fake/stub/factory helpers; production endpoint নয়।

- [make_session_factory()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/db.py:36>) — File-backed when `path` is given (needed when a background worker and the test use different sessions at once: each session gets its own connection, as in production). In-memory otherwise.

- [store_vectors_as_json()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/db.py:55>) — Let the multimodal embedding columns (Postgres ARRAY) hold lists on SQLite.

- [add_user()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/db.py:61>) — Test setup/fake/helper: add user; test dependencies বা expected input/output প্রস্তুত করে।

- [add_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/db.py:70>) — Test setup/fake/helper: add source; test dependencies বা expected input/output প্রস্তুত করে।

- [add_voting_config()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/db.py:87>) — Test setup/fake/helper: add voting config; test dependencies বা expected input/output প্রস্তুত করে।

- [add_completed_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/db.py:99>) — A submission whose automated check is done (EXPERT_REVIEW) with its result.

- [add_multimodal_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/db.py:162>) — A text-and-image submission with its stored AI prediction.

### backend/tests/helpers/gemini.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/gemini.py>) · 60 lines

Tests-এর reusable fake/stub/factory helpers; production endpoint নয়।

- [gemini_body()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/gemini.py:12>) — Test setup/fake/helper: gemini body; test dependencies বা expected input/output প্রস্তুত করে।

- [quota_429()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/gemini.py:22>) — Test setup/fake/helper: quota 429; test dependencies বা expected input/output প্রস্তুত করে।

**Class [Gemini](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/gemini.py:31>)** · inherits `plain class`

দায়িত্ব/contract: Answers each request with the next scripted item (a body dict, an httpx.Response or an exception to raise) and records every request.

- [Gemini.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/gemini.py:35>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [Gemini.handler()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/gemini.py:39>) — Test setup/fake/helper: handler; test dependencies বা expected input/output প্রস্তুত করে।

- [Gemini.client()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/gemini.py:48>) — Test setup/fake/helper: client; test dependencies বা expected input/output প্রস্তুত করে।

- [Gemini.keys_used()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/gemini.py:51>) — Test setup/fake/helper: keys used; test dependencies বা expected input/output প্রস্তুত করে।

**Class [Sleeps](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/gemini.py:55>)** · inherits `plain class`

- [Sleeps.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/gemini.py:56>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [Sleeps.__call__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/gemini.py:59>) — Test setup/fake/helper:   call  ; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/helpers/multimodal.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/multimodal.py>) · 42 lines

Tests-এর reusable fake/stub/factory helpers; production endpoint নয়।

**Class [TinyLoader](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/multimodal.py:13>)** · inherits `plain class`

- [TinyLoader.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/multimodal.py:17>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [TinyLoader.tokenizer()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/multimodal.py:22>) — Test setup/fake/helper: tokenizer; test dependencies বা expected input/output প্রস্তুত করে।

- [TinyLoader.text_backbone()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/multimodal.py:27>) — Test setup/fake/helper: text backbone; test dependencies বা expected input/output প্রস্তুত করে।

- [TinyLoader.img_backbone()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/multimodal.py:31>) — Test setup/fake/helper: img backbone; test dependencies বা expected input/output প্রস্তুত করে।

- [TinyLoader.classifier()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/multimodal.py:34>) — Test setup/fake/helper: classifier; test dependencies বা expected input/output প্রস্তুত করে।

- [png()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/multimodal.py:39>) — Test setup/fake/helper: png; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/helpers/pipeline.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py>) · 198 lines

Tests-এর reusable fake/stub/factory helpers; production endpoint নয়।

**Class [FakeEmbedder](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:41>)** · inherits `plain class`

- [FakeEmbedder.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:42>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeEmbedder._vec()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:48>) — Test setup/fake/helper:  vec; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeEmbedder.encode_batch()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:55>) — Test setup/fake/helper: encode batch; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeEmbedder.compute_similarity()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:61>) — Test setup/fake/helper: compute similarity; test dependencies বা expected input/output প্রস্তুত করে।

**Class [FakeNLI](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:68>)** · inherits `plain class`

দায়িত্ব/contract: `scripted[(premise, hypothesis)]` wins; identical texts entail; everything else is uninformative. `available=False` -> None.

- [FakeNLI.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:72>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeNLI.predict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:79>) — Test setup/fake/helper: predict; test dependencies বা expected input/output প্রস্তুত করে।

**Class [FakeNER](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:90>)** · inherits `plain class`

দায়িত্ব/contract: Detects any of `known` whose text occurs in the input.

- [FakeNER.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:93>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeNER.extract_mentions()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:97>) — Test setup/fake/helper: extract mentions; test dependencies বা expected input/output প্রস্তুত করে।

- [article()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:103>) — Test setup/fake/helper: article; test dependencies বা expected input/output প্রস্তুত করে।

- [make_context()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:121>) — Test setup/fake/helper: make context; test dependencies বা expected input/output প্রস্তুত করে।

- [run_analysis()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:153>) — S08 -> S12 (everything after retrieval except persistence) over fakes.

- [source_record()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:172>) — A verified_sources row as the pipeline reads it.

**Class [FakeSourceRepo](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:184>)** · inherits `plain class`

দায়িত্ব/contract: In-memory SourceRepository: canonical names, then aliases of active sources.

- [FakeSourceRepo.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:187>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeSourceRepo.get_by_canonical_name()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:190>) — Test setup/fake/helper: get by canonical name; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeSourceRepo.resolve_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:193>) — Test setup/fake/helper: resolve source; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeSourceRepo.list_active()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/pipeline.py:197>) — Test setup/fake/helper: list active; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/helpers/playwright.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py>) · 89 lines

Tests-এর reusable fake/stub/factory helpers; production endpoint নয়।

**Class [_Page](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:17>)** · inherits `plain class`

- [_Page.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:18>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [_Page.goto()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:24>) — Test setup/fake/helper: goto; test dependencies বা expected input/output প্রস্তুত করে।

- [_Page.wait_for_url()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:32>) — Test setup/fake/helper: wait for url; test dependencies বা expected input/output প্রস্তুত করে।

- [_Page.wait_for_timeout()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:38>) — Test setup/fake/helper: wait for timeout; test dependencies বা expected input/output প্রস্তুত করে।

- [_Page.content()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:41>) — Test setup/fake/helper: content; test dependencies বা expected input/output প্রস্তুত করে।

- [_Page.close()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:44>) — Test setup/fake/helper: close; test dependencies বা expected input/output প্রস্তুত করে।

- [install()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:48>) — Install the fake module; returns the list of URLs opened in pages.

**Class [install.Context](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:52>)** · inherits `plain class`

- [install.Context.route()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:53>) — Test setup/fake/helper: route; test dependencies বা expected input/output প্রস্তুত করে।

- [install.Context.new_page()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:56>) — Test setup/fake/helper: new page; test dependencies বা expected input/output প্রস্তুত করে।

- [install.Context.close()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:59>) — Test setup/fake/helper: close; test dependencies বা expected input/output প্রস্তুত করে।

**Class [install.Browser](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:62>)** · inherits `plain class`

- [install.Browser.new_context()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:63>) — Test setup/fake/helper: new context; test dependencies বা expected input/output প্রস্তুত করে।

- [install.Browser.close()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:66>) — Test setup/fake/helper: close; test dependencies বা expected input/output প্রস্তুত করে।

- [install.launch()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:69>) — Test setup/fake/helper: launch; test dependencies বা expected input/output প্রস্তুত করে।

**Class [install.Manager](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:74>)** · inherits `plain class`

- [install.Manager.__aenter__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:75>) — Test setup/fake/helper:   aenter  ; test dependencies বা expected input/output প্রস্তুত করে।

- [install.Manager.__aexit__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:78>) — Test setup/fake/helper:   aexit  ; test dependencies বা expected input/output প্রস্তুত করে।

- [uninstall()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/helpers/playwright.py:87>) — Make `from playwright.async_api import ...` raise ImportError.

### backend/tests/unit/admin/test_admin_dashboard.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/admin/test_admin_dashboard.py>) · 52 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_dashboard_lists_and_counts()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/admin/test_admin_dashboard.py:13>) — Test scenario: dashboard lists and counts। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/admin/test_admin_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/admin/test_admin_service.py>) · 169 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [fast_bcrypt()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/admin/test_admin_service.py:39>) — Test setup/fake/helper: fast bcrypt; test dependencies বা expected input/output প্রস্তুত করে।

- [admin()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/admin/test_admin_service.py:44>) — Test setup/fake/helper: admin; test dependencies বা expected input/output প্রস্তুত করে।

- [new_expert()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/admin/test_admin_service.py:49>) — Test setup/fake/helper: new expert; test dependencies বা expected input/output প্রস্তুত করে।

- [test_expert_accounts_are_created_found_updated_and_switched_off()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/admin/test_admin_service.py:53>) — Test scenario: expert accounts are created found updated and switched off। এই named behavior assertion দিয়ে যাচাই করে।

- [test_expert_search_covers_name_email_and_expertise()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/admin/test_admin_service.py:78>) — Test scenario: expert search covers name email and expertise। এই named behavior assertion দিয়ে যাচাই করে।

- [test_expert_search_covers_name_email_and_expertise.emails()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/admin/test_admin_service.py:83>) — Test setup/fake/helper: emails; test dependencies বা expected input/output প্রস্তুত করে।

- [test_resetting_a_password_ends_the_experts_sessions()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/admin/test_admin_service.py:92>) — Test scenario: resetting a password ends the experts sessions। এই named behavior assertion দিয়ে যাচাই করে।

- [test_platform_statistics_count_only_original_claims()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/admin/test_admin_service.py:105>) — Test scenario: platform statistics count only original claims। এই named behavior assertion দিয়ে যাচাই করে।

- [tier()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/admin/test_admin_service.py:119>) — Test setup/fake/helper: tier; test dependencies বা expected input/output প্রস্তুত করে।

- [test_active_tiers_must_keep_tiling_0_to_100_without_gaps_or_overlaps()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/admin/test_admin_service.py:123>) — Test scenario: active tiers must keep tiling 0 to 100 without gaps or overlaps। এই named behavior assertion দিয়ে যাচাই করে।

- [test_changing_n_rescores_every_expert_at_once()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/admin/test_admin_service.py:156>) — Test scenario: changing n rescores every expert at once। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/auth/test_auth_repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_auth_repository.py>) · 51 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_only_unrevoked_unexpired_tokens_are_valid()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_auth_repository.py:20>) — Test scenario: only unrevoked unexpired tokens are valid। এই named behavior assertion দিয়ে যাচাই করে।

- [test_users_by_email_and_role()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_auth_repository.py:43>) — Test scenario: users by email and role। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/auth/test_auth_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_auth_service.py>) · 149 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [fast_bcrypt()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_auth_service.py:36>) — Test setup/fake/helper: fast bcrypt; test dependencies বা expected input/output প্রস্তুত করে।

- [auth()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_auth_service.py:41>) — Test setup/fake/helper: auth; test dependencies বা expected input/output প্রস্তুত করে।

- [aware()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_auth_service.py:47>) — Test setup/fake/helper: aware; test dependencies বা expected input/output প্রস্তুত করে।

- [test_registration_needs_a_strong_password_and_a_new_email()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_auth_service.py:52>) — Test scenario: registration needs a strong password and a new email। এই named behavior assertion দিয়ে যাচাই করে।

- [test_login_never_reveals_which_part_was_wrong_and_blocks_inactive_accounts()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_auth_service.py:62>) — Test scenario: login never reveals which part was wrong and blocks inactive accounts। এই named behavior assertion দিয়ে যাচাই করে।

- [test_refresh_rotates_with_a_grace_window_and_logout_revokes_at_once()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_auth_service.py:75>) — Test scenario: refresh rotates with a grace window and logout revokes at once। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_inactive_account_cannot_refresh()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_auth_service.py:100>) — Test scenario: an inactive account cannot refresh। এই named behavior assertion দিয়ে যাচাই করে।

- [test_password_reset_code_is_emailed_single_use_and_ends_every_session()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_auth_service.py:108>) — Test scenario: password reset code is emailed single use and ends every session। এই named behavior assertion দিয়ে যাচাই করে।

- [test_otp_generation_gives_up_after_repeated_collisions()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_auth_service.py:132>) — Test scenario: otp generation gives up after repeated collisions। এই named behavior assertion দিয়ে যাচাই করে।

- [test_changing_the_password_needs_the_current_one_and_ends_sessions()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_auth_service.py:140>) — Test scenario: changing the password needs the current one and ends sessions। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/auth/test_security.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_security.py>) · 83 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [fast_bcrypt()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_security.py:23>) — Test setup/fake/helper: fast bcrypt; test dependencies বা expected input/output প্রস্তুত করে।

- [bearer()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_security.py:27>) — Test setup/fake/helper: bearer; test dependencies বা expected input/output প্রস্তুত করে।

- [token()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_security.py:31>) — Test setup/fake/helper: token; test dependencies বা expected input/output প্রস্তুত করে।

- [test_passwords_are_salted_hashes_compared_on_the_first_72_bytes()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_security.py:38>) — Test scenario: passwords are salted hashes compared on the first 72 bytes। এই named behavior assertion দিয়ে যাচাই করে।

- [test_access_tokens_round_trip_and_reject_expired_tampered_or_refresh_tokens()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_security.py:46>) — Test scenario: access tokens round trip and reject expired tampered or refresh tokens। এই named behavior assertion দিয়ে যাচাই করে।

- [users_db()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_security.py:60>) — Test setup/fake/helper: users db; test dependencies বা expected input/output প্রস্তুত করে।

- [test_the_request_user_must_exist_and_be_active()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/auth/test_security.py:65>) — Test scenario: the request user must exist and be active। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/cache/test_cache_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/cache/test_cache_service.py>) · 60 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

**Class [FakeRedis](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/cache/test_cache_service.py:12>)** · inherits `plain class`

- [FakeRedis.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/cache/test_cache_service.py:13>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeRedis.get()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/cache/test_cache_service.py:16>) — Test setup/fake/helper: get; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeRedis.set()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/cache/test_cache_service.py:19>) — Test setup/fake/helper: set; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeRedis.delete()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/cache/test_cache_service.py:22>) — Test setup/fake/helper: delete; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeRedis.ping()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/cache/test_cache_service.py:25>) — Test setup/fake/helper: ping; test dependencies বা expected input/output প্রস্তুত করে।

- [test_claims_searches_and_raw_values_round_trip_with_ttls()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/cache/test_cache_service.py:29>) — Test scenario: claims searches and raw values round trip with ttls। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_unavailable_redis_degrades_to_cache_misses()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/cache/test_cache_service.py:50>) — Test scenario: an unavailable redis degrades to cache misses। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/conftest.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/conftest.py>) · 28 lines

Pytest fixtures/shared setup: test database, mocked services বা dependency configuration। নিচে প্রতিটি fixture/helper-এর নাম আছে।

- [db()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/conftest.py:9>) — Session factory over a fresh in-memory database.

- [session()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/conftest.py:17>) — Test setup/fake/helper: session; test dependencies বা expected input/output প্রস্তুত করে।

- [file_db()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/conftest.py:23>) — Session factory over a file database, for code that opens its own sessions concurrently with the test (background workers).

### backend/tests/unit/core/test_config.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/core/test_config.py>) · 58 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_gemini_budget_is_capped_at_nine_requests()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/core/test_config.py:16>) — Test scenario: gemini budget is capped at nine requests। এই named behavior assertion দিয়ে যাচাই করে।

- [test_gemini_keys_rotate_main_then_numbered_in_order_without_blanks_or_duplicates()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/core/test_config.py:23>) — Test scenario: gemini keys rotate main then numbered in order without blanks or duplicates। এই named behavior assertion দিয়ে যাচাই করে।

- [test_log_level_is_validated()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/core/test_config.py:35>) — Test scenario: log level is validated। এই named behavior assertion দিয়ে যাচাই করে।

- [test_env_example_names_only_real_settings_once_and_leaves_secrets_blank()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/core/test_config.py:41>) — Test scenario: env example names only real settings once and leaves secrets blank। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/core/test_lifespan.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/core/test_lifespan.py>) · 78 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

**Class [_Worker](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/core/test_lifespan.py:15>)** · inherits `plain class`

- [_Worker.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/core/test_lifespan.py:16>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [_Worker.start()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/core/test_lifespan.py:19>) — Test setup/fake/helper: start; test dependencies বা expected input/output প্রস্তুত করে।

- [_Worker.stop()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/core/test_lifespan.py:22>) — Test setup/fake/helper: stop; test dependencies বা expected input/output প্রস্তুত করে।

- [_patches()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/core/test_lifespan.py:26>) — Test setup/fake/helper:  patches; test dependencies বা expected input/output প্রস্তুত করে।

- [test_restartable_and_stops_workers_before_clients_and_engine()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/core/test_lifespan.py:51>) — Test scenario: restartable and stops workers before clients and engine। এই named behavior assertion দিয়ে যাচাই করে।

- [test_unavailable_models_and_storage_never_prevent_startup()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/core/test_lifespan.py:69>) — Test scenario: unavailable models and storage never prevent startup। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/dashboard/test_dashboard_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/dashboard/test_dashboard_service.py>) · 66 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_public_statistics_and_top_sources()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/dashboard/test_dashboard_service.py:23>) — Test scenario: public statistics and top sources। এই named behavior assertion দিয়ে যাচাই করে।

- [test_explorer_rows_show_findings_images_and_only_final_verdicts()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/dashboard/test_dashboard_service.py:43>) — Test scenario: explorer rows show findings images and only final verdicts। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/expert_review/test_escalation.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_escalation.py>) · 74 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [claim()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_escalation.py:27>) — Test setup/fake/helper: claim; test dependencies বা expected input/output প্রস্তুত করে।

- [test_the_time_limit_escalates_once_without_any_vote()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_escalation.py:34>) — Test scenario: the time limit escalates once without any vote। এই named behavior assertion দিয়ে যাচাই করে।

- [test_without_configured_limits_nothing_is_ever_escalated()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_escalation.py:47>) — Test scenario: without configured limits nothing is ever escalated। এই named behavior assertion দিয়ে যাচাই করে।

- [test_the_worker_sweeps_periodically_and_survives_errors()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_escalation.py:54>) — Test scenario: the worker sweeps periodically and survives errors। এই named behavior assertion দিয়ে যাচাই করে।

- [test_the_worker_sweeps_periodically_and_survives_errors.sleep()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_escalation.py:59>) — Test setup/fake/helper: sleep; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/unit/expert_review/test_expert_review_repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_repository.py>) · 80 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [claim()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_repository.py:21>) — Test setup/fake/helper: claim; test dependencies বা expected input/output প্রস্তুত করে।

- [vote()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_repository.py:28>) — Test setup/fake/helper: vote; test dependencies বা expected input/output প্রস্তুত করে।

- [test_only_votes_on_finalized_claims_count_and_correct_means_the_final_verdict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_repository.py:33>) — Test scenario: only votes on finalized claims count and correct means the final verdict। এই named behavior assertion দিয়ে যাচাই করে।

- [test_tiers_resolve_inclusively_among_active_ones_and_config_exists_once()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_repository.py:65>) — Test scenario: tiers resolve inclusively among active ones and config exists once। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/expert_review/test_expert_review_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py>) · 314 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [config()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:48>) — Test setup/fake/helper: config; test dependencies বা expected input/output প্রস্তুত করে।

- [test_finalization_needs_threshold_voters_margin_and_a_unique_leader()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:63>) — Test scenario: finalization needs threshold voters margin and a unique leader। এই named behavior assertion দিয়ে যাচাই করে।

- [test_tally_sums_expert_weights_per_verdict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:67>) — Test scenario: tally sums expert weights per verdict। এই named behavior assertion দিয়ে যাচাই করে।

- [test_review_limits_are_or_ed_and_unset_limits_never_trigger()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:72>) — Test scenario: review limits are or ed and unset limits never trigger। এই named behavior assertion দিয়ে যাচাই করে।

- [setup()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:83>) — Test setup/fake/helper: setup; test dependencies বা expected input/output প্রস্তুত করে।

- [vote()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:96>) — Test setup/fake/helper: vote; test dependencies বা expected input/output প্রস্তুত করে।

- [escalation_notices()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:100>) — Test setup/fake/helper: escalation notices; test dependencies বা expected input/output প্রস্তুত করে।

- [test_agreeing_overall_votes_finalize_whatever_the_supplementary_findings()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:105>) — Test scenario: agreeing overall votes finalize whatever the supplementary findings। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_split_overall_vote_escalates_at_the_vote_limit_and_notifies_admins_once()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:122>) — Test scenario: a split overall vote escalates at the vote limit and notifies admins once। এই named behavior assertion দিয়ে যাচাই করে।

- [test_the_spec_worked_example_with_tier_weights()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:134>) — Test scenario: the spec worked example with tier weights। এই named behavior assertion দিয়ে যাচাই করে।

- [test_weights_activate_after_n_finalized_votes_and_follow_the_admin_tiers()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:150>) — Test scenario: weights activate after n finalized votes and follow the admin tiers। এই named behavior assertion দিয়ে যাচাই করে।

- [test_votes_are_refused_when_they_would_be_unfair_or_incoherent()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:167>) — Test scenario: votes are refused when they would be unfair or incoherent। এই named behavior assertion দিয়ে যাচাই করে।

- [test_multimodal_votes_carry_no_supplementary_findings()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:186>) — Test scenario: multimodal votes carry no supplementary findings। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_administrator_decides_only_escalated_claims_and_that_decision_is_final()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:196>) — Test scenario: an administrator decides only escalated claims and that decision is final। এই named behavior assertion দিয়ে যাচাই করে।

- [test_editing_a_vote_is_owner_only_coherent_and_can_tip_the_decision()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:218>) — Test scenario: editing a vote is owner only coherent and can tip the decision। এই named behavior assertion দিয়ে যাচাই করে।

- [test_history_stats_and_credibility_reflect_final_decisions_only()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:231>) — Test scenario: history stats and credibility reflect final decisions only। এই named behavior assertion দিয়ে যাচাই করে।

- [test_queues_show_each_role_only_what_it_may_act_on()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:250>) — Test scenario: queues show each role only what it may act on। এই named behavior assertion দিয়ে যাচাই করে।

- [test_queue_search_runs_before_pagination_over_every_open_claim()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:270>) — Test scenario: queue search runs before pagination over every open claim। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_queue_item_shows_the_saved_ai_findings_evidence_and_image()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_expert_review_service.py:284>) — Test scenario: a queue item shows the saved ai findings evidence and image। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/expert_review/test_overall_verdict.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_overall_verdict.py>) · 7 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_the_multimodal_model_only_ever_implies_fake_or_real()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_overall_verdict.py:5>) — Test scenario: the multimodal model only ever implies fake or real। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/expert_review/test_public_votes.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_public_votes.py>) · 64 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [review()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_public_votes.py:17>) — Test setup/fake/helper: review; test dependencies বা expected input/output প্রস্তুত করে।

- [test_an_admin_decision_is_published_with_every_vote_and_no_private_data()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_public_votes.py:24>) — Test scenario: an admin decision is published with every vote and no private data। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_copy_shows_its_originals_expert_consensus_and_multimodal_claims_are_supported()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/expert_review/test_public_votes.py:46>) — Test scenario: a copy shows its originals expert consensus and multimodal claims are supported। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/multimodal/test_embedding_extractor.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_embedding_extractor.py>) · 47 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_cosine_similarity_is_clamped_to_0_1()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_embedding_extractor.py:11>) — Test scenario: cosine similarity is clamped to 0 1। এই named behavior assertion দিয়ে যাচাই করে।

- [test_combined_embedding_is_the_unit_normalised_concatenation()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_embedding_extractor.py:19>) — Test scenario: combined embedding is the unit normalised concatenation। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_different_image_is_never_a_duplicate()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_embedding_extractor.py:25>) — Test scenario: a different image is never a duplicate। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_different_image_is_never_a_duplicate.check()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_embedding_extractor.py:30>) — Test setup/fake/helper: check; test dependencies বা expected input/output প্রস্তুত করে।

- [test_features_come_from_both_backbones_and_an_unreadable_image_does_not_fail()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_embedding_extractor.py:42>) — Test scenario: features come from both backbones and an unreadable image does not fail। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/multimodal/test_inference_engine.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_inference_engine.py>) · 39 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_label_and_confidences_follow_the_softmax()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_inference_engine.py:13>) — Test scenario: label and confidences follow the softmax। এই named behavior assertion দিয়ে যাচাই করে।

- [test_reusing_extracted_features_matches_the_full_forward_pass()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_inference_engine.py:20>) — Test scenario: reusing extracted features matches the full forward pass। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_model_failure_is_an_inference_error()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_inference_engine.py:31>) — Test scenario: a model failure is an inference error। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_model_failure_is_an_inference_error.broken()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_inference_engine.py:34>) — Test setup/fake/helper: broken; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/unit/multimodal/test_model_architecture.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_model_architecture.py>) · 24 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_backbones_expose_their_feature_size_and_the_classifier_fuses_both()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_model_architecture.py:10>) — Test scenario: backbones expose their feature size and the classifier fuses both। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/multimodal/test_model_loader.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_model_loader.py>) · 62 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

**Class [Tiny](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_model_loader.py:17>)** · inherits `nn.Module`

- [Tiny.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_model_loader.py:18>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [model_dir()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_model_loader.py:25>) — Test setup/fake/helper: model dir; test dependencies বা expected input/output প্রস্তুত করে।

- [test_weights_load_into_eval_mode_once_per_instance()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_model_loader.py:38>) — Test scenario: weights load into eval mode once per instance। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_missing_or_broken_model_directory_is_an_inference_error()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_model_loader.py:54>) — Test scenario: a missing or broken model directory is an inference error। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/multimodal/test_multimodal_repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_repository.py>) · 37 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_candidates_are_same_version_newest_first()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_repository.py:17>) — Test scenario: candidates are same version newest first। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/multimodal/test_multimodal_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_service.py>) · 125 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [vectors_on_sqlite()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_service.py:29>) — Test setup/fake/helper: vectors on sqlite; test dependencies বা expected input/output প্রস্তুত করে।

- [storage()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_service.py:33>) — Test setup/fake/helper: storage; test dependencies বা expected input/output প্রস্তুত করে।

- [service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_service.py:39>) — Test setup/fake/helper: service; test dependencies বা expected input/output প্রস্তুত করে।

- [predict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_service.py:50>) — Test setup/fake/helper: predict; test dependencies বা expected input/output প্রস্তুত করে।

- [test_a_fresh_prediction_runs_the_backbones_once_and_goes_to_expert_review()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_service.py:54>) — Test scenario: a fresh prediction runs the backbones once and goes to expert review। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_near_identical_upload_reuses_the_earlier_prediction()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_service.py:68>) — Test scenario: a near identical upload reuses the earlier prediction। এই named behavior assertion দিয়ে যাচাই করে।

- [test_acceptance_stores_the_image_submission_and_job_together()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_service.py:80>) — Test scenario: acceptance stores the image submission and job together। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_failed_acceptance_rolls_back_and_removes_the_uploaded_image()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_service.py:91>) — Test scenario: a failed acceptance rolls back and removes the uploaded image। এই named behavior assertion দিয়ে যাচাই করে।

- [test_processing_a_queued_upload_is_idempotent()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_service.py:102>) — Test scenario: processing a queued upload is idempotent। এই named behavior assertion দিয়ে যাচাই করে।

- [test_listing_reports_the_total_not_the_page_size()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_service.py:118>) — Test scenario: listing reports the total not the page size। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/multimodal/test_multimodal_storage_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_storage_service.py>) · 60 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [s3_error()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_storage_service.py:15>) — Test setup/fake/helper: s3 error; test dependencies বা expected input/output প্রস্তুত করে।

- [minio()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_storage_service.py:20>) — Test setup/fake/helper: minio; test dependencies বা expected input/output প্রস্তুত করে।

- [test_upload_uses_a_safe_key_and_the_right_content_type()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_storage_service.py:26>) — Test scenario: upload uses a safe key and the right content type। এই named behavior assertion দিয়ে যাচাই করে।

- [test_bucket_urls_reads_and_deletes()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_storage_service.py:38>) — Test scenario: bucket urls reads and deletes। এই named behavior assertion দিয়ে যাচাই করে।

- [test_storage_failures_are_typed_errors()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_multimodal_storage_service.py:56>) — Test scenario: storage failures are typed errors। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/multimodal/test_preprocessing.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_preprocessing.py>) · 17 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_images_are_resized_and_imagenet_normalised()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/multimodal/test_preprocessing.py:13>) — Test scenario: images are resized and imagenet normalised। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/nlp/test_embedding_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_embedding_service.py>) · 87 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

**Class [FakeModel](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_embedding_service.py:17>)** · inherits `plain class`

- [FakeModel.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_embedding_service.py:18>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeModel.encode()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_embedding_service.py:21>) — Test setup/fake/helper: encode; test dependencies বা expected input/output প্রস্তুত করে।

- [fresh()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_embedding_service.py:28>) — Test setup/fake/helper: fresh; test dependencies বা expected input/output প্রস্তুত করে।

- [cache()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_embedding_service.py:34>) — Test setup/fake/helper: cache; test dependencies বা expected input/output প্রস্তুত করে।

- [test_nothing_is_encoded_before_the_model_loads_and_it_loads_once()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_embedding_service.py:39>) — Test scenario: nothing is encoded before the model loads and it loads once। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_failed_load_is_raised_and_leaves_the_service_unloaded()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_embedding_service.py:52>) — Test scenario: a failed load is raised and leaves the service unloaded। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_failed_load_is_raised_and_leaves_the_service_unloaded.broken()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_embedding_service.py:53>) — Test setup/fake/helper: broken; test dependencies বা expected input/output প্রস্তুত করে।

- [test_vectors_are_cached_by_text_and_cache_trouble_is_ignored()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_embedding_service.py:62>) — Test scenario: vectors are cached by text and cache trouble is ignored। এই named behavior assertion দিয়ে যাচাই করে।

- [test_similarity_is_clipped_and_batches_are_encoded_together()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_embedding_service.py:77>) — Test scenario: similarity is clipped and batches are encoded together। এই named behavior assertion দিয়ে যাচাই করে।

- [hit_vector()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_embedding_service.py:86>) — Test setup/fake/helper: hit vector; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/unit/nlp/test_model_identity.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_model_identity.py>) · 25 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_labse_and_the_legacy_setting_share_the_historic_identity()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_model_identity.py:16>) — Test scenario: labse and the legacy setting share the historic identity। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_different_model_changes_identity_and_cache_namespace()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_model_identity.py:22>) — Test scenario: a different model changes identity and cache namespace। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/nlp/test_ner_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_ner_service.py>) · 94 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [fresh()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_ner_service.py:19>) — Test setup/fake/helper: fresh; test dependencies বা expected input/output প্রস্তুত করে।

- [fake_pipe()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_ner_service.py:24>) — Test setup/fake/helper: fake pipe; test dependencies বা expected input/output প্রস্তুত করে।

- [fake_pipe.pipe()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_ner_service.py:25>) — Test setup/fake/helper: pipe; test dependencies বা expected input/output প্রস্তুত করে।

- [install()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_ner_service.py:36>) — Test setup/fake/helper: install; test dependencies বা expected input/output প্রস্তুত করে।

- [test_labels_map_bio_and_banglatag_types_and_reject_generic_ones()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_ner_service.py:40>) — Test scenario: labels map bio and banglatag types and reject generic ones। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_working_checkpoint_is_usable_and_normalises_surfaces()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_ner_service.py:45>) — Test scenario: a working checkpoint is usable and normalises surfaces। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_checkpoint_failing_its_audit_is_unavailable_not_empty()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_ner_service.py:66>) — Test scenario: a checkpoint failing its audit is unavailable not empty। এই named behavior assertion দিয়ে যাচাই করে।

- [test_long_text_is_chunked_and_inference_errors_are_unavailable()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_ner_service.py:75>) — Test scenario: long text is chunked and inference errors are unavailable। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_load_failure_is_raised()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_ner_service.py:87>) — Test scenario: a load failure is raised। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_load_failure_is_raised.broken()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_ner_service.py:88>) — Test setup/fake/helper: broken; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/unit/nlp/test_nli_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_nli_service.py>) · 67 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [fresh()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_nli_service.py:18>) — Test setup/fake/helper: fresh; test dependencies বা expected input/output প্রস্তুত করে।

- [install()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_nli_service.py:23>) — Test setup/fake/helper: install; test dependencies বা expected input/output প্রস্তুত করে।

- [install.pipe()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_nli_service.py:24>) — Test setup/fake/helper: pipe; test dependencies বা expected input/output প্রস্তুত করে।

- [test_scores_are_mapped_by_label_name_and_inputs_truncated()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_nli_service.py:36>) — Test scenario: scores are mapped by label name and inputs truncated। এই named behavior assertion দিয়ে যাচাই করে।

- [test_unrecognised_labels_or_failures_give_no_scores()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_nli_service.py:48>) — Test scenario: unrecognised labels or failures give no scores। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_load_failure_is_raised()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_nli_service.py:60>) — Test scenario: a load failure is raised। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_load_failure_is_raised.broken()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/nlp/test_nli_service.py:61>) — Test setup/fake/helper: broken; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/unit/notifications/test_notification_delivery.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/notifications/test_notification_delivery.py>) · 117 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [notices()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/notifications/test_notification_delivery.py:20>) — Test setup/fake/helper: notices; test dependencies বা expected input/output প্রস্তুত করে।

- [test_each_stage_is_notified_once_and_the_final_one_is_emailed()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/notifications/test_notification_delivery.py:25>) — Test scenario: each stage is notified once and the final one is emailed। এই named behavior assertion দিয়ে যাচাই করে।

- [test_guests_get_nothing_and_a_reused_copy_follows_its_original()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/notifications/test_notification_delivery.py:49>) — Test scenario: guests get nothing and a reused copy follows its original। এই named behavior assertion দিয়ে যাচাই করে।

- [test_smtp_failures_back_off_and_retry_without_new_notices()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/notifications/test_notification_delivery.py:68>) — Test scenario: smtp failures back off and retry without new notices। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_inactive_account_is_skipped()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/notifications/test_notification_delivery.py:84>) — Test scenario: an inactive account is skipped। এই named behavior assertion দিয়ে যাচাই করে।

- [test_the_worker_reconciles_and_sends_then_survives_errors()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/notifications/test_notification_delivery.py:95>) — Test scenario: the worker reconciles and sends then survives errors। এই named behavior assertion দিয়ে যাচাই করে।

- [test_the_worker_reconciles_and_sends_then_survives_errors.sleep()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/notifications/test_notification_delivery.py:102>) — Test setup/fake/helper: sleep; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/unit/notifications/test_notification_repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/notifications/test_notification_repository.py>) · 30 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_listing_counting_and_marking_never_cross_users()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/notifications/test_notification_repository.py:10>) — Test scenario: listing counting and marking never cross users। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/notifications/test_notification_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/notifications/test_notification_service.py>) · 49 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_the_preliminary_notice_has_one_wording_and_is_written_once()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/notifications/test_notification_service.py:20>) — Test scenario: the preliminary notice has one wording and is written once। এই named behavior assertion দিয়ে যাচাই করে।

- [test_other_types_keep_their_text_and_failures_are_swallowed()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/notifications/test_notification_service.py:37>) — Test scenario: other types keep their text and failures are swallowed। এই named behavior assertion দিয়ে যাচাই করে।

- [test_final_notice_text()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/notifications/test_notification_service.py:47>) — Test scenario: final notice text। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/photocard/test_card_date.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_card_date.py>) · 31 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_complete_dates_parse()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_card_date.py:22>) — Test scenario: complete dates parse। এই named behavior assertion দিয়ে যাচাই করে।

- [test_incomplete_impossible_or_ambiguous_dates_are_not_guessed()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_card_date.py:30>) — Test scenario: incomplete impossible or ambiguous dates are not guessed। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/photocard/test_claim_extraction.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_claim_extraction.py>) · 128 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [gemini_settings()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_claim_extraction.py:35>) — Test setup/fake/helper: gemini settings; test dependencies বা expected input/output প্রস্তুত করে।

- [source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_claim_extraction.py:44>) — Test setup/fake/helper: source; test dependencies বা expected input/output প্রস্তুত করে।

- [repo()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_claim_extraction.py:50>) — Test setup/fake/helper: repo; test dependencies বা expected input/output প্রস্তুত করে।

- [extract()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_claim_extraction.py:59>) — Test setup/fake/helper: extract; test dependencies বা expected input/output প্রস্তুত করে।

- [test_card_values_become_the_claim_and_only_active_sources_are_offered()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_claim_extraction.py:63>) — Test scenario: card values become the claim and only active sources are offered। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_missing_or_partial_date_is_no_date_not_a_failure()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_claim_extraction.py:76>) — Test scenario: a missing or partial date is no date not a failure। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_api_failure_is_its_own_outcome()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_claim_extraction.py:83>) — Test scenario: an api failure is its own outcome। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_readable_headline_without_a_verified_source_uses_the_verified_sources()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_claim_extraction.py:93>) — Test scenario: a readable headline without a verified source uses the verified sources। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_source_deactivated_meanwhile_is_not_accepted()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_claim_extraction.py:102>) — Test scenario: a source deactivated meanwhile is not accepted। এই named behavior assertion দিয়ে যাচাই করে।

- [test_with_the_fallback_off_a_card_needs_a_headline_and_a_verified_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_claim_extraction.py:116>) — Test scenario: with the fallback off a card needs a headline and a verified source। এই named behavior assertion দিয়ে যাচাই করে।

- [test_with_the_fallback_on_a_missing_headline_is_still_rejected()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_claim_extraction.py:124>) — Test scenario: with the fallback on a missing headline is still rejected। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/photocard/test_gemini_image_extractor.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_image_extractor.py>) · 144 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [fresh_key_pools()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_image_extractor.py:31>) — Test setup/fake/helper: fresh key pools; test dependencies বা expected input/output প্রস্তুত করে।

- [extract()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_image_extractor.py:37>) — Test setup/fake/helper: extract; test dependencies বা expected input/output প্রস্তুত করে।

- [test_the_original_image_catalogue_and_anti_hallucination_rules_are_sent()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_image_extractor.py:42>) — Test scenario: the original image catalogue and anti hallucination rules are sent। এই named behavior assertion দিয়ে যাচাই করে।

- [test_nine_failures_are_nine_requests_in_three_paused_batches()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_image_extractor.py:59>) — Test scenario: nine failures are nine requests in three paused batches। এই named behavior assertion দিয়ে যাচাই করে।

- [test_the_first_success_stops_the_loop()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_image_extractor.py:70>) — Test scenario: the first success stops the loop। এই named behavior assertion দিয়ে যাচাই করে।

- [test_each_transient_failure_is_retried()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_image_extractor.py:87>) — Test scenario: each transient failure is retried। এই named behavior assertion দিয়ে যাচাই করে।

- [test_permanent_errors_and_an_exhausted_daily_quota_stop_at_once()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_image_extractor.py:97>) — Test scenario: permanent errors and an exhausted daily quota stop at once। এই named behavior assertion দিয়ে যাচাই করে।

- [test_without_a_key_nothing_is_sent()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_image_extractor.py:103>) — Test scenario: without a key nothing is sent। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_key_at_its_limit_hands_the_next_call_to_the_next_key_at_once()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_image_extractor.py:110>) — Test scenario: a key at its limit hands the next call to the next key at once। এই named behavior assertion দিয়ে যাচাই করে।

- [test_spent_keys_stay_skipped_for_later_cards_and_other_errors_keep_the_key()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_image_extractor.py:118>) — Test scenario: spent keys stay skipped for later cards and other errors keep the key। এই named behavior assertion দিয়ে যাচাই করে।

- [test_rotation_stays_within_nine_requests_and_stops_when_every_key_is_spent()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_image_extractor.py:128>) — Test scenario: rotation stays within nine requests and stops when every key is spent। এই named behavior assertion দিয়ে যাচাই করে।

- [test_mime_type_is_detected_from_the_bytes()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_image_extractor.py:141>) — Test scenario: mime type is detected from the bytes। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/photocard/test_gemini_key_pool.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_key_pool.py>) · 50 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [quota_429()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_key_pool.py:14>) — Test setup/fake/helper: quota 429; test dependencies বা expected input/output প্রস্তুত করে।

- [test_limit_info_tells_daily_from_per_minute_limits()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_key_pool.py:23>) — Test scenario: limit info tells daily from per minute limits। এই named behavior assertion দিয়ে যাচাই করে।

- [test_keys_rotate_and_blocked_keys_are_skipped_until_they_reset()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_key_pool.py:30>) — Test scenario: keys rotate and blocked keys are skipped until they reset। এই named behavior assertion দিয়ে যাচাই করে।

- [test_pools_are_shared_per_key_set_until_reset()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_key_pool.py:45>) — Test scenario: pools are shared per key set until reset। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/photocard/test_gemini_prompt.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_prompt.py>) · 29 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_the_prompt_lists_each_source_with_its_known_names_and_the_schema_restricts_ids()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_prompt.py:15>) — Test scenario: the prompt lists each source with its known names and the schema restricts ids। এই named behavior assertion দিয়ে যাচাই করে।

- [test_values_count_only_when_marked_present_or_identified()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_gemini_prompt.py:23>) — Test scenario: values count only when marked present or identified। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/photocard/test_photocard_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py>) · 296 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [storage()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:45>) — Test setup/fake/helper: storage; test dependencies বা expected input/output প্রস্তুত করে।

**Class [FakeExtractor](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:50>)** · inherits `plain class`

দায়িত্ব/contract: Stands in for Gemini; `result` may be a callable taking the source repo.

- [FakeExtractor.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:56>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeExtractor.extract()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:59>) — Test setup/fake/helper: extract; test dependencies বা expected input/output প্রস্তুত করে।

- [extraction()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:65>) — Test setup/fake/helper: extraction; test dependencies বা expected input/output প্রস্তুত করে।

- [with_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:75>) — Test setup/fake/helper: with source; test dependencies বা expected input/output প্রস্তুত করে।

**Class [FakeOrchestrator](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:80>)** · inherits `plain class`

দায়িত্ব/contract: The shared pipeline over deterministic fakes: real analysis (S08-S12) and the REAL persistence stage. `cache_hit_from` simulates an S02 hit.

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `captured` | `dict` | {} |

- [FakeOrchestrator.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:88>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeOrchestrator.run()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:91>) — Test setup/fake/helper: run; test dependencies বা expected input/output প্রস্তুত করে।

- [fakes()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:109>) — Test setup/fake/helper: fakes; test dependencies বা expected input/output প্রস্তুত করে।

- [session()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:118>) — Test setup/fake/helper: session; test dependencies বা expected input/output প্রস্তুত করে।

- [service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:124>) — Test setup/fake/helper: service; test dependencies বা expected input/output প্রস্তুত করে।

- [accept()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:134>) — Test setup/fake/helper: accept; test dependencies বা expected input/output প্রস্তুত করে।

- [test_acceptance_stores_only_the_image_with_an_owned_submission_and_a_job()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:139>) — Test scenario: acceptance stores only the image with an owned submission and a job। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_image_that_could_not_be_stored_is_not_accepted()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:159>) — Test scenario: an image that could not be stored is not accepted। এই named behavior assertion দিয়ে যাচাই করে।

- [test_the_read_card_becomes_a_saved_headline_only_result()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:165>) — Test scenario: the read card becomes a saved headline only result। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_failed_reading_stops_before_verification_with_its_own_message()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:196>) — Test scenario: a failed reading stops before verification with its own message। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_identical_card_reuses_the_saved_result_but_keeps_its_own_identity()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:214>) — Test scenario: an identical card reuses the saved result but keeps its own identity। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_retry_after_extraction_never_reads_the_card_again()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:230>) — Test scenario: a retry after extraction never reads the card again। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_card_without_a_recognised_outlet_is_checked_against_the_verified_sources()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:241>) — Test scenario: a card without a recognised outlet is checked against the verified sources। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_card_without_a_recognised_outlet_is_checked_against_the_verified_sources.no_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:242>) — Test setup/fake/helper: no source; test dependencies বা expected input/output প্রস্তুত করে।

- [test_a_sourceless_card_resumes_after_a_crash_without_reading_it_again()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:257>) — Test scenario: a sourceless card resumes after a crash without reading it again। এই named behavior assertion দিয়ে যাচাই করে।

- [test_jobs_that_cannot_succeed_fail_permanently_and_unreadable_storage_is_retried()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:269>) — Test scenario: jobs that cannot succeed fail permanently and unreadable storage is retried। এই named behavior assertion দিয়ে যাচাই করে।

- [test_reading_failures_are_explained_in_plain_words()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_service.py:285>) — Test scenario: reading failures are explained in plain words। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/photocard/test_photocard_storage_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_storage_service.py>) · 46 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [minio()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_storage_service.py:16>) — Test setup/fake/helper: minio; test dependencies বা expected input/output প্রস্তুত করে।

- [test_keys_content_types_and_round_trip()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_storage_service.py:22>) — Test scenario: keys content types and round trip। এই named behavior assertion দিয়ে যাচাই করে।

- [test_storage_trouble_is_reported_not_raised()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_storage_service.py:41>) — Test scenario: storage trouble is reported not raised। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/photocard/test_photocard_verification_stages.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_verification_stages.py>) · 71 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_photo_cards_and_text_claims_share_every_stage_but_the_normaliser()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_verification_stages.py:28>) — Test scenario: photo cards and text claims share every stage but the normaliser। এই named behavior assertion দিয়ে যাচাই করে।

- [test_the_card_identity_is_headline_only_and_never_a_text_claims()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_verification_stages.py:37>) — Test scenario: the card identity is headline only and never a text claims। এই named behavior assertion দিয়ে যাচাই করে।

- [test_the_persisted_card_identity_is_stable()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_verification_stages.py:54>) — Test scenario: the persisted card identity is stable। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_real_model_change_changes_the_identity()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/photocard/test_photocard_verification_stages.py:66>) — Test scenario: a real model change changes the identity। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/search/test_internal_site_client.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_internal_site_client.py>) · 57 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [search()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_internal_site_client.py:16>) — Test setup/fake/helper: search; test dependencies বা expected input/output প্রস্তুত করে।

- [search.handler()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_internal_site_client.py:19>) — Test setup/fake/helper: handler; test dependencies বা expected input/output প্রস্তুত করে।

- [test_results_are_on_domain_articles_with_headline_text()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_internal_site_client.py:28>) — Test scenario: results are on domain articles with headline text। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_page_of_unrelated_latest_news_is_not_a_result_set()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_internal_site_client.py:48>) — Test scenario: a page of unrelated latest news is not a result set। এই named behavior assertion দিয়ে যাচাই করে।

- [test_unconfigured_failed_and_empty_searches()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_internal_site_client.py:53>) — Test scenario: unconfigured failed and empty searches। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/search/test_pygooglenews_client.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_pygooglenews_client.py>) · 108 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [clean_cache()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_pygooglenews_client.py:21>) — Test setup/fake/helper: clean cache; test dependencies বা expected input/output প্রস্তুত করে।

**Class [FakeGoogleNews](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_pygooglenews_client.py:27>)** · inherits `plain class`

- [FakeGoogleNews.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_pygooglenews_client.py:28>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeGoogleNews.search()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_pygooglenews_client.py:31>) — Test setup/fake/helper: search; test dependencies বা expected input/output প্রস্তুত করে।

- [client()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_pygooglenews_client.py:38>) — Test setup/fake/helper: client; test dependencies বা expected input/output প্রস্তুত করে।

- [test_query_and_date_window()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_pygooglenews_client.py:46>) — Test scenario: query and date window। এই named behavior assertion দিয়ে যাচাই করে।

- [test_redirects_are_resolved_once_and_unresolvable_ones_fail_the_call()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_pygooglenews_client.py:61>) — Test scenario: redirects are resolved once and unresolvable ones fail the call। এই named behavior assertion দিয়ে যাচাই করে।

- [test_redirects_are_resolved_once_and_unresolvable_ones_fail_the_call.resolver()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_pygooglenews_client.py:64>) — Test setup/fake/helper: resolver; test dependencies বা expected input/output প্রস্তুত করে।

- [test_redirects_are_resolved_once_and_unresolvable_ones_fail_the_call.browser_down()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_pygooglenews_client.py:74>) — Test setup/fake/helper: browser down; test dependencies বা expected input/output প্রস্তুত করে।

- [test_the_browser_follows_the_redirect_and_a_failed_launch_is_retried()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_pygooglenews_client.py:81>) — Test scenario: the browser follows the redirect and a failed launch is retried। এই named behavior assertion দিয়ে যাচাই করে।

- [test_the_browser_follows_the_redirect_and_a_failed_launch_is_retried.no_sleep()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_pygooglenews_client.py:82>) — Test setup/fake/helper: no sleep; test dependencies বা expected input/output প্রস্তুত করে।

- [test_the_browser_follows_the_redirect_and_a_failed_launch_is_retried.counting()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/search/test_pygooglenews_client.py:100>) — Test setup/fake/helper: counting; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/unit/shared/test_article_url_heuristics.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_article_url_heuristics.py>) · 22 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_article_url_classification()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_article_url_heuristics.py:21>) — Test scenario: article url classification। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/shared/test_bangla_normalizer.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_bangla_normalizer.py>) · 36 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_text_normalisation_removes_invisible_chars_and_unifies_punctuation_and_space()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_bangla_normalizer.py:10>) — Test scenario: text normalisation removes invisible chars and unifies punctuation and space। এই named behavior assertion দিয়ে যাচাই করে।

- [test_source_name_resolution()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_bangla_normalizer.py:25>) — Test scenario: source name resolution। এই named behavior assertion দিয়ে যাচাই করে।

- [test_canonical_domain_extraction()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_bangla_normalizer.py:35>) — Test scenario: canonical domain extraction। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/shared/test_base_repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_base_repository.py>) · 49 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

**Class [Sources](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_base_repository.py:12>)** · inherits `BaseRepository[VerifiedSource]`

- [source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_base_repository.py:16>) — Test setup/fake/helper: source; test dependencies বা expected input/output প্রস্তুত করে।

- [test_crud_round_trip()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_base_repository.py:20>) — Test scenario: crud round trip। এই named behavior assertion দিয়ে যাচাই করে।

- [test_unique_violation_is_a_duplicate_record_error()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_base_repository.py:39>) — Test scenario: unique violation is a duplicate record error। এই named behavior assertion দিয়ে যাচাই করে।

- [test_rows_by_submission_maps_one_row_per_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_base_repository.py:46>) — Test scenario: rows by submission maps one row per submission। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/shared/test_dates.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_dates.py>) · 33 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_utc_timestamp_converts_to_the_dhaka_calendar_day()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_dates.py:10>) — Test scenario: utc timestamp converts to the dhaka calendar day। এই named behavior assertion দিয়ে যাচাই করে।

- [test_offsetless_timestamp_assumes_dhaka_and_says_so()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_dates.py:17>) — Test scenario: offsetless timestamp assumes dhaka and says so। এই named behavior assertion দিয়ে যাচাই করে।

- [test_date_forms()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_dates.py:31>) — Test scenario: date forms। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/shared/test_domains.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_domains.py>) · 16 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_allowed_domains_are_the_source_and_its_registered_channels_without_duplicates()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_domains.py:4>) — Test scenario: allowed domains are the source and its registered channels without duplicates। এই named behavior assertion দিয়ে যাচাই করে।

- [test_host_must_be_an_allowed_domain_or_its_subdomain()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_domains.py:10>) — Test scenario: host must be an allowed domain or its subdomain। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/shared/test_email_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_email_service.py>) · 86 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

**Class [FakeSMTP](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_email_service.py:12>)** · inherits `plain class`

| Field | Type | Declaration / default / relationship |
|---|---|---|
| `sent` | `list` | [] |

- [FakeSMTP.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_email_service.py:16>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeSMTP.__enter__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_email_service.py:19>) — Test setup/fake/helper:   enter  ; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeSMTP.__exit__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_email_service.py:22>) — Test setup/fake/helper:   exit  ; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeSMTP.starttls()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_email_service.py:25>) — Test setup/fake/helper: starttls; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeSMTP.login()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_email_service.py:28>) — Test setup/fake/helper: login; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeSMTP.sendmail()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_email_service.py:31>) — Test setup/fake/helper: sendmail; test dependencies বা expected input/output প্রস্তুত করে।

- [smtp()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_email_service.py:38>) — Test setup/fake/helper: smtp; test dependencies বা expected input/output প্রস্তুত করে।

- [service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_email_service.py:44>) — Test setup/fake/helper: service; test dependencies বা expected input/output প্রস্তুত করে।

- [test_unconfigured_otp_is_logged_not_sent_but_result_email_is_refused()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_email_service.py:53>) — Test scenario: unconfigured otp is logged not sent but result email is refused। এই named behavior assertion দিয়ে যাচাই করে।

- [test_otp_is_sent_over_tls_with_a_cleaned_credential()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_email_service.py:61>) — Test scenario: otp is sent over tls with a cleaned credential। এই named behavior assertion দিয়ে যাচাই করে।

- [test_smtp_failure_is_a_typed_delivery_error()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_email_service.py:69>) — Test scenario: smtp failure is a typed delivery error। এই named behavior assertion দিয়ে যাচাই করে।

- [test_result_email_links_to_the_decision_with_a_headline_preview()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_email_service.py:75>) — Test scenario: result email links to the decision with a headline preview। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/shared/test_hashing.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_hashing.py>) · 72 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_golden_values()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_hashing.py:23>) — Test scenario: golden values। এই named behavior assertion দিয়ে যাচাই করে।

- [test_every_identity_field_distinguishes_claims()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_hashing.py:39>) — Test scenario: every identity field distinguishes claims। এই named behavior assertion দিয়ে যাচাই করে।

- [test_identity_is_normalisation_stable_and_unambiguous()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_hashing.py:53>) — Test scenario: identity is normalisation stable and unambiguous। এই named behavior assertion দিয়ে যাচাই করে।

- [test_url_hash_ignores_tracking_params_and_case()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_hashing.py:61>) — Test scenario: url hash ignores tracking params and case। এই named behavior assertion দিয়ে যাচাই করে।

- [test_search_query_hash_depends_on_provider_query_and_date()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_hashing.py:68>) — Test scenario: search query hash depends on provider query and date। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/shared/test_headline_preview.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_headline_preview.py>) · 15 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_headline_preview()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_headline_preview.py:14>) — Test scenario: headline preview। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/shared/test_keyword_extractor.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_keyword_extractor.py>) · 23 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_headline_keywords_are_content_words_and_short_text_has_none()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_keyword_extractor.py:4>) — Test scenario: headline keywords are content words and short text has none। এই named behavior assertion দিয়ে যাচাই করে।

- [test_extractor_failure_falls_back_to_word_frequency()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_keyword_extractor.py:11>) — Test scenario: extractor failure falls back to word frequency। এই named behavior assertion দিয়ে যাচাই করে।

- [test_extractor_failure_falls_back_to_word_frequency.broken()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_keyword_extractor.py:12>) — Test setup/fake/helper: broken; test dependencies বা expected input/output প্রস্তুত করে।

- [test_keyword_overlap_is_case_insensitive_jaccard()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_keyword_extractor.py:20>) — Test scenario: keyword overlap is case insensitive jaccard। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/shared/test_keyword_search.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_keyword_search.py>) · 29 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_keywords_are_unique_meaningful_and_bounded()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_keyword_search.py:8>) — Test scenario: keywords are unique meaningful and bounded। এই named behavior assertion দিয়ে যাচাই করে।

- [test_like_wildcards_are_escaped()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_keyword_search.py:16>) — Test scenario: like wildcards are escaped। এই named behavior assertion দিয়ে যাচাই করে।

- [test_nukta_letters_are_searched_in_both_spellings()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_keyword_search.py:20>) — Test scenario: nukta letters are searched in both spellings। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_stopword_only_query_still_searches_what_was_typed()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_keyword_search.py:25>) — Test scenario: a stopword only query still searches what was typed। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/shared/test_status_labels.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_status_labels.py>) · 10 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_ai_decision_is_only_ever_likely_fake_or_likely_real()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_status_labels.py:5>) — Test scenario: ai decision is only ever likely fake or likely real। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/shared/test_text_cleaner.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_text_cleaner.py>) · 32 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_extracted_text_loses_markup_boilerplate_and_extra_space()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_text_cleaner.py:6>) — Test scenario: extracted text loses markup boilerplate and extra space। এই named behavior assertion দিয়ে যাচাই করে।

- [test_too_short_or_empty_text_is_no_body()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_text_cleaner.py:18>) — Test scenario: too short or empty text is no body। এই named behavior assertion দিয়ে যাচাই করে।

- [test_title_is_single_line_plain_text()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_text_cleaner.py:23>) — Test scenario: title is single line plain text। এই named behavior assertion দিয়ে যাচাই করে।

- [test_nli_truncation_prefers_a_sentence_boundary()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/shared/test_text_cleaner.py:28>) — Test scenario: nli truncation prefers a sentence boundary। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/sources/test_source_repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/sources/test_source_repository.py>) · 20 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_canonical_lookup_and_listings()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/sources/test_source_repository.py:8>) — Test scenario: canonical lookup and listings। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/sources/test_source_resolution.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/sources/test_source_resolution.py>) · 32 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [repo()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/sources/test_source_resolution.py:11>) — Test setup/fake/helper: repo; test dependencies বা expected input/output প্রস্তুত করে।

- [test_resolution_order()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/sources/test_source_resolution.py:25>) — Test scenario: resolution order। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_registry_failure_is_unresolved_not_an_error()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/sources/test_source_resolution.py:31>) — Test scenario: a registry failure is unresolved not an error। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/sources/test_source_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/sources/test_source_service.py>) · 46 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_lifecycle_and_duplicate_protection()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/sources/test_source_service.py:13>) — Test scenario: lifecycle and duplicate protection। এই named behavior assertion দিয়ে যাচাই করে।

- [test_listing_and_search_respect_activity_and_report_matching_totals()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/sources/test_source_service.py:29>) — Test scenario: listing and search respect activity and report matching totals। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/submissions/test_submission_access.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/submissions/test_submission_access.py>) · 26 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_unpublished_work_is_private()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/submissions/test_submission_access.py:17>) — Test scenario: unpublished work is private। এই named behavior assertion দিয়ে যাচাই করে।

- [test_published_results_are_public()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/submissions/test_submission_access.py:25>) — Test scenario: published results are public। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/submissions/test_submission_repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/submissions/test_submission_repository.py>) · 121 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [ranked()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/submissions/test_submission_repository.py:24>) — Test setup/fake/helper: ranked; test dependencies বা expected input/output প্রস্তুত করে।

- [test_keyword_search_ranks_by_distinct_keywords_before_paginating()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/submissions/test_submission_repository.py:43>) — Test scenario: keyword search ranks by distinct keywords before paginating। এই named behavior assertion দিয়ে যাচাই করে।

- [test_keyword_search_is_literal_and_nukta_insensitive()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/submissions/test_submission_repository.py:55>) — Test scenario: keyword search is literal and nukta insensitive। এই named behavior assertion দিয়ে যাচাই করে।

- [test_archive_scope_counts_and_review_filters()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/submissions/test_submission_repository.py:67>) — Test scenario: archive scope counts and review filters। এই named behavior assertion দিয়ে যাচাই করে।

- [test_finding_and_date_filters_use_the_ai_call_and_whole_days()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/submissions/test_submission_repository.py:89>) — Test scenario: finding and date filters use the ai call and whole days। এই named behavior assertion দিয়ে যাচাই করে।

- [test_status_transitions_happen_once()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/submissions/test_submission_repository.py:103>) — Test scenario: status transitions happen once। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/users/test_users_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/users/test_users_service.py>) · 93 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [mine()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/users/test_users_service.py:22>) — Test setup/fake/helper: mine; test dependencies বা expected input/output প্রস্তুত করে।

- [test_my_submissions_are_private_and_filtered_before_paging()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/users/test_users_service.py:29>) — Test scenario: my submissions are private and filtered before paging। এই named behavior assertion দিয়ে যাচাই করে।

- [test_my_submissions_are_private_and_filtered_before_paging.ids()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/users/test_users_service.py:40>) — Test setup/fake/helper: ids; test dependencies বা expected input/output প্রস্তুত করে।

- [test_each_row_shows_ai_findings_and_only_a_final_decision()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/users/test_users_service.py:54>) — Test scenario: each row shows ai findings and only a final decision। এই named behavior assertion দিয়ে যাচাই করে।

- [test_statistics_and_the_profile_total_are_counted_live()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/users/test_users_service.py:81>) — Test scenario: statistics and the profile total are counted live। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/analysis/test_body_similarity.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_body_similarity.py>) · 86 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_identical_bodies_score_one_and_unrelated_bodies_score_low()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_body_similarity.py:23>) — Test scenario: identical bodies score one and unrelated bodies score low। এই named behavior assertion দিয়ে যাচাই করে।

- [test_lexical_metrics_follow_their_documented_formulas()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_body_similarity.py:32>) — Test scenario: lexical metrics follow their documented formulas। এই named behavior assertion দিয়ে যাচাই করে।

- [test_semantic_similarity_keeps_the_raw_cosine_and_chunks_long_text()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_body_similarity.py:47>) — Test scenario: semantic similarity keeps the raw cosine and chunks long text। এই named behavior assertion দিয়ে যাচাই করে।

**Class [test_semantic_similarity_keeps_the_raw_cosine_and_chunks_long_text.Opposite](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_body_similarity.py:48>)** · inherits `FakeEmbedder`

- [test_semantic_similarity_keeps_the_raw_cosine_and_chunks_long_text.Opposite.encode_batch()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_body_similarity.py:49>) — Test setup/fake/helper: encode batch; test dependencies বা expected input/output প্রস্তুত করে।

- [test_missing_bodies_are_never_scored()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_body_similarity.py:67>) — Test scenario: missing bodies are never scored। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_failing_metric_never_discards_the_others()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_body_similarity.py:72>) — Test scenario: a failing metric never discards the others। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_failing_metric_never_discards_the_others.boom()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_body_similarity.py:73>) — Test setup/fake/helper: boom; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/unit/verification/analysis/test_decisions.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_decisions.py>) · 79 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [m()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_decisions.py:24>) — Test setup/fake/helper: m; test dependencies বা expected input/output প্রস্তুত করে।

- [test_correspondence_levels()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_decisions.py:37>) — Test scenario: correspondence levels। এই named behavior assertion দিয়ে যাচাই করে।

- [test_source_decision()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_decisions.py:58>) — Test scenario: source decision। এই named behavior assertion দিয়ে যাচাই করে।

- [test_date_decision_only_applies_to_a_confirmed_source_with_a_claimed_date()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_decisions.py:65>) — Test scenario: date decision only applies to a confirmed source with a claimed date। এই named behavior assertion দিয়ে যাচাই করে।

- [test_search_adequacy_and_strength()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_decisions.py:74>) — Test scenario: search adequacy and strength। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/analysis/test_entities.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_entities.py>) · 36 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [keys()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_entities.py:13>) — Test setup/fake/helper: keys; test dependencies বা expected input/output প্রস্তুত করে।

- [test_match_status()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_entities.py:28>) — Test scenario: match status। এই named behavior assertion দিয়ে যাচাই করে।

- [test_mentions_in_a_sentence_are_found_once_each()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_entities.py:34>) — Test scenario: mentions in a sentence are found once each। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/analysis/test_headline_comparison.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py>) · 149 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

**Class [FixedCosineEmbedder](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:24>)** · inherits `FakeEmbedder`

দায়িত্ব/contract: Every pair has the same cosine - isolates the NLI/rule logic.

- [FixedCosineEmbedder.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:27>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [FixedCosineEmbedder.encode_batch()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:31>) — Test setup/fake/helper: encode batch; test dependencies বা expected input/output প্রস্তুত করে।

**Class [CountingNER](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:36>)** · inherits `FakeNER`

- [CountingNER.extract_mentions()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:39>) — Test setup/fake/helper: extract mentions; test dependencies বা expected input/output প্রস্তুত করে।

- [comparator()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:44>) — Test setup/fake/helper: comparator; test dependencies বা expected input/output প্রস্তুত করে।

- [test_exact_match_is_matched_without_running_any_model()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:48>) — Test scenario: exact match is matched without running any model। এই named behavior assertion দিয়ে যাচাই করে।

- [test_exact_match_normalisation_never_erases_meaning()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:57>) — Test scenario: exact match normalisation never erases meaning। এই named behavior assertion দিয়ে যাচাই করে।

- [test_matched_needs_same_words_or_semantic_equivalence()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:70>) — Test scenario: matched needs same words or semantic equivalence। এই named behavior assertion দিয়ে যাচাই করে।

- [test_no_conflict_found_is_not_an_automatic_match()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:87>) — Test scenario: no conflict found is not an automatic match। এই named behavior assertion দিয়ে যাচাই করে।

- [test_same_speaker_different_main_statement_is_altered()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:94>) — Test scenario: same speaker different main statement is altered। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_material_difference_is_altered_even_when_the_model_entails()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:103>) — Test scenario: a material difference is altered even when the model entails। এই named behavior assertion দিয়ে যাচাই করে।

- [test_entities_are_compared_only_when_ner_is_usable()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:113>) — Test scenario: entities are compared only when ner is usable। এই named behavior assertion দিয়ে যাচাই করে।

**Class [test_entities_are_compared_only_when_ner_is_usable.BrokenNER](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:120>)** · inherits `plain class`

- [test_entities_are_compared_only_when_ner_is_usable.BrokenNER.extract_mentions()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:121>) — Test setup/fake/helper: extract mentions; test dependencies বা expected input/output প্রস্তুত করে।

- [test_missing_inputs_or_models_give_no_verdict_instead_of_a_guess()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:128>) — Test scenario: missing inputs or models give no verdict instead of a guess। এই named behavior assertion দিয়ে যাচাই করে।

**Class [test_missing_inputs_or_models_give_no_verdict_instead_of_a_guess.RaisingNLI](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:135>)** · inherits `plain class`

- [test_missing_inputs_or_models_give_no_verdict_instead_of_a_guess.RaisingNLI.predict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_headline_comparison.py:136>) — Test setup/fake/helper: predict; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/unit/verification/analysis/test_keywords.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_keywords.py>) · 42 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_identical_text_and_extra_evidence_words_give_complete_coverage()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_keywords.py:10>) — Test scenario: identical text and extra evidence words give complete coverage। এই named behavior assertion দিয়ে যাচাই করে।

- [test_inflection_and_split_compounds_still_match()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_keywords.py:15>) — Test scenario: inflection and split compounds still match। এই named behavior assertion দিয়ে যাচাই করে।

- [test_genuine_zero_is_computed_not_unavailable()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_keywords.py:20>) — Test scenario: genuine zero is computed not unavailable। এই named behavior assertion দিয়ে যাচাই করে।

- [test_negation_and_numbers_are_weighted_units()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_keywords.py:25>) — Test scenario: negation and numbers are weighted units। এই named behavior assertion দিয়ে যাচাই করে।

- [test_states_for_missing_input_and_failure()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_keywords.py:33>) — Test scenario: states for missing input and failure। এই named behavior assertion দিয়ে যাচাই করে।

- [test_states_for_missing_input_and_failure.broken()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_keywords.py:37>) — Test setup/fake/helper: broken; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/unit/verification/analysis/test_material_differences.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_material_differences.py>) · 68 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [kinds()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_material_differences.py:17>) — Test setup/fake/helper: kinds; test dependencies বা expected input/output প্রস্তুত করে।

- [test_each_rule_fires_with_quoted_evidence()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_material_differences.py:33>) — Test scenario: each rule fires with quoted evidence। এই named behavior assertion দিয়ে যাচাই করে।

- [test_no_rule_fires_on_lookalikes()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_material_differences.py:46>) — Test scenario: no rule fires on lookalikes। এই named behavior assertion দিয়ে যাচাই করে।

- [test_entity_rules_need_usable_ner()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_material_differences.py:50>) — Test scenario: entity rules need usable ner। এই named behavior assertion দিয়ে যাচাই করে।

- [test_building_blocks()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_material_differences.py:60>) — Test scenario: building blocks। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/analysis/test_passages.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_passages.py>) · 29 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_relevant_sentences_are_selected_with_context_and_overlaps_merged()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_passages.py:13>) — Test scenario: relevant sentences are selected with context and overlaps merged। এই named behavior assertion দিয়ে যাচাই করে।

- [test_long_passages_are_capped()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_passages.py:22>) — Test scenario: long passages are capped। এই named behavior assertion দিয়ে যাচাই করে।

- [test_nothing_relevant_or_nothing_to_read_gives_no_passages()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_passages.py:26>) — Test scenario: nothing relevant or nothing to read gives no passages। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/analysis/test_text.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_text.py>) · 46 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_normalisation_unifies_digits_case_and_tokenizer_artifacts()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_text.py:12>) — Test scenario: normalisation unifies digits case and tokenizer artifacts। এই named behavior assertion দিয়ে যাচাই করে।

- [test_light_stem_strips_inflections_but_keeps_a_minimum_stem()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_text.py:17>) — Test scenario: light stem strips inflections but keeps a minimum stem। এই named behavior assertion দিয়ে যাচাই করে।

- [test_negation_detection_includes_fused_forms_but_not_lookalike_nouns()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_text.py:24>) — Test scenario: negation detection includes fused forms but not lookalike nouns। এই named behavior assertion দিয়ে যাচাই করে।

- [test_content_tokens_drop_stopwords_but_keep_meaning_bearing_words()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_text.py:29>) — Test scenario: content tokens drop stopwords but keep meaning bearing words। এই named behavior assertion দিয়ে যাচাই করে।

- [test_sentences_and_chunks_never_lose_text()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/analysis/test_text.py:33>) — Test scenario: sentences and chunks never lose text। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/pipeline/stages/test_cross_encoder_reranker.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_cross_encoder_reranker.py>) · 47 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [fresh_model()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_cross_encoder_reranker.py:9>) — Test setup/fake/helper: fresh model; test dependencies বা expected input/output প্রস্তুত করে।

**Class [FakeCrossEncoder](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_cross_encoder_reranker.py:14>)** · inherits `plain class`

- [FakeCrossEncoder.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_cross_encoder_reranker.py:17>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [FakeCrossEncoder.predict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_cross_encoder_reranker.py:21>) — Test setup/fake/helper: predict; test dependencies বা expected input/output প্রস্তুত করে।

- [test_scores_pair_the_claim_with_each_article_and_the_model_loads_once()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_cross_encoder_reranker.py:27>) — Test scenario: scores pair the claim with each article and the model loads once। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_unloadable_model_is_reported_as_unavailable_and_not_retried()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_cross_encoder_reranker.py:38>) — Test scenario: an unloadable model is reported as unavailable and not retried। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_unloadable_model_is_reported_as_unavailable_and_not_retried.broken()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_cross_encoder_reranker.py:41>) — Test setup/fake/helper: broken; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/unit/verification/pipeline/stages/test_s01_normalizer.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s01_normalizer.py>) · 72 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [normalise()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s01_normalizer.py:22>) — Test setup/fake/helper: normalise; test dependencies বা expected input/output প্রস্তুত করে।

- [test_claimed_source_claim_is_normalised_and_identified()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s01_normalizer.py:26>) — Test scenario: claimed source claim is normalised and identified। এই named behavior assertion দিয়ে যাচাই করে।

- [test_source_resolution_paths()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s01_normalizer.py:40>) — Test scenario: source resolution paths। এই named behavior assertion দিয়ে যাচাই করে।

- [test_empty_headline_is_rejected()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s01_normalizer.py:44>) — Test scenario: empty headline is rejected। এই named behavior assertion দিয়ে যাচাই করে।

- [test_unusable_source_is_verified_against_the_active_verified_sources()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s01_normalizer.py:54>) — Test scenario: unusable source is verified against the active verified sources। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_callers_reason_for_a_missing_source_is_kept()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s01_normalizer.py:64>) — Test scenario: a callers reason for a missing source is kept। এই named behavior assertion দিয়ে যাচাই করে।

- [test_with_the_fallback_disabled_an_unresolved_source_fails_closed()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s01_normalizer.py:69>) — Test scenario: with the fallback disabled an unresolved source fails closed। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/pipeline/stages/test_s02_cache_lookup.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s02_cache_lookup.py>) · 98 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [cache()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s02_cache_lookup.py:25>) — Test setup/fake/helper: cache; test dependencies বা expected input/output প্রস্তুত করে।

- [pointer()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s02_cache_lookup.py:32>) — Test setup/fake/helper: pointer; test dependencies বা expected input/output প্রস্তুত করে।

- [lookup()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s02_cache_lookup.py:36>) — Test setup/fake/helper: lookup; test dependencies বা expected input/output প্রস্তুত করে।

- [test_a_complete_result_is_reused_from_the_database_and_written_back()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s02_cache_lookup.py:42>) — Test scenario: a complete result is reused from the database and written back। এই named behavior assertion দিয়ে যাচাই করে।

- [test_redis_pointer_hits_and_falls_back_to_the_database()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s02_cache_lookup.py:54>) — Test scenario: redis pointer hits and falls back to the database। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_result_that_is_not_a_settled_answer_is_never_reused()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s02_cache_lookup.py:69>) — Test scenario: a result that is not a settled answer is never reused। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_pointer_to_a_deleted_or_own_submission_is_never_served()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s02_cache_lookup.py:77>) — Test scenario: a pointer to a deleted or own submission is never served। এই named behavior assertion দিয়ে যাচাই করে।

- [test_without_an_identity_nothing_is_looked_up()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s02_cache_lookup.py:87>) — Test scenario: without an identity nothing is looked up। এই named behavior assertion দিয়ে যাচাই করে।

- [test_not_found_pointers_expire_sooner()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s02_cache_lookup.py:95>) — Test scenario: not found pointers expire sooner। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/pipeline/stages/test_s03_query_generator.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s03_query_generator.py>) · 84 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [context()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s03_query_generator.py:19>) — Test setup/fake/helper: context; test dependencies বা expected input/output প্রস্তুত করে।

- [generate()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s03_query_generator.py:25>) — Test setup/fake/helper: generate; test dependencies বা expected input/output প্রস্তুত করে।

- [test_headline_all_keywords_and_short_keyword_queries_restricted_to_the_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s03_query_generator.py:31>) — Test scenario: headline all keywords and short keyword queries restricted to the source। এই named behavior assertion দিয়ে যাচাই করে।

- [test_short_keyword_queries_only_when_available_and_never_duplicated()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s03_query_generator.py:47>) — Test scenario: short keyword queries only when available and never duplicated। এই named behavior assertion দিয়ে যাচাই করে।

- [test_the_body_and_site_operators_in_the_text_never_shape_the_search()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s03_query_generator.py:53>) — Test scenario: the body and site operators in the text never shape the search। এই named behavior assertion দিয়ে যাচাই করে।

- [test_without_a_source_nothing_is_generated()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s03_query_generator.py:62>) — Test scenario: without a source nothing is generated। এই named behavior assertion দিয়ে যাচাই করে।

- [verified_context()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s03_query_generator.py:67>) — Test setup/fake/helper: verified context; test dependencies বা expected input/output প্রস্তুত করে।

- [test_verified_sources_mode_has_bounded_queries_without_a_site_operator()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s03_query_generator.py:76>) — Test scenario: verified sources mode has bounded queries without a site operator। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/pipeline/stages/test_s04_source_search.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s04_source_search.py>) · 151 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [provider()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s04_source_search.py:24>) — Test setup/fake/helper: provider; test dependencies বা expected input/output প্রস্তুত করে।

- [cache()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s04_source_search.py:28>) — Test setup/fake/helper: cache; test dependencies বা expected input/output প্রস্তুত করে।

- [ctx()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s04_source_search.py:33>) — Test setup/fake/helper: ctx; test dependencies বা expected input/output প্রস্তুত করে।

- [search()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s04_source_search.py:42>) — Test setup/fake/helper: search; test dependencies বা expected input/output প্রস্তুত করে।

- [test_all_providers_failing_is_an_inadequate_search_not_an_empty_one()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s04_source_search.py:46>) — Test scenario: all providers failing is an inadequate search not an empty one। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_adequate_empty_search_and_an_unconfigured_outlet_search()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s04_source_search.py:52>) — Test scenario: an adequate empty search and an unconfigured outlet search। এই named behavior assertion দিয়ে যাচাই করে।

- [test_both_providers_get_every_keyword_and_only_date_bound_queries_get_the_date()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s04_source_search.py:63>) — Test scenario: both providers get every keyword and only date bound queries get the date। এই named behavior assertion দিয়ে যাচাই করে।

- [test_candidates_are_on_domain_articles_deduplicated_and_cached()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s04_source_search.py:79>) — Test scenario: candidates are on domain articles deduplicated and cached। এই named behavior assertion দিয়ে যাচাই করে।

- [test_cached_results_are_served_without_calling_the_provider()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s04_source_search.py:93>) — Test scenario: cached results are served without calling the provider। এই named behavior assertion দিয়ে যাচাই করে।

- [test_missing_queries_or_source_dispatch_nothing()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s04_source_search.py:101>) — Test scenario: missing queries or source dispatch nothing। এই named behavior assertion দিয়ে যাচাই করে।

- [verified()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s04_source_search.py:111>) — Test setup/fake/helper: verified; test dependencies বা expected input/output প্রস্তুত করে।

- [test_verified_sources_search_is_google_only_grouped_and_allowlisted()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s04_source_search.py:121>) — Test scenario: verified sources search is google only grouped and allowlisted। এই named behavior assertion দিয়ে যাচাই করে।

- [test_url_canonicalisation_and_helpers()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s04_source_search.py:144>) — Test scenario: url canonicalisation and helpers। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/pipeline/stages/test_s05_evidence_retrieval.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s05_evidence_retrieval.py>) · 147 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [no_delays()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s05_evidence_retrieval.py:23>) — Test setup/fake/helper: no delays; test dependencies বা expected input/output প্রস্তুত করে।

- [no_delays.instant()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s05_evidence_retrieval.py:24>) — Test setup/fake/helper: instant; test dependencies বা expected input/output প্রস্তুত করে।

- [candidates()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s05_evidence_retrieval.py:31>) — Test setup/fake/helper: candidates; test dependencies বা expected input/output প্রস্তুত করে।

- [client()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s05_evidence_retrieval.py:39>) — Test setup/fake/helper: client; test dependencies বা expected input/output প্রস্তুত করে।

- [client.handler()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s05_evidence_retrieval.py:40>) — Test setup/fake/helper: handler; test dependencies বা expected input/output প্রস্তুত করে।

- [context()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s05_evidence_retrieval.py:53>) — Test setup/fake/helper: context; test dependencies বা expected input/output প্রস্তুত করে।

- [test_tiers_failures_and_off_source_redirects_are_kept_apart()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s05_evidence_retrieval.py:59>) — Test scenario: tiers failures and off source redirects are kept apart। এই named behavior assertion দিয়ে যাচাই করে।

- [test_tiers_failures_and_off_source_redirects_are_kept_apart.browser()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s05_evidence_retrieval.py:64>) — Test setup/fake/helper: browser; test dependencies বা expected input/output প্রস্তুত করে।

- [test_candidates_are_cleaned_capped_and_restricted_to_the_allowed_scope()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s05_evidence_retrieval.py:78>) — Test scenario: candidates are cleaned capped and restricted to the allowed scope। এই named behavior assertion দিয়ে যাচাই করে।

- [_response()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s05_evidence_retrieval.py:100>) — Test setup/fake/helper:  response; test dependencies বা expected input/output প্রস্তুত করে।

- [test_browser_waits_out_challenges_and_backs_off_from_walled_hosts()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s05_evidence_retrieval.py:106>) — Test scenario: browser waits out challenges and backs off from walled hosts। এই named behavior assertion দিয়ে যাচাই করে।

- [test_without_playwright_installed_browser_pages_are_failures()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s05_evidence_retrieval.py:125>) — Test scenario: without playwright installed browser pages are failures। এই named behavior assertion দিয়ে যাচাই করে।

- [test_cooldown_expires()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s05_evidence_retrieval.py:131>) — Test scenario: cooldown expires। এই named behavior assertion দিয়ে যাচাই করে।

- [test_interstitials_need_both_a_marker_and_almost_no_text()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s05_evidence_retrieval.py:143>) — Test scenario: interstitials need both a marker and almost no text। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/pipeline/stages/test_s06_article_extractor.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s06_article_extractor.py>) · 134 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [page()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s06_article_extractor.py:27>) — Test setup/fake/helper: page; test dependencies বা expected input/output প্রস্তুত করে।

- [ld()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s06_article_extractor.py:31>) — Test setup/fake/helper: ld; test dependencies বা expected input/output প্রস্তুত করে।

- [extract()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s06_article_extractor.py:35>) — Test setup/fake/helper: extract; test dependencies বা expected input/output প্রস্তুত করে।

- [test_publication_date_and_provenance()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s06_article_extractor.py:51>) — Test scenario: publication date and provenance। এই named behavior assertion দিয়ে যাচাই করে।

- [test_outlet_selectors_give_title_body_and_date()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s06_article_extractor.py:56>) — Test scenario: outlet selectors give title body and date। এই named behavior assertion দিয়ে যাচাই করে।

- [test_fallback_extractors_in_order()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s06_article_extractor.py:65>) — Test scenario: fallback extractors in order। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_generic_aggregator_title_is_replaced_by_the_search_title()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s06_article_extractor.py:88>) — Test scenario: a generic aggregator title is replaced by the search title। এই named behavior assertion দিয়ে যাচাই করে।

- [test_kicker_lines_next_to_the_title_are_headline_variants()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s06_article_extractor.py:96>) — Test scenario: kicker lines next to the title are headline variants। এই named behavior assertion দিয়ে যাচাই করে।

- [test_stage_keeps_readable_pages_and_counts_the_rest_as_failures()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s06_article_extractor.py:108>) — Test scenario: stage keeps readable pages and counts the rest as failures। এই named behavior assertion দিয়ে যাচাই করে।

- [test_stage_keeps_readable_pages_and_counts_the_rest_as_failures.flaky()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s06_article_extractor.py:114>) — Test setup/fake/helper: flaky; test dependencies বা expected input/output প্রস্তুত করে।

- [test_verified_sources_pages_use_their_own_publishers_selectors()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s06_article_extractor.py:125>) — Test scenario: verified sources pages use their own publishers selectors। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/pipeline/stages/test_s07_evidence_ranker.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s07_evidence_ranker.py>) · 62 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

**Class [SaturatedCrossEncoder](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s07_evidence_ranker.py:16>)** · inherits `plain class`

দায়িত্ব/contract: Scores that slightly favour a re-worded video page, as observed on the real Prothom Alo case (+10.87 vs +10.79).

- [SaturatedCrossEncoder.scores()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s07_evidence_ranker.py:20>) — Test setup/fake/helper: scores; test dependencies বা expected input/output প্রস্তুত করে।

- [stage()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s07_evidence_ranker.py:24>) — Test setup/fake/helper: stage; test dependencies বা expected input/output প্রস্তুত করে।

- [test_the_exact_headline_wins_and_the_cross_encoder_only_breaks_ties()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s07_evidence_ranker.py:30>) — Test scenario: the exact headline wins and the cross encoder only breaks ties। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_kicker_line_and_the_claimed_domain_count_toward_relevance()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s07_evidence_ranker.py:39>) — Test scenario: a kicker line and the claimed domain count toward relevance। এই named behavior assertion দিয়ে যাচাই করে।

- [test_verified_sources_give_every_eligible_publisher_the_same_bonus()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s07_evidence_ranker.py:47>) — Test scenario: verified sources give every eligible publisher the same bonus। এই named behavior assertion দিয়ে যাচাই করে।

- [test_weak_or_unmeasurable_evidence_still_yields_the_best_candidate()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s07_evidence_ranker.py:55>) — Test scenario: weak or unmeasurable evidence still yields the best candidate। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/pipeline/stages/test_s08_source_correspondence.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s08_source_correspondence.py>) · 84 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [blocked()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s08_source_correspondence.py:24>) — Test setup/fake/helper: blocked; test dependencies বা expected input/output প্রস্তুত করে।

- [correspond()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s08_source_correspondence.py:31>) — Test setup/fake/helper: correspond; test dependencies বা expected input/output প্রস্তুত করে।

- [test_the_best_corresponding_article_is_selected_not_rank_one()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s08_source_correspondence.py:35>) — Test scenario: the best corresponding article is selected not rank one। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_claim_quoting_the_kicker_selects_that_headline_line()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s08_source_correspondence.py:45>) — Test scenario: a claim quoting the kicker selects that headline line। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_blocked_search_result_only_matters_when_it_matches_better()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s08_source_correspondence.py:59>) — Test scenario: a blocked search result only matters when it matches better। এই named behavior assertion দিয়ে যাচাই করে।

- [test_without_evidence_only_an_adequate_search_means_not_found()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s08_source_correspondence.py:67>) — Test scenario: without evidence only an adequate search means not found। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_failed_similarity_model_is_recorded_and_keywords_still_decide()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s08_source_correspondence.py:71>) — Test scenario: a failed similarity model is recorded and keywords still decide। এই named behavior assertion দিয়ে যাচাই করে।

- [test_verified_sources_mode_never_names_a_claimed_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s08_source_correspondence.py:79>) — Test scenario: verified sources mode never names a claimed source। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/pipeline/stages/test_s09_headline_alteration.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s09_headline_alteration.py>) · 77 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [confirmed()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s09_headline_alteration.py:19>) — Test setup/fake/helper: confirmed; test dependencies বা expected input/output প্রস্তুত করে।

- [compare()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s09_headline_alteration.py:25>) — Test setup/fake/helper: compare; test dependencies বা expected input/output প্রস্তুত করে।

- [test_the_verdict_comes_from_the_title_alone_and_is_fully_explained()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s09_headline_alteration.py:30>) — Test scenario: the verdict comes from the title alone and is fully explained। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_altered_headline_carries_its_quoted_differences()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s09_headline_alteration.py:45>) — Test scenario: an altered headline carries its quoted differences। এই named behavior assertion দিয়ে যাচাই করে।

- [test_no_source_and_an_incomplete_search_are_different_non_verdicts()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s09_headline_alteration.py:51>) — Test scenario: no source and an incomplete search are different non verdicts। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_untitled_article_or_a_crashed_comparison_gives_no_verdict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s09_headline_alteration.py:67>) — Test scenario: an untitled article or a crashed comparison gives no verdict। এই named behavior assertion দিয়ে যাচাই করে।

**Class [test_an_untitled_article_or_a_crashed_comparison_gives_no_verdict.Crashing](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s09_headline_alteration.py:72>)** · inherits `plain class`

- [test_an_untitled_article_or_a_crashed_comparison_gives_no_verdict.Crashing.compare()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s09_headline_alteration.py:73>) — Test setup/fake/helper: compare; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/unit/verification/pipeline/stages/test_s10_body_similarity.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s10_body_similarity.py>) · 47 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [ctx()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s10_body_similarity.py:13>) — Test setup/fake/helper: ctx; test dependencies বা expected input/output প্রস্তুত করে।

- [measure()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s10_body_similarity.py:19>) — Test setup/fake/helper: measure; test dependencies বা expected input/output প্রস্তুত করে।

- [test_all_four_scores_are_measured_without_touching_the_headline_verdict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s10_body_similarity.py:23>) — Test scenario: all four scores are measured without touching the headline verdict। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_failed_metric_is_recorded_and_the_others_kept()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s10_body_similarity.py:31>) — Test scenario: a failed metric is recorded and the others kept। এই named behavior assertion দিয়ে যাচাই করে।

- [test_nothing_is_scored_without_both_bodies()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s10_body_similarity.py:45>) — Test scenario: nothing is scored without both bodies। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/pipeline/stages/test_s11_date_verification.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s11_date_verification.py>) · 31 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_date_status()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s11_date_verification.py:22>) — Test scenario: date status। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/pipeline/stages/test_s12_result_assembly.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s12_result_assembly.py>) · 119 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_confirmed_source_reasoning_explains_each_dimension()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s12_result_assembly.py:38>) — Test scenario: confirmed source reasoning explains each dimension। এই named behavior assertion দিয়ে যাচাই করে।

- [test_not_found_is_not_a_false_verdict_and_its_strength_is_search_completeness()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s12_result_assembly.py:53>) — Test scenario: not found is not a false verdict and its strength is search completeness। এই named behavior assertion দিয়ে যাচাই করে।

- [test_incomplete_checks_say_why_and_carry_no_findings()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s12_result_assembly.py:66>) — Test scenario: incomplete checks say why and carry no findings। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_run_whose_source_check_never_finished_is_incomplete()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s12_result_assembly.py:77>) — Test scenario: a run whose source check never finished is incomplete। এই named behavior assertion দিয়ে যাচাই করে।

- [verified_context()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s12_result_assembly.py:86>) — Test setup/fake/helper: verified context; test dependencies বা expected input/output প্রস্তুত করে।

- [test_verified_sources_results_never_imply_a_claimed_outlet()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s12_result_assembly.py:96>) — Test scenario: verified sources results never imply a claimed outlet। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_assembly_failure_is_a_classification_error()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s12_result_assembly.py:115>) — Test scenario: an assembly failure is a classification error। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/pipeline/stages/test_s13_result_persistence.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s13_result_persistence.py>) · 130 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [cache()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s13_result_persistence.py:37>) — Test setup/fake/helper: cache; test dependencies বা expected input/output প্রস্তুত করে।

- [persist()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s13_result_persistence.py:41>) — Test setup/fake/helper: persist; test dependencies বা expected input/output প্রস্তুত করে।

- [count()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s13_result_persistence.py:52>) — Test setup/fake/helper: count; test dependencies বা expected input/output প্রস্তুত করে।

- [test_a_new_claim_is_stored_completely_and_enters_expert_review()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s13_result_persistence.py:56>) — Test scenario: a new claim is stored completely and enters expert review। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_retry_is_idempotent_and_never_notifies_twice()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s13_result_persistence.py:80>) — Test scenario: a retry is idempotent and never notifies twice। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_reviewed_submission_is_never_overwritten()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s13_result_persistence.py:93>) — Test scenario: a reviewed submission is never overwritten। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_incomplete_result_is_stored_for_review_but_never_cached()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s13_result_persistence.py:103>) — Test scenario: an incomplete result is stored for review but never cached। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_article_that_failed_extraction_before_is_completed_on_a_retry()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s13_result_persistence.py:110>) — Test scenario: an article that failed extraction before is completed on a retry। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_storage_failure_is_a_persistence_error()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/stages/test_s13_result_persistence.py:126>) — Test scenario: a storage failure is a persistence error। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/pipeline/test_context.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_context.py>) · 40 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_scope_follows_the_body_and_an_explicit_headline_only_drops_it()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_context.py:7>) — Test scenario: scope follows the body and an explicit headline only drops it। এই named behavior assertion দিয়ে যাচাই করে।

- [test_retrieval_failure_means_every_fetch_or_every_extraction_failed()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_context.py:18>) — Test scenario: retrieval failure means every fetch or every extraction failed। এই named behavior assertion দিয়ে যাচাই করে।

- [test_publisher_and_confirmation_depend_on_the_mode()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_context.py:29>) — Test scenario: publisher and confirmation depend on the mode। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/pipeline/test_factory.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_factory.py>) · 20 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_stages_run_in_the_documented_order_with_the_given_services()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_factory.py:8>) — Test scenario: stages run in the documented order with the given services। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/pipeline/test_orchestrator.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_orchestrator.py>) · 78 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

**Class [Stage](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_orchestrator.py:14>)** · inherits `plain class`

- [Stage.__init__()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_orchestrator.py:15>) — Test setup/fake/helper:   init  ; test dependencies বা expected input/output প্রস্তুত করে।

- [Stage.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_orchestrator.py:18>) — Test setup/fake/helper: execute; test dependencies বা expected input/output প্রস্তুত করে।

- [run()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_orchestrator.py:26>) — Test setup/fake/helper: run; test dependencies বা expected input/output প্রস্তুত করে।

- [test_every_stage_runs_in_order_and_is_timed()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_orchestrator.py:32>) — Test scenario: every stage runs in order and is timed। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_reuse_hit_skips_everything_after_the_lookup()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_orchestrator.py:40>) — Test scenario: a reuse hit skips everything after the lookup। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_non_critical_failure_is_recorded_and_the_run_continues()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_orchestrator.py:49>) — Test scenario: a non critical failure is recorded and the run continues। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_critical_failure_marks_the_submission_failed_and_stops()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_orchestrator.py:58>) — Test scenario: a critical failure marks the submission failed and stops। এই named behavior assertion দিয়ে যাচাই করে।

- [test_status_bookkeeping_failures_never_mask_the_run()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_orchestrator.py:69>) — Test scenario: status bookkeeping failures never mask the run। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/pipeline/test_source_registry.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_source_registry.py>) · 21 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_every_record_is_consistent_and_usable()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/pipeline/test_source_registry.py:13>) — Test scenario: every record is consistent and usable। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/test_headline_status.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_headline_status.py>) · 41 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_derived_status()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_headline_status.py:30>) — Test scenario: derived status। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_stored_result_uses_its_saved_detail_and_legacy_rows_have_none()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_headline_status.py:34>) — Test scenario: a stored result uses its saved detail and legacy rows have none। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/test_job_repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_job_repository.py>) · 77 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [enqueue()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_job_repository.py:16>) — Test setup/fake/helper: enqueue; test dependencies বা expected input/output প্রস্তুত করে।

- [test_enqueue_is_idempotent_per_submission()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_job_repository.py:31>) — Test scenario: enqueue is idempotent per submission। এই named behavior assertion দিয়ে যাচাই করে।

- [test_claims_follow_lanes_and_reclaim_only_stale_running_jobs()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_job_repository.py:38>) — Test scenario: claims follow lanes and reclaim only stale running jobs। এই named behavior assertion দিয়ে যাচাই করে।

- [test_retries_are_bounded_and_permanent_errors_fail_at_once()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_job_repository.py:53>) — Test scenario: retries are bounded and permanent errors fail at once। এই named behavior assertion দিয়ে যাচাই করে।

- [test_done_and_heartbeat()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_job_repository.py:69>) — Test scenario: done and heartbeat। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/test_jobs.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_jobs.py>) · 177 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [deps()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_jobs.py:25>) — Test setup/fake/helper: deps; test dependencies বা expected input/output প্রস্তুত করে।

- [pending()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_jobs.py:29>) — Test setup/fake/helper: pending; test dependencies বা expected input/output প্রস্তুত করে।

- [job_of()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_jobs.py:45>) — Test setup/fake/helper: job of; test dependencies বা expected input/output প্রস্তুত করে।

- [wait_for()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_jobs.py:50>) — Test setup/fake/helper: wait for; test dependencies বা expected input/output প্রস্তুত করে।

- [test_job_bodies_are_idempotent_and_dispatched_by_kind()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_jobs.py:61>) — Test scenario: job bodies are idempotent and dispatched by kind। এই named behavior assertion দিয়ে যাচাই করে।

- [test_multimodal_jobs_need_the_model_and_storage()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_jobs.py:84>) — Test scenario: multimodal jobs need the model and storage। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_unresolvable_source_is_a_permanent_failure_and_rolls_back()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_jobs.py:98>) — Test scenario: an unresolvable source is a permanent failure and rolls back। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_restarted_worker_recovers_queued_and_crashed_jobs_only()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_jobs.py:108>) — Test scenario: a restarted worker recovers queued and crashed jobs only। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_restarted_worker_recovers_queued_and_crashed_jobs_only.runner()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_jobs.py:114>) — Test setup/fake/helper: runner; test dependencies বা expected input/output প্রস্তুত করে।

- [test_failures_retry_boundedly_then_notify_the_owner_once()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_jobs.py:127>) — Test scenario: failures retry boundedly then notify the owner once। এই named behavior assertion দিয়ে যাচাই করে।

- [test_failures_retry_boundedly_then_notify_the_owner_once.failing()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_jobs.py:134>) — Test setup/fake/helper: failing; test dependencies বা expected input/output প্রস্তুত করে।

- [test_photo_cards_waiting_on_gemini_never_block_text_jobs()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_jobs.py:152>) — Test scenario: photo cards waiting on gemini never block text jobs। এই named behavior assertion দিয়ে যাচাই করে।

- [test_photo_cards_waiting_on_gemini_never_block_text_jobs.runner()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_jobs.py:158>) — Test setup/fake/helper: runner; test dependencies বা expected input/output প্রস্তুত করে।

- [test_dependencies_come_from_the_app_state()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_jobs.py:173>) — Test scenario: dependencies come from the app state। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/test_presenter.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_presenter.py>) · 128 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [present()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_presenter.py:28>) — Test setup/fake/helper: present; test dependencies বা expected input/output প্রস্তুত করে।

- [test_a_preliminary_result_never_carries_an_overall_verdict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_presenter.py:41>) — Test scenario: a preliminary result never carries an overall verdict। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_final_decision_is_shown_beside_the_unchanged_ai_findings()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_presenter.py:49>) — Test scenario: a final decision is shown beside the unchanged ai findings। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_reused_copy_follows_its_original_review_live()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_presenter.py:65>) — Test scenario: a reused copy follows its original review live। এই named behavior assertion দিয়ে যাচাই করে।

- [test_legacy_rows_never_expose_an_old_content_verdict_as_a_headline_verdict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_presenter.py:80>) — Test scenario: legacy rows never expose an old content verdict as a headline verdict। এই named behavior assertion দিয়ে যাচাই করে।

- [test_without_a_stored_result_there_is_no_response()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_presenter.py:93>) — Test scenario: without a stored result there is no response। এই named behavior assertion দিয়ে যাচাই করে।

- [test_the_selected_article_comes_first_with_at_most_three_unique_articles()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_presenter.py:99>) — Test scenario: the selected article comes first with at most three unique articles। এই named behavior assertion দিয়ে যাচাই করে।

- [test_the_selected_article_comes_first_with_at_most_three_unique_articles.art()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_presenter.py:102>) — Test setup/fake/helper: art; test dependencies বা expected input/output প্রস্তুত করে।

### backend/tests/unit/verification/test_reuse.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_reuse.py>) · 62 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_reusability_rules()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_reuse.py:33>) — Test scenario: reusability rules। এই named behavior assertion দিয়ে যাচাই করে।

- [test_the_newest_reusable_original_is_found_and_copied_once()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_reuse.py:42>) — Test scenario: the newest reusable original is found and copied once। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/test_source_policy.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_source_policy.py>) · 64 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_resolution_mode_and_reason()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_source_policy.py:26>) — Test scenario: resolution mode and reason। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_registry_lookup_hiccup_keeps_the_claimed_path()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_source_policy.py:32>) — Test scenario: a registry lookup hiccup keeps the claimed path। এই named behavior assertion দিয়ে যাচাই করে।

- [test_verified_scope_lists_active_publishers_with_their_domains()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_source_policy.py:39>) — Test scenario: verified scope lists active publishers with their domains। এই named behavior assertion দিয়ে যাচাই করে।

- [test_the_identity_changes_with_the_registry_and_never_collides_with_a_claimed_source()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_source_policy.py:49>) — Test scenario: the identity changes with the registry and never collides with a claimed source। এই named behavior assertion দিয়ে যাচাই করে।

- [test_source_config_carries_selectors_and_allowed_channels()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_source_policy.py:59>) — Test scenario: source config carries selectors and allowed channels। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/test_verdict_compat.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verdict_compat.py>) · 17 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_ai_said_column_never_states_an_overall_verdict()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verdict_compat.py:16>) — Test scenario: ai said column never states an overall verdict। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/test_verification_repository.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_repository.py>) · 23 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

- [test_upsert_keeps_one_row_and_timings_describe_this_execution()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_repository.py:9>) — Test scenario: upsert keeps one row and timings describe this execution। এই named behavior assertion দিয়ে যাচাই করে।

### backend/tests/unit/verification/test_verification_service.py

[Source খুলুন](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_service.py>) · 183 lines

এই module-এর test functions সংশ্লিষ্ট backend behavior-এর expected success/failure/regression cases assert করে; test list নিচে। Tests এই walkthrough-এ execute করা হয়নি।

**Class [Analysis](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_service.py:35>)** · inherits `plain class`

দায়িত্ব/contract: S03-S12 stand-in: the claimed outlet carries the exact report.

- [Analysis.execute()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_service.py:40>) — Test setup/fake/helper: execute; test dependencies বা expected input/output প্রস্তুত করে।

- [pointer_cache()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_service.py:49>) — Test setup/fake/helper: pointer cache; test dependencies বা expected input/output প্রস্তুত করে।

- [service()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_service.py:56>) — Test setup/fake/helper: service; test dependencies বা expected input/output প্রস্তুত করে।

- [req()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_service.py:69>) — Test setup/fake/helper: req; test dependencies বা expected input/output প্রস্তুত করে।

- [jobs()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_service.py:73>) — Test setup/fake/helper: jobs; test dependencies বা expected input/output প্রস্তুত করে।

- [session()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_service.py:78>) — Test setup/fake/helper: session; test dependencies বা expected input/output প্রস্তুত করে।

- [test_a_claim_is_verified_once_and_each_requester_gets_their_own_copy()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_service.py:86>) — Test scenario: a claim is verified once and each requester gets their own copy। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_queued_submission_is_verified_from_its_stored_row()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_service.py:105>) — Test scenario: a queued submission is verified from its stored row। এই named behavior assertion দিয়ে যাচাই করে।

- [test_registration_commits_the_submission_and_its_job_with_the_pipeline_identity()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_service.py:120>) — Test scenario: registration commits the submission and its job with the pipeline identity। এই named behavior assertion দিয়ে যাচাই করে।

- [test_identical_claims_collapse_only_when_everything_matches()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_service.py:131>) — Test scenario: identical claims collapse only when everything matches। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_checked_claim_is_copied_for_a_new_requester_and_never_queued()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_service.py:141>) — Test scenario: a checked claim is copied for a new requester and never queued। এই named behavior assertion দিয়ে যাচাই করে।

- [test_an_unsettled_or_deleted_result_is_verified_afresh()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_service.py:156>) — Test scenario: an unsettled or deleted result is verified afresh। এই named behavior assertion দিয়ে যাচাই করে।

- [test_a_missing_source_is_queued_for_verified_sources_and_rejected_when_that_is_off()](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/tests/unit/verification/test_verification_service.py:170>) — Test scenario: a missing source is queued for verified sources and rejected when that is off। এই named behavior assertion দিয়ে যাচাই করে।

## Non-Python support ও model artifacts

| File | কাজ |
|---|---|
| [backend/README.md](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/README.md>) | Setup ও architecture documentation; কিছু বর্ণনা historical, runtime code প্রাধান্য পাবে। |
| [backend/pyproject.toml](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/pyproject.toml>) | Package dependencies, Python requirement, lint/type/test/coverage configuration। |
| [backend/requirements.txt](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/requirements.txt>) | Installable dependency list। |
| [backend/alembic.ini](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/alembic.ini>) | Migration runner configuration; scripts live under app/db/migrations। |
| [backend/docker-compose.yml](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/docker-compose.yml>) | Local Redis ও MinIO services; PostgreSQL এই compose-এ নেই। |
| [backend/.env.example](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/.env.example>) | Environment setting names ও example values; live credentials নয়। |
| [backend/app/db/migrations/script.py.mako](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/db/migrations/script.py.mako>) | নতুন migration তৈরির Alembic template। |
| [backend/app/features/multimodal/multimodal_model/config.json](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/multimodal_model/config.json>) | Bundled model configuration artifact; runtime settings/loader-এর সঙ্গে মিলিয়ে বুঝবে। |
| [backend/app/features/multimodal/multimodal_model/tokenizer/tokenizer.json](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/multimodal_model/tokenizer/tokenizer.json>) | Serialized tokenizer vocabulary/rules। |
| [backend/app/features/multimodal/multimodal_model/tokenizer/tokenizer_config.json](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/multimodal_model/tokenizer/tokenizer_config.json>) | Tokenizer configuration metadata। |
| [backend/app/features/multimodal/multimodal_model/tokenizer/special_tokens_map.json](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/multimodal_model/tokenizer/special_tokens_map.json>) | Special token mapping। |
| [backend/app/features/multimodal/multimodal_model/tokenizer/vocab.txt](<E:/8th Sem/SPL3/Main/BanglaFactGuard/backend/app/features/multimodal/multimodal_model/tokenizer/vocab.txt>) | Tokenizer vocabulary; executable business function নয়। |

`backend/.env` runtime secrets/configuration ধারণ করে; content এই guide-এর জন্য পড়া হয়নি। `.venv`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `__pycache__`, `.coverage`, `coverage.xml` dependencies/generated files, project business logic নয়। Trained `.pt` model weights loader-এর configured directory-তে expected; source declarations থেকে installed weights-এর উপস্থিতি বা training accuracy দাবি করা হয়নি।

## Coverage of this index

- Python files indexed: **297**।
- App Python files (migrations/package markers-সহ): **193**।
- Total class/function declarations (control-flow-এর nested helpers-সহ): **1723**।
- Test function names scenario index হিসেবে দেওয়া হয়েছে; passing test report হিসেবে নয়।
- Migration/scripts শুধু ব্যাখ্যা করা হয়েছে; execute করে database পরিবর্তন করা হয়নি।
