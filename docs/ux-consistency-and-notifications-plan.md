# UX, sessions and result delivery

## Scope and wording

Keep all website and extension interface copy in English. Use **Text & source**, **Photo card**, and **Text & image** for the three submission methods. Automatic checks are preliminary; every method requires expert review. Text & image preliminary verdicts are **Likely real** and **Likely fake**. Text & source and Photo card report source, content and date findings separately, without inventing an automatic overall verdict. Expert final verdicts are **Fake**, **Real**, **Altered**, and **Misleading**.

Show the stage and verdict before supporting details. Keep evidence available on detail pages; remove repeated explanations from overview cards. After acceptance say: “Verification may take a few minutes. You can continue browsing. Find results in Fact Explorer or My Submissions.” Guests retain a direct result link and extension Activity; My Submissions requires sign-in. Do not promise a fixed expert review completion time.

## Implementation order

1. Repair website session refresh: retry expired authenticated API requests once, share simultaneous refresh requests, coordinate rotating refresh tokens across tabs, and retain sessions during temporary network failures. Keep public/auth requests out of refresh loops.
2. Treat the user-selected photocard source as authoritative. OCR source/date metadata must never override it or produce comparison warnings. Suppress historical metadata conflict warnings in API and extension cache; retain genuine extraction failures.
3. Store new expert credibility as uncalculated (`null`). Each vote has weight 1 before N completed, finalized reviews. At N or more, calculate accuracy from completed reviews and apply configured tiers to subsequent votes. Snapshot vote weights; do not rewrite existing votes. Update admin and expert displays and migrate existing below-threshold scores.
4. Replace the expert queue's 100-record in-memory cutoff with database search and pagination. Search headlines, body text and claimed source before pagination. Add history search and pagination, links to evidence, and clearer vote/final-result hierarchy.
5. Redesign My Submissions and role-aware account settings with fewer competing details, readable status badges, mobile layouts and clear next actions. Unify home, submission, result and extension copy.
6. Add durable result delivery for all three methods, including synchronous, asynchronous and reused results. Reconcile persisted completed stages into uniquely keyed delivery events. Notify the signed-in submitter in-app at preliminary and final stages; queue final-result email to the account email. Anonymous submissions do not receive email. Retry failed delivery without changing saved verdicts.
7. Keep notifications personal: website notifications and extension alerts cover only the current user’s submissions. No all-facts feed or global result alerts (confirmed by the user). OFF pauses extension polling and alerts.

## Delivery design

Use a database migration for nullable credibility and result-delivery events. A background reconciliation worker discovers ready preliminary/final results for every method, records each `(submission, stage)` once, and writes in-app notifications transactionally. Final emails remain queued until SMTP is configured and delivered; failures retry with backoff. SMTP is at-least-once: a process crash after sending but before recording success can cause a duplicate email. Seed historical stages as already handled during migration to avoid sending old-result email on deployment. Newly finalized historical claims still produce final events.

Reuse the existing SMTP settings; add an absolute website URL for email result links. Do not send test email to real accounts during implementation. Extension notification preferences and admin-only connection controls remain enforced.

## Validation and rollout

- Tests: concurrent refresh and retry boundaries, photocard source/date policy, neutral weighting and activation, queue search before pagination, result delivery deduplication/retry/privacy, and extension verdict/personal-notification behavior.
- Build Angular and extension; inspect changed templates and responsive styles. Run relevant existing backend tests and report any environment limitations.
- Deployment: run Alembic migrations, configure website URL/SMTP, restart backend, rebuild frontend, then reload the unpacked extension. Live SMTP and Chrome/OS notification delivery require a configured running environment.

## Acceptance checks

- No raw NON_FAKE labels or extracted-source/date conflict messages in either client.
- Expired access tokens refresh without logging out valid sessions; rejected refresh credentials require login.
- A new expert has no calculated credibility and vote weight 1 until N completed reviews.
- All three methods show noticeable preliminary/final results and send the appropriate submitter notifications.
- Expert queue searches beyond the newest 100 claims; pagination remains available on an empty page.
- Settings, submissions and review history prioritize actions and outcomes over descriptive text.

## Implemented and validated

- All-facts notifications were explicitly cancelled by the user. Only personal updates remain; the old new-claim broadcast to every expert was removed.
- Website and extension wording, prominent verdicts, the home page, account settings, My Submissions, expert queue and history were updated. Website Text & image now uses background submission too.
- Website refresh is shared across concurrent requests and coordinated across tabs; transient failures retain the session. Extension refresh also retains credentials on temporary server failures.
- Database migration `b2f8a4d6c9e1` adds nullable credibility and personal delivery records, and repairs the previously missing PostgreSQL `ESCALATED` enum value. It was applied successfully to the local configured database on 2026-10-04. Historical stages were seeded without sending old-result emails.
- Validation: 90 targeted backend tests, 52 Angular tests in Chrome Headless, and 24 extension tests passed. Angular production and extension builds passed. Real PostgreSQL reconciliation was validated in a rolled-back transaction; backend readiness and both Fact Explorer stages returned HTTP 200.
- No real email was sent as a test. Actual SMTP delivery and Chrome/OS desktop notifications still depend on local configuration and permissions.
