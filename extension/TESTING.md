# Verification record

Verified on 2026-10-04. Runtime: Node 22.17; backend virtual environment: Python 3.13.5.

## Automated results

- `npm run build`: passed; ready-to-load Manifest V3 output exists in `dist/`.
- `npm test`: 19 passed (including page-access and cached photocard date-warning regressions).
- Targeted backend suite: 30 passed across `test_multimodal_background.py`, `test_multimodal_service.py`, `test_multimodal_router.py` and `test_photocard_background.py`.
- Backend test temporary files were directed into the repository's `tmp/` directory because the sandbox could not access the default Windows pytest temporary directory.
- Existing multimodal test fixtures were updated to supply current response fields and a sufficiently long valid body when testing unsupported image MIME types.

## Coverage

Version 1.0.2 removes extracted photocard date warnings from new responses and old locally cached results. Website public/expert pages no longer render an extracted-date field. The backend photocard/date-policy suite passes 20 tests. Extracted dates may remain archival API metadata but are never compared; the actual supplied-date versus source-article verification still applies.

Extension tests cover independent headline/body selection import, Bangla text preservation, draft persistence, source submission, English form modes, expert sign-in/workspace link, no password persistence, result mapping, preliminary versus final stages, crop coordinate scaling, image/body validation, notification deduplication, unread state, OFF/re-enable behavior, account isolation, rejected content-script messages, retry after notification delivery failure and network backoff without false failure verdicts.

The UI tests use a simulated DOM and mocked Chrome APIs. Background tests exercise the real extension worker handlers against fake Chrome storage/network/notification APIs. They do not prove that the extension is installed or that the OS displayed a notification.

Backend tests cover fast 202 acknowledgement, image/submission/job acceptance, commit/rollback and orphan cleanup, reuse of queued input, inference retry, invalid input rejection, existing synchronous endpoint compatibility, plus existing photo-card queue/recovery tests. A new SQLite test exercises actual durable submission/analysis persistence through `execute_job`: acceptance and processing use separate sessions, and running the completed job twice leaves one submission and one analysis. Models/storage are deterministic fakes; SQLite uses test-only JSON in place of PostgreSQL vector arrays.

## Manual checks still required in installed Chrome

Version 1.0.1 adds regression checks for missing tab URL metadata on a Facebook-like tab, denied activeTab access, genuine restricted Chrome pages, synchronous toolbar opening, and selected-text extraction without URL metadata. These simulate Chrome API responses; a live Facebook capture still needs the manual check below.

This session could not connect to local Chrome through the Browser tool. No installed-Chrome visual, capture, Chrome restart, or OS-notification test is claimed. Full live verification against the actual PostgreSQL/MinIO/OCR/model deployment was also not run.

After following README.md:

1. Load `dist` unpacked, click the toolbar icon on an ordinary web page, and confirm side-panel layout at narrow and wide widths.
2. Test headline and body separately: typing, Ctrl+V, Use selected text, right-click import, replace and append.
3. Drag a screenshot rectangle in all directions, cancel with Escape, test browser zoom/Windows display scaling, preview, crop, reset and remove. Confirm only selected content appears in the uploaded image.
4. Test PNG/JPEG/WebP/GIF upload, empty/oversized/invalid files and crop-reset behavior.
5. Submit each claim type as guest; close the panel and confirm result notification, unread badge, summary and correct website details link.
6. Repeat as registered user, expert and admin. Switch accounts and confirm private drafts/activity are not shown to the other account.
7. Close/reopen Chrome after submission; turn OFF before completion, then ON; confirm tracking and missed-result recovery.
8. Test expired login, offline/server interruption and an OCR/model failure; no incomplete check should be displayed as a confident verdict.
9. Complete expert review on the website and confirm a separate final-result notification within the slow follow-up interval.
10. Block/silence OS notifications and confirm Activity/unread fallback. Verify notification clicks open extension Activity and View details opens the website.

Browser control, if desired later, requires the ChatGPT browser connection configured under Settings → Computer use. That connection is separate from the BanglaFactGuard extension and is not needed to use BanglaFactGuard manually.
