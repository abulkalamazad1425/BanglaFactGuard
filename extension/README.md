# BanglaFactGuard — Quick Verify

An English-language Chrome side panel built with **Preact + Vite**, styled to match the existing Angular website. The backend remains FastAPI. Read [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the detailed design and scope.

## Features

- Guest, registered-user, expert and admin access. Optional email/password sign-in using the existing API.
- Text & source, Photo card, and Text & image submission.
- **Both headline and body:** type, paste, select page text and press **Use selected text**, or right-click selected text and choose the headline/body action. Import offers replace or append and never submits automatically.
- **Area screenshot:** press **Select screenshot area**, drag the rectangle on the current webpage, or press Escape to cancel. Preview the selected area, drag to crop further, apply/reset crop or remove. Image uploads support the same crop tools.
- Persistent drafts, per-account local Activity, queued status, preliminary and expert-final summaries, notifications and unread badge.
- ON/OFF switch pauses extension capture, submission, polling and new notifications. Server jobs already accepted keep running. Turning on resumes tracking.
- **View details** opens the existing website at `/verify/{submission_id}` in a new tab.

## 1. Start the existing backend and website

Use your existing database, Redis, MinIO, OCR and model configuration. This extension does not replace those services. From a terminal in the repository root:

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe run.py
```

If the project's virtual environment has another name, activate/use that environment instead. The API should run at `http://localhost:8000/api/v1`. Existing installations should restart the backend to load the new multimodal background endpoint. Keep the verification worker enabled. The existing durable `verification_jobs` table is reused; this change adds no new migration.

In a separate terminal:

```powershell
cd frontend
npm install
npm start
```

Default website URL: `http://localhost:4200`. The extension can submit without the website tab being open; the website server is required for detail links. Multimodal model weights and MinIO are required for Text & image; photocard verification also needs the configured OCR/extraction services.

## 2. Build the extension

Node.js 22 LTS is recommended. In another terminal:

```powershell
cd extension
npm ci
npm run build
```

The installable folder is **`extension/dist`**. This folder contains `manifest.json`, the side-panel page, worker, icon and bundled scripts. A build was generated during implementation; rebuild after changing source files.

## 3. Load into local Chrome

1. Open Chrome and enter `chrome://extensions` in the address bar.
2. Turn on **Developer mode** in the top-right corner.
3. Click **Load unpacked**.
4. Select this exact folder on this machine:

   `E:\8th Sem\SPL3\Main\BanglaFactGuard\extension\dist`

5. Pin **BanglaFactGuard — Quick Verify** from Chrome's Extensions menu.
6. Open a regular news or social-media webpage, then click the pinned icon. The side panel opens beside your page.
7. Keep the switch **ON**. Use it as a guest, or open **Account** to sign in.
8. Submit a small claim. Once accepted, you can close the panel. Watch Activity/the toolbar badge and Chrome desktop notifications for completion.

Do **not** select the `extension` source directory or open `dist/index.html` as a normal file. Chrome APIs are available only after loading the manifest as an extension. This is for desktop Chrome 120 or newer.

## 4. Daily use

### Text

Choose **Text & source**. Enter headline and optional body using any of typing, normal Ctrl+C/Ctrl+V, or page selection. Each text field has its own selection button. The right-click menu also has separate headline and body entries. Confirm Replace/Append, choose the claimed publisher and optional date, then submit.

### Photo card or screenshot

Choose **Photo card**. Upload an image or click **Select screenshot area**. Drag on the page to select only the desired region. Very small drags are ignored; Escape, resize or the 90-second selection timeout cancels. The selected area appears in the panel. Drag on the preview and use **Apply crop** if needed. **Reset crop** returns to the selected area (never to the full webpage). Enter the claimed publisher/date and submit.

Chrome's API captures the visible viewport internally; the worker immediately crops it locally. Only the selected region is persisted and uploaded. It does not capture the full scrolling page. Selecting text/regions on Chrome settings, the Web Store, some PDF viewers and other restricted pages is not supported; use paste or image upload instead. Click the extension toolbar icon on the intended tab if Chrome has not granted temporary access to it.

### Text & image

Headline, body and image are required. Body must contain at least 10 non-whitespace characters. An image alone belongs in Photo card. Image uploads accept PNG/JPEG/WebP/GIF up to 10 MB; cropped output must also fit the limit.

## Notifications and result meaning

- Pending claims are checked roughly every 30 seconds in the background; browser scheduling may delay this. An open panel requests checks every 10 seconds, with pending work normally limited to its next scheduled check. **Refresh** explicitly checks sooner.
- AI-complete claims are followed approximately every 5 minutes for expert finalization. Finalized/failed claims stop network polling.
- A preliminary result, final expert verdict and failure are distinct notifications. Reading/dismissing a result does not stop tracking the later expert verdict.
- Desktop alerts require Chrome and OS notification permissions and the extension to be ON. Browser closure, sleep, Do Not Disturb or disabling the extension can delay/suppress desktop alerts. Saved Activity and the unread badge remain the fallback. Reopening Chrome/turning ON catches up.
- Notification clicks open the extension Activity page; **View details** opens the website. Website login is separate when a private pending result requires authentication.
- Source not found is not automatically a fake verdict. Incomplete retrieval is shown as incomplete. Date mismatch does not imply a false story. Multimodal predictions are clearly preliminary; expert verdict is separate.
- Photocard OCR dates are not displayed or compared. Extracted-date warnings are suppressed for both newly processed cards and older saved Activity entries; supplied-date versus source-article checks still appear normally.

## Connection settings and permissions

Account → **Connection settings** is visible only to a signed-in admin. Guests, registered users and experts cannot view this form or change either connection URL through extension messages. Saving revalidates the admin role with the current backend. ON/OFF and notification preferences remain available to everyone. Defaults are the local API and website URLs above. For deployment, an admin can enter the HTTPS API base (including `/api/v1`) and HTTPS website URL. Chrome asks for permission only for the selected API host. Plain HTTP is allowed only for localhost/127.0.0.1. Changing the API clears extension tracking and credentials so they are not sent to a different server; old server records are unaffected. For first-time deployment where localhost is unavailable, configure the default URLs in `src/shared.js` and the API host in `public/manifest.json` before building.

Permissions: sidePanel, activeTab, scripting, contextMenus, storage, alarms, notifications; localhost host access plus optional HTTPS API-host access. Content access occurs only after user action. No browsing history, clipboard-reading or all-site persistent content script is used. Scripts and styles are bundled locally; no remote font dependency.

Tokens are stored locally with trusted-extension-only access; storage is **not encrypted**. Passwords are never persisted. Sign out on shared computers. Different accounts have separate drafts and local activity; guest submissions do not become account-owned after login. Guest records cannot be recovered from local history after uninstall/data clearing. Account history on the website remains available.

## Development and tests

```powershell
cd extension
npm test
npm run build
# Optional rebuild on source changes:
npm run dev
```

After each build, click **Reload** for the extension on `chrome://extensions`, then reopen the side panel. There is no need to reinstall dependencies after ordinary edits.

Backend tests:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests/unit/test_multimodal_background.py tests/unit/test_multimodal_service.py tests/integration/test_multimodal_router.py -q --no-cov
```

See [TESTING.md](TESTING.md) for verified behavior and the remaining installed-Chrome checklist.

## Limitations and troubleshooting

- **Cannot reach server:** start backend, check API base URL and optional host permission. HTTPS deployments must expose the API with a valid certificate and appropriate network access.
- **404 for `/multimodal/predict/async`:** restart the backend with this checkout. The existing synchronous endpoint remains available to the website.
- **Model unavailable / processing failed:** check server model, image storage, OCR and worker configuration. The extension does not run the ML pipeline itself.
- **Expired session:** sign in again. Authenticated submission never silently becomes anonymous.
- **Uncertain submission:** if a network connection fails before an acknowledgement, do not blindly resubmit. Check Activity and website history first. Existing APIs have no cross-request idempotency key; the extension prevents in-flight double clicks but cannot promise deduplication when an acknowledgement is lost.
- **No desktop alert:** check Account notification preference, ON state, Chrome notification permission and OS notification settings. Check Activity for the actual server outcome.
- **No selected text / capture:** use an ordinary HTTPS page, activate the intended tab and click the extension icon. Some frames/PDF viewers restrict selections; paste/upload is the fallback.
- **Facebook screenshot / page access (v1.0.1):** Facebook is a normal supported website. After reloading the extension, close the old panel, activate the Facebook tab and click the pinned BanglaFactGuard toolbar icon to reopen it. Then choose Photo card → Select screenshot area. Merely keeping a panel open while moving to a different site does not grant temporary page access. Missing tab URL metadata now triggers an actual permission check rather than being mislabeled as a restricted page. Capture uses the panel's own Chrome window.
- The extension Activity shows submissions made in this extension installation, not every historical website submission. Expert/admin moderation remains on the website.
- Raw API/result errors may retain backend-provided wording; all extension-authored interface text is English.

## File map

`src/panel.jsx` — Preact UI/forms/crop preview; `src/style.css` — matching visual tokens; `src/background.js` — API/auth/tracking/notifications; `src/capture.js` — temporary page selection; `src/shared.js` — validation/result mapping/crop scaling; `src/db.js` — image drafts; `public/manifest.json` — Chrome permissions/entrypoints; `tests/` — automated tests.
