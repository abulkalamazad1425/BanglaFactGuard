# BanglaFactGuard — Website

This is the Angular 19 website for BanglaFactGuard. Visitors use it to submit Bangla news claims and read results. Experts use it to review claims, and admins use it to run the platform. It talks to the [FastAPI backend](../backend/README.md). The [repository README](../README.md) explains the verification methods and verdicts.

## Tech stack

- **Angular 19.2.** Standalone components, signals, lazy-loaded routes, and the `@angular-devkit/build-angular` application builder.
- **Libraries.** Angular Material and CDK; RxJS 7.8.
- **Styling.** SCSS, with a shared green/light theme in `src/styles.scss` and `src/app/shared/styles/verification-workspace.scss`.
- **Language.** TypeScript 5.7.

## Pages

| Route | Access | Page |
| --- | --- | --- |
| `/` | public | Home: how a claim becomes a final result, the three verification methods, the four final verdicts |
| `/verify` | public | Submission workspace with the three methods. `?method=source` is Text & source, `?method=photocard` is Photo card, `?method=image` is Text & image. `/photo-card` and `/multimodal` redirect here |
| `/verify/:id` | public, or owner while pending | Result report for any submission type. It polls while processing and shows the automated findings, the expert verdict, and (once final) each reviewer's vote and justification |
| `/dashboard` | public | **Fact Explorer**: archive summary and a searchable list of *Final decisions* and *Under review* claims. Filters: keyword, decision, method, claimed outlet, submission date range |
| `/faq`, `/about` | public | How results are produced (Headline Alteration, body scores, photo cards, dates, final decisions) and project information |
| `/auth/login`, `/auth/register`, `/auth/forgot-password` | public | Sign in, create an account, reset the password with an emailed code |
| `/history` | signed in | **My Submissions**: every method, with keyword search, status and type filters, and pagination |
| `/notifications` | signed in | Personal result notifications |
| `/settings` | signed in | Profile and password. Experts also see their reviewer performance here (`/expert/stats` redirects to it) |
| `/expert/queue`, `/expert/queue/:id`, `/expert/history` | expert | Review queue with search and paging, the review page (claim, evidence, automated report, vote form), and the expert's vote history |
| `/admin` | admin | Admin dashboard: escalated claims needing a decision, claims waiting longest in review, recent decisions, submissions, review activity and experts |
| `/admin/review-queue`, `/admin/review-queue/:id` | admin | The expert queue as admins see it. Escalated claims can be decided; others are view-only |
| `/admin/experts`, `/admin/experts/new` | admin | Expert accounts: create, edit, activate or deactivate, reset password |
| `/admin/sources` | admin | Verified news sources: aliases, selectors, internal search URL, active flag |
| `/admin/credibility-tiers` | admin | Credibility weight tiers and the voting configuration (M, N, T, lead margin, vote and time limits) |
| `**` | public | Not found |

`authGuard` and `roleGuard(...)` in `src/app/core/guards/` protect the signed-in and role-specific routes. The backend checks permissions on every request as well.

## How the website works

- **Submitting.** A Text & source claim needs a headline. The claimed outlet is optional: you can search the verified sources or type an outlet, and if none is given the claim is checked against all verified sources. Article text and date are optional too.
  - Photo card takes only an image.
  - Text & image needs article text (at least 10 characters) and an image; the headline is optional.
  - Images can be JPEG/PNG/WebP/GIF, up to 10 MB.
- **Background tracking.** Claims are queued on the server (`…/async` endpoints). `PendingVerificationsService` remembers submissions in progress in `localStorage`, polls them every 4 s for up to 10 minutes, and shows a toast when the result is ready. You can leave the page or close the tab; the server keeps working.
- **Session.**
  - **Storage.** Access and refresh tokens are kept in `localStorage` (`StorageService`). `authInterceptor` adds the bearer token to API calls.
  - **Proactive refresh.** `AuthService` renews the access token 60 s before it expires. It also refreshes when the tab wakes up, regains focus or comes back online.
  - **On a 401.** The interceptor refreshes once and retries the request.
  - **When the session ends.** Only when the server rejects the refresh token; temporary network failures do not log you out.
- **Errors.** `errorInterceptor` shows toasts for 403, 422, 5xx and offline errors.
- **Notifications.** The unread count in the navbar refreshes every 15 s.
- **Labels.** `shared/utils/status-labels.ts` uses the same wording as the backend (`app/shared/status_labels.py`) and the extension. Examples: *Found / Not found in claimed source*, *Exact Matched / Meaning Preserved / Altered*, *Likely Fake / Likely Real*, *Real / Fake / Misleading / Altered*.

## Project structure

```text
src/
|-- index.html, main.ts, styles.scss
|-- environments/
|   |-- environment.ts              development: apiUrl = http://localhost:8000/api/v1
|   `-- environment.production.ts   production:  apiUrl = /api/v1 (replaces the dev file at build time)
`-- app/
    |-- app.component.ts, app.config.ts   router (view transitions, anchor scrolling), HttpClient + interceptors
    |-- routes/app.routes.ts              all routes (lazy loaded)
    |-- core/
    |   |-- constants/api-endpoints.constant.ts   every backend path
    |   |-- guards/                                authGuard, roleGuard
    |   `-- interceptors/                          authInterceptor, errorInterceptor
    |-- layouts/                          main layout (navbar + footer) and auth layout
    |-- models/                           TypeScript types for API payloads
    |-- services/                         API clients: auth, verification, photocard, submissions,
    |                                     dashboard, expert, admin, source, notification,
    |                                     pending-verifications, storage
    |-- shared/
    |   |-- components/                   navbar, footer, pagination, toast, verdict-badge,
    |   |                                 verification-report (the shared result report),
    |   |                                 voting-details (public reviewer votes)
    |   |-- services/toast.service.ts
    |   |-- styles/verification-workspace.scss
    |   `-- utils/                        presentation, result-view, status-labels
    `-- features/                         one folder per page (see the table above)
```

## Development

Requires Node.js 22 and npm. Start the backend first ([backend/README.md](../backend/README.md)).

```powershell
npm ci
npm start            # ng serve on http://localhost:4200, live reload
```

To use a different API during development, change `apiUrl` in `src/environments/environment.ts`. The backend allows all origins by default (`CORS_ORIGINS`).

Format code with Prettier, using `.prettierrc.json` (100-character lines, single quotes, `htmlWhitespaceSensitivity: strict`, Angular HTML parser):

```powershell
npx prettier@3 --write "src/**/*.{ts,html,scss}"
```

## Build and deployment

```powershell
npm run build        # production build
npm run watch        # development build, rebuilds on change
```

The production build goes to `dist/bangla-fact-guard/browser/`. It needs internet access, because Google Fonts are inlined at build time. In production the site calls the API at the relative path `/api/v1`, so the web server must:

1. serve `dist/bangla-fact-guard/browser/` and return `index.html` for unknown paths (Angular routing);
2. proxy `/api/v1` to the FastAPI backend.

Set the backend's `EMAIL_WEBSITE_URL` to the public website address, so links in result emails point to it.

## Tests

The website has no unit test target. `angular.json` defines only `build`, `serve` and `extract-i18n`, and there are no spec files. To check the website, run `npm run build`; it fails on any template or type error. The verification logic is tested in the backend suite.
