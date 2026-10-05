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

  it('renders "Source not found" with no question mark before it', () => {
    const el = render({ sourceStatus: 'NOT_FOUND' });
    const badge = el.querySelector('.badge')!;
    expect(badge.textContent!.trim()).toBe('Source not found');
    expect(badge.querySelector('.badge-icon')).toBeNull();
    expect(el.textContent).not.toContain('?');
  });

  it('legacy not-found label has no question mark either', () => {
    expect(render({ label: 'NOT_FOUND_IN_CLAIMED_SOURCE' }).textContent).not.toContain('?');
  });

  it('labels the content status as the Headline Alteration verdict', () => {
    const el = render({ sourceStatus: 'CONFIRMED', contentStatus: 'ALTERED' });
    expect(el.textContent).toContain('Headline altered');
    expect(el.textContent).not.toMatch(/content/i);
  });

  it('shows no headline badge when there is no headline verdict', () => {
    const el = render({ sourceStatus: 'CONFIRMED', contentStatus: null });
    expect(el.querySelectorAll('.badge').length).toBe(1);
  });
});
