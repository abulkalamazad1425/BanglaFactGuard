import { TestBed } from '@angular/core/testing';
import { VerdictBadgeComponent } from './verdict-badge.component';

function render(inputs: Record<string, unknown>): HTMLElement {
  const fixture = TestBed.createComponent(VerdictBadgeComponent);
  for (const [k, v] of Object.entries(inputs)) fixture.componentRef.setInput(k, v);
  fixture.detectChanges();
  return fixture.nativeElement as HTMLElement;
}

describe('VerdictBadgeComponent', () => {
  beforeEach(() => TestBed.configureTestingModule({ imports: [VerdictBadgeComponent] }));

  it('summarises a missing article as "Not found in claimed source", with no question mark', () => {
    const el = render({ sourceStatus: 'NOT_FOUND', headlineStatus: null, dateStatus: 'MATCHED' });
    const badges = el.querySelectorAll('.badge');
    expect(badges.length).toBe(1);
    expect(badges[0].textContent!.trim()).toBe('Not found in claimed source');
    expect(el.textContent).not.toContain('?');
  });

  it('never shows "Found" for a confirmed source in a summary', () => {
    const el = render({ sourceStatus: 'CONFIRMED', headlineStatus: 'EXACT_MATCHED' });
    expect(el.textContent).toContain('Headline: Exact Matched');
    expect(el.textContent).not.toMatch(/found|confirmed/i);
  });

  it('labels the three headline statuses and hides an unclaimed date', () => {
    expect(
      render({ sourceStatus: 'CONFIRMED', headlineStatus: 'MEANING_PRESERVED' }).textContent,
    ).toContain('Meaning Preserved');
    const el = render({
      sourceStatus: 'CONFIRMED',
      headlineStatus: 'ALTERED',
      dateStatus: 'MISMATCHED',
      hideDate: true,
    });
    expect(el.textContent).toContain('Headline: Altered');
    expect(el.textContent).not.toContain('Mismatched');
    expect(
      render({ sourceStatus: 'CONFIRMED', headlineStatus: 'ALTERED', dateStatus: 'MISMATCHED' })
        .textContent,
    ).toContain('Date: Mismatched');
  });

  it('shows the AI decision as Likely Fake / Likely Real, never a final verdict', () => {
    expect(render({ label: 'FAKE' }).textContent).toContain('AI: Likely Fake');
    expect(render({ label: 'NON_FAKE' }).textContent).toContain('AI: Likely Real');
    expect(render({ overallVerdict: 'FAKE' }).textContent!.trim()).toBe('✗ Fake');
  });
});
