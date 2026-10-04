# BanglaFactGuard Chrome Extension — Implementation Plan

## Product and scope

Build an English-language Manifest V3 Chrome side panel beside the existing Angular frontend and FastAPI backend. Anonymous visitors and signed-in registered users, experts and admins can submit SOURCE_BASED, PHOTO_CARD and MULTIMODAL claims. Expert/admin actions remain on the website. No automatic page scraping or automatic submission.

## Technology and visual design

Use lightweight Preact components with Vite, native Chrome extension APIs and ordinary CSS. Preact keeps the extension small while retaining a component-based structure familiar from Angular. Bundle every script locally; no runtime CDN, inline scripts or remote fonts. Match frontend/src/styles.scss: green #1f7f4e, dark green #186640, paper #e5efed, white surfaces, text #102a20, 12–18px rounded corners. System fonts include Nirmala UI for Bangla input. All labels, validation and notifications are English; submitted Bangla text is preserved.

## User interface

Header: shield mark, product name, ON/OFF switch. Navigation: Verify, Activity, Account. Three verification modes with explanations. Both headline and body independently support typing, normal copy/paste, a Use selected text button, and right-click selection actions. Imported text remains editable; append/replace is explicit. Never infer claimed publisher from the site where the claim was encountered.

Source form: headline (5–2000 chars), optional body (up to 50000 chars), registered source name/domain, optional date. Photocard: image, source, optional date. Multimodal: headline (1–2000), body (10–50000), image. Validate trimmed inputs and image MIME/size before upload. Source suggestions come from the existing source API but manual entry remains possible.

## Selected-area screenshot

User presses Select screenshot area; inject a temporary selection overlay only into the active ordinary web page. Drag a rectangle; Escape cancels. Disable page scrolling during selection and remove listeners/overlay afterwards. Hide the overlay before capture and verify the active tab is unchanged. Chrome captures the visible viewport internally; immediately crop locally to the selected rectangle using actual bitmap-to-viewport scale. Do not upload or persist the full viewport. Return only the selected image to the panel. Preview supports another drag-to-crop, reset crop, replace and remove. Uploaded images support the same crop UI. Restricted pages provide upload fallback. Capture is user initiated, never continuous.

## API integration

Default API: http://localhost:8000/api/v1; website: http://localhost:4200. Settings permit another HTTP localhost or HTTPS deployment with an explicit optional host permission. API requests run in the background worker, not the content script. Do not use wildcard permanent website access.

Existing endpoints: POST /auth/login, /auth/refresh, /auth/logout; GET /auth/me; POST /verify/async; GET /verify/{id}/status; POST /photocard/verify/async; GET /photocard/{id}; GET /multimodal/by-submission/{id}; GET /submissions/{id}; GET /sources. Open website /verify/{id} for details.

Add POST /multimodal/predict/async using the existing durable verification_jobs table/worker. Persist image and submission before acknowledgement, enqueue in the submission transaction, reuse the same submission during inference and retries, and mark AI completion only when analysis is stored. Read queued image through the storage service. Preserve existing synchronous predict API. Check authorization before exposing queued multimodal content. No new queue infrastructure is necessary.

## Authentication and ownership

Login with existing email/password endpoint; obtain actual role from /auth/me. Store tokens only in trusted extension storage (not content scripts), never passwords. Persistent local session with logout and refresh rotation; local storage is not an encrypted vault. Account-bound items are shown and polled only for that account, anonymous items remain separate. Do not attach old anonymous work to a newly signed-in account. Auth failure pauses authenticated polling and asks for login, never retries an authenticated submission anonymously. Endpoint changes clear credentials/drafts/tracking to avoid forwarding credentials or identifiers to another server.

## Background lifecycle and notification

Save each accepted submission under a separate storage key to avoid overwriting concurrent submissions. Worker owns network calls, token refresh, tracking and notifications. A 30-second Chrome alarm checks due pending work; open panel may request a poll every 10 seconds. Persist state and notification markers; check/recreate alarms when worker wakes. Completed AI results continue slow follow-up for expert finalization. Finalized and failed work stops polling. Network failures back off without changing a claim into FAILED. Cached results follow the same notification path. Stable notification IDs and persisted result-stage markers suppress repeated alerts. Notification clicks open the extension Activity page with the selected result; website opens only from View details. Badge reflects unread result count.

Notification stages: preliminary AI result, final expert verdict, failed verification. Show source/content/date independently; NOT_FOUND is not a fake verdict, INCOMPLETE is not a confident negative. Multimodal FAKE/NON_FAKE is preliminary. No source-check confidence-as-truth percentage. Show photocard extraction warnings and extracted headline.

When browser is closed, asleep, extension disabled, or OS notifications blocked, immediate desktop delivery is impossible. Recover on restart/re-enable and retain Activity/badge fallback. Anonymous history lives on this installation only and is lost on uninstall/clear. OFF stops capture, submit, network polling and new notifications; server jobs continue. ON catches up. History remains readable.

## Drafts, failure and retry

Save text drafts by owner and restore after panel closure. Keep selected/uploaded image drafts in IndexedDB (not full page capture). Submission is performed by the worker so closing the panel does not cancel the accepted job. Prevent double-click submission and persist a submission-in-progress marker. Network failure before acknowledgement is an uncertain outcome: do not silently auto-resubmit. Surface a message to check Activity/website before retrying. Cross-request idempotency for existing text/photocard APIs is a future backend migration, not claimed as implemented. Accepted submissions can always resume polling.

## Implementation order

1. Save this plan before implementation; inspect existing styling and contracts.
2. Scaffold Preact/Vite extension, manifest, English UI, CSS and build.
3. Implement auth, API adapter, durable tracking, notifications, OFF state.
4. Implement selected text context menus and active-tab area capture.
5. Build preview/crop, form validation, drafts and result cards.
6. Add durable multimodal acceptance/worker support and focused backend tests.
7. Run build, pure result/crop tests, worker lifecycle tests and backend tests. Test UI with a browser when available; report any untested installed-Chrome behavior explicitly.
8. Document local Chrome Load unpacked setup, permissions, backend prerequisites, deployment and troubleshooting.

## Acceptance checks

- All four roles use the same three forms; guests need no login.
- Headline and body support independent write/paste/highlight workflows.
- Screenshot drag rectangle selects the initial area; preview allows further crop/reset.
- Off toggle blocks capture, upload and polling and persists through restart.
- Closing panel does not lose an acknowledged submission; service worker restart recovers tracking.
- Preliminary/final/failure notifications are separate and do not repeat on each poll.
- Auth refresh works; logout/account switch never exposes another account's private activity.
- Network failure is retryable and never becomes a false verdict.
- Detail links use submission IDs for every type.
- English labels match the website palette; Bangla claim text renders safely as text.
- Multimodal job retries reuse the accepted submission and do not create a duplicate analysis.
- Documentation distinguishes automated verification from manual Chrome/OS checks.
