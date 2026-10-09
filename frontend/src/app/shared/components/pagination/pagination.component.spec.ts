import { TestBed } from '@angular/core/testing';
import { PAGE_SIZE, PaginationComponent } from './pagination.component';

function render(inputs: Partial<PaginationComponent>) {
  const fixture = TestBed.createComponent(PaginationComponent);
  Object.assign(fixture.componentInstance, inputs);
  fixture.detectChanges();
  const el = fixture.nativeElement as HTMLElement;
  const [prev, next] = Array.from(el.querySelectorAll('button'));
  return { fixture, el, prev, next };
}

describe('PaginationComponent', () => {
  it('shows ten items per page everywhere', () => {
    expect(PAGE_SIZE).toBe(10);
  });

  it('hides itself when everything fits on the first page', () => {
    expect(render({ page: 1, total: 7 }).el.querySelector('nav')).toBeNull();
    expect(render({ page: 1, hasNext: false }).el.querySelector('nav')).toBeNull();
  });

  it('shows "Page X of Y" when the total is known', () => {
    const { el, prev, next } = render({ page: 2, total: 25 });
    expect(el.textContent).toContain('Page 2 of 3');
    expect(prev.disabled).toBeFalse();
    expect(next.disabled).toBeFalse();
    expect(render({ page: 3, total: 25 }).next.disabled).toBeTrue();
  });

  it('shows "Page X" and follows hasNext when there is no total', () => {
    const { el, prev, next } = render({ page: 1, hasNext: true });
    expect(el.textContent).toContain('Page 1');
    expect(el.textContent).not.toContain(' of ');
    expect(prev.disabled).toBeTrue();
    expect(next.disabled).toBeFalse();
  });

  it('emits the requested page', () => {
    const { fixture, prev, next } = render({ page: 2, hasNext: true });
    const pages: number[] = [];
    fixture.componentInstance.pageChange.subscribe((p) => pages.push(p));
    next.click();
    prev.click();
    expect(pages).toEqual([3, 1]);
  });
});
