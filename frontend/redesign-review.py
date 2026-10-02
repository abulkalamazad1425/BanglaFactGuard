from pathlib import Path
p=Path('frontend/src/app/features/expert/expert-review-detail/expert-review-detail.html'); s=p.read_text(encoding='utf-8-sig')
form=s[s.index('<form '):s.index('</form>')+7]
import re
form=re.sub(r'(\[class.selected\]="([^"]+)")',r'\1 [attr.aria-pressed]="\2"',form)
form=form.replace('Overall, is this claim...','Overall decision').replace('Submit Vote','Submit assessment').replace('Justification','Evidence and reasoning').replace('Explain your reasoning. What evidence supports your verdict?','Explain what the evidence shows, cite the relevant source, and describe any uncertainty.').replace('Is this source confirmed?','Was the report found on the claimed outlet?')
form=form.replace('<div class="verdict-options">','<div class="verdict-options" role="group" aria-label="Choose a finding">')
out='''<div class="verification-shell"><div class="flow-container">
<div class="report-toolbar"><a routerLink="/expert/queue" class="btn btn-ghost">← Review queue</a>@if (claim()) {<a [routerLink]="['/verify',claim()!.submission_id]" class="btn btn-secondary">View public report ↗</a>}</div>
<header class="flow-heading"><div><span class="eyebrow">EXPERT WORKSPACE</span><h1>Review the claim. Follow the evidence.</h1><p>Read the original submission and source material before making your independent assessment. Automated findings are supporting information, not instructions for your decision.</p></div></header>
@if (loading()) {<section class="surface state-card" role="status"><div class="spinner"></div><h2>Loading the review</h2><p>Retrieving the claim and the available comparison evidence.</p></section>}
@else if (loadError()) {<section class="surface state-card" role="alert"><h2>Review temporarily unavailable</h2><p>The claim could not be loaded. Try again or return to the review queue.</p><button type="button" class="btn btn-primary" (click)="loadReview()">Try again</button></section>}
@else if (claim(); as c) {
<div class="review-workspace"><main class="review-evidence">
<section class="surface"><div class="section-heading"><span class="eyebrow">01 / ORIGINAL SUBMISSION</span><h2>{{ isStructuredType() ? 'Read the claim in context' : 'Read the article and inspect its image' }}</h2></div><h3 class="claim-preview">{{ c.headline || 'No headline recorded' }}</h3>
@if (c.image_url) {<img [src]="c.image_url" class="media-image" alt="Image submitted with this claim">}
<dl class="meta-grid">@if (isStructuredType()) {<div><dt>Claimed outlet</dt><dd>{{ c.claimed_source_text || 'Not recorded' }}</dd></div>}<div><dt>Submitted</dt><dd>{{ c.submitted_at | date:'medium' }}</dd></div></dl>
@if (c.body_text) {<details open><summary>Submitted article text</summary><p class="long-text">{{ c.body_text }}</p></details>}
@if (photocardDetails(); as p) {<div class="note">Photocard comparison covers the extracted headline only. Check that the read headline accurately represents the image.</div>@if (p.source_date_conflict) {<div class="note warning"><strong>Source or date conflict</strong><p>The text read from the card differs from the supplied source or date. Verification used the supplied details.</p></div>}<dl class="meta-grid"><div><dt>Supplied date</dt><dd>{{ p.published_date || 'Not provided' }}</dd></div><div><dt>Date read from card</dt><dd>{{ p.detected_date_text || 'Not identified' }}</dd></div><div><dt>Outlet read from card</dt><dd>{{ p.detected_source_text || 'Not identified' }}</dd></div></dl>@if (p.ocr_raw_text) {<details><summary>All text read from the photocard</summary><p class="long-text">{{ p.ocr_raw_text }}</p></details>}}
</section>
@if (aiResult(); as r) {<app-verification-report [r]="r" [reviewer]="true" />}
@if (evidenceError()) {<section class="surface claim-section" role="alert"><h2>Comparison evidence could not be loaded</h2><p class="field-hint">Do not interpret this as a missing source or a false claim. Retry to inspect the recorded evidence before assessing this submission.</p><button type="button" class="btn btn-secondary" (click)="loadReview()">Reload evidence</button></section>}
@if (!isStructuredType()) {<section class="surface claim-section"><span class="eyebrow">02 / PRELIMINARY ASSESSMENT</span><h2 class="assessment-value">{{ predictionLabel(c.ai_overall_verdict || c.ai_label) }}</h2><p class="assessment-explanation">This automated assessment is preliminary. Review the article and image independently; it does not establish publication by a news outlet.</p><div class="note">No source-report comparison is provided by this verification method. Explain the evidence and limitations supporting your overall decision.</div></section>}
</main><aside class="review-decision">
<section class="surface review-guide"><span class="eyebrow">YOUR INDEPENDENT REVIEW</span><h2>Before you decide</h2><ol><li>Read the full claim and available source.</li><li>Distinguish missing evidence from a false statement.</li><li>Explain how the evidence supports your decision.</li></ol><p class="field-hint">{{ c.vote_count }} expert assessment{{ c.vote_count === 1 ? '' : 's' }} recorded. A final decision depends on the configured review rules.</p></section>
@if (isAdmin()) {<section class="surface"><span class="eyebrow">VIEW-ONLY ACCESS</span><h2>Observe this review</h2><p class="field-hint">Administrators can inspect the evidence. Only expert accounts can submit an assessment here.</p></section>}
@else if (submitted() || c.has_voted) {<section class="surface" role="status"><div class="state-mark" aria-hidden="true">✓</div><h2>Assessment recorded</h2><p class="field-hint">Your assessment has been saved. The overall decision will be finalized when the review rules are met.</p><a routerLink="/expert/queue" class="btn btn-primary">Back to review queue</a></section>}
@else {<section class="surface"><div class="section-heading"><span class="eyebrow">03 / YOUR ASSESSMENT</span><h2>Record your findings</h2><p>Choose each applicable finding and explain the evidence behind it.</p></div>'''+form+'''@if (voteError()) {<p class="error-copy" role="alert">{{ voteError() }} Your selections and reasoning are still here.</p>}</section>}
</aside></div>
}
</div></div>'''
p.write_text(out,encoding='utf-8')
