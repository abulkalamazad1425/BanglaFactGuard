# BanglaFactGuard — Browser Extension

This Chrome side panel (Manifest V3, Preact + Vite) lets you submit Bangla news claims without leaving the page you are reading. You can then track the results. It uses the same [FastAPI backend](../backend/README.md) and the same three methods as the [website](../frontend/README.md): **Text & source**, **Photo card** and **Text & image**. Its look matches the website. The interface is in English.

Manifest version 1.0.3. Requires desktop Chrome 120 or newer.

## Features

- **Three views:** Verify, Activity and Account, in a side panel next to the current tab.
- **Text from the page.**
  - Type or paste into the fields.
  - Select text on the page and press **Use selected text** next to a field.
  - Or right-click the selected text and choose **BanglaFactGuard: use as headline** or **… use as body text**.
  - If the field already has text, you can **Replace** or **Append** it. Importing text never submits anything.
- **Images.**
  - Upload a PNG/JPEG/WebP/GIF up to 10 MB.
  - Or press **Select screenshot area** and drag a rectangle on the page. Pressing Escape, resizing the window, or not finishing within 90 s cancels the selection. Very small drags are ignored.
  - In the preview you can drag to crop further, then **Apply crop**, **Reset crop** (back to the selected area, never the whole page) or remove the image.
- **Drafts are kept** per account. Text is stored in `chrome.storage.local` and images in IndexedDB, so they survive closing the panel.
- **Activity** lists this installation's submissions for the signed-in account (or the guest). It has search (headline, type, result), 10 items per page, short result summaries, unread markers and **View details**, which opens the website report at `/verify/{id}`.
- **Background tracking.** Results are checked in the background. A desktop notification and the toolbar badge (unread count, or `OFF`) appear for the preliminary result, the final expert verdict and failures.
- **ON/OFF switch.** OFF pauses capture, selection, submission, polling and new notifications. Jobs the server has already accepted keep running. Turning it back ON picks up tracking again.
- **Account.**
  - Sign in with an existing website account. Registration is on the website.
  - Experts and admins get an **Open workspace** link to `/expert` or `/admin` on the website.
  - Admins also see **Connection settings**.

## Requirements

- A running backend (`http://localhost:8000/api/v1` by default) with its job worker turned on. The website (`http://localhost:4200`) is only needed for **View details** links.
- The backend's own setup applies: PostgreSQL, Redis, MinIO and the models. Photo cards need Gemini, and Text & image needs the multimodal weights and MinIO. See [backend/README.md](../backend/README.md).
- Node.js 22 to build.

## Build and install

```powershell
cd extension
npm ci
npm run build        # writes the installable extension to extension/dist
```

1. Open `chrome://extensions` and turn on **Developer mode**.
2. Click **Load unpacked** and select the **`extension/dist`** folder. Do not select `extension/` itself, and do not open `dist/index.html` as a file; the Chrome APIs only exist in the loaded extension.
3. Pin **BanglaFactGuard — Browser Extension** from Chrome's Extensions menu.
4. Open a normal news or social-media page and click the pinned icon. The side panel opens in that window.

After editing source files, run `npm run build` again (or keep `npm run dev` running to rebuild on every change). Then click **Reload** on `chrome://extensions` and reopen the panel.

## Using it

### Text & source

Enter the headline (required, 5–2,000 characters).

- **Claimed source** is optional. Leave it empty to check the claim against all verified sources.
- **Article text** is optional (up to 50,000 characters). If given, the result includes body similarity scores.
- **Publication date** is optional.

### Photo card

Add only the image, by uploading it or selecting a screenshot area. The server reads the headline, the outlet and the printed date from the card; the form has no fields for them. The collapsible **Verified news sources** list shows which outlets the system recognises. If the card shows no recognised outlet, the headline is checked against all verified sources.

### Text & image

Article text (at least 10 characters) and an image are required. The headline is optional.

### How screenshots work

Chrome's `captureVisibleTab` captures the visible part of the page. The worker crops it straight away to the rectangle you drew, adjusting for display scaling. Only that area is saved and uploaded; the full scrolling page is never captured.

Chrome settings pages, the Web Store, some PDF viewers and other restricted pages do not allow selection or capture. On those pages, paste the text or upload an image instead.

## Results and notifications

- **How often results are checked.** A Chrome alarm runs every 30 s:
  - Pending submissions are checked every 30 s.
  - Submissions in expert review are checked every 5 minutes, waiting for the final verdict.
  - Finished submissions are checked every 10 minutes, so one deleted on the server disappears from Activity.
  - Failed requests back off up to 5 minutes.
- **While the panel is open and visible**, it asks for a check every 10 s, and **Refresh** checks immediately.
- **Three kinds of notification:** the preliminary result, the final expert verdict, and a failure. Each is shown once. Reading the preliminary result does not stop tracking the final verdict.
- **Clicking a notification** opens the extension's Activity page in a tab.
- **When alerts may not appear.** Desktop alerts need the extension to be ON, notifications turned on in Account, and Chrome and OS notification permission. Closing Chrome, sleep, Do Not Disturb or disabling the extension can delay or block them. Activity and the badge still show the saved outcome, and tracking catches up when Chrome or the extension comes back.
- **When an item is removed from Activity.** Only when the server answers "not found" for that specific submission. A wrong API address or an outage never removes anything.
- **What the results mean.** They use the same labels as the website:
  - *Found / Not found in claimed source* (or *in verified sources*);
  - *Exact Matched / Meaning Preserved / Altered*;
  - date *Matched / Mismatched / Could not be determined*;
  - *Likely Fake / Likely Real* for Text & image.

  A source that was not found is not a fake verdict, an incomplete check is not a negative, and a date mismatch does not make a story false. The final verdict (*Real / Fake / Misleading / Altered*) always comes from expert review.

## Accounts, settings and privacy

- **Guests and accounts.** Guest activity belongs to this Chrome installation. Each account has its own drafts and Activity, and guest submissions do not move to an account when you sign in. Website and extension sign-ins are separate.
- **Tokens.** Tokens are kept in `chrome.storage.local`, which only trusted extension pages can read. This storage is **not encrypted**. Passwords are never stored. An expired access token is refreshed automatically, and a temporary refresh failure keeps you signed in. Sign out on shared computers.
- **Connection settings** (Account tab).
  - **Who can change them.** Only a signed-in admin. Before saving, the worker re-checks with the current server (`/auth/me`) that the user is still an admin. Guests, users and experts cannot change the URLs, even through extension messages. Everyone can use ON/OFF and the notification setting.
  - **Allowed addresses.** URLs must be HTTPS, or plain HTTP on `localhost`/`127.0.0.1`, with no credentials, query string or fragment. Chrome asks for host permission only for the API host you choose.
  - **Changing the API address** clears all local tracking, drafts and credentials, so nothing is sent to the new server. Records on the old server are not affected.
  - **First-time deployment without localhost.** Change `DEFAULTS` in `src/shared.js` (and `host_permissions` in `public/manifest.json` if needed) before building.
- **Permissions:** `sidePanel`, `activeTab`, `scripting`, `contextMenus`, `storage`, `alarms`, `notifications`.
  - Host access is limited to localhost; other HTTPS hosts are optional and requested when needed.
  - Pages are accessed only after you click the toolbar icon or a menu item. There is no content script that runs on every site, no reading of browsing history or the clipboard, and no remote code. The page's CSP is `script-src 'self'`.

## Development and tests

```powershell
npm test             # node --test tests/*.test.mjs
npm run build
npm run dev          # vite build --watch
```

There are 34 tests, using Node's built-in runner with simulated Chrome APIs and `fake-indexeddb`:

- **`tests/shared.test.mjs`** covers result summaries and labels, required fields for each method, capture and display-scaling maths, deletion detection, and Activity search and paging.
- **`tests/background.test.mjs`** covers the service worker:
  - polling, notification de-duplication, ON/OFF and restart recovery;
  - account isolation;
  - photo-card submission;
  - blocking privileged messages from content scripts;
  - page-access handling (Facebook, Chrome internal pages);
  - the admin-only connection settings;
  - token refresh.

These tests do not replace a manual check in a real Chrome install for screenshots and OS notifications. Prettier settings are in `.prettierrc.json`.

| File | Role |
| --- | --- |
| `public/manifest.json` | Manifest V3: permissions, side panel, service worker, icon |
| `index.html`, `src/panel.jsx`, `src/style.css` | Side-panel UI (Verify / Activity / Account, forms, crop preview) |
| `src/background.js` | Service worker: API calls and token refresh, submission, polling, notifications, badge, context menus, selection and capture, settings |
| `src/capture.js` | The temporary on-page rectangle selector |
| `src/shared.js` | Defaults, labels, validation, result summaries, crop maths, Activity search and paging |
| `src/db.js` | IndexedDB store for draft images |
| `vite.config.js` | Builds `panel.js` and `background.js` into `dist/` |

## Troubleshooting

- **Cannot reach server:** start the backend and check the API address. A deployed API needs HTTPS with a valid certificate and an allowed host permission.
- **Processing failed or model unavailable:** check the backend's models, MinIO, Gemini settings and job worker. The extension does not run any models itself.
- **Session expired:** sign in again. A signed-in submission is never sent anonymously instead.
- **Not sure whether a submission went through:** if the connection dropped before the server confirmed it, check Activity and *My Submissions* on the website before trying again. The extension prevents double clicks, but the API has no general idempotency key. If you resubmit an identical Text & source claim from the same account, you get your existing submission back.
- **No selected text, or capture fails ("page access"):** go to the tab you want, click the pinned BanglaFactGuard toolbar icon (this gives temporary access to that site), then try again. Keeping the panel open while switching to another site does not give access to the new site. This includes Facebook, which works like any other site.
- **No desktop alert:** check the ON switch, the notification setting in Account, and Chrome and OS notification permissions. Activity shows the actual outcome.
- **Connection settings are missing:** they are shown only to admins.
- **Activity shows only some submissions:** Activity lists submissions made from this installation. Your full history is under *My Submissions* on the website. Expert and admin work happens on the website.
