import { Component, EventEmitter, Input, Output } from '@angular/core';

/** Items per page for every paginated list in the app. */
export const PAGE_SIZE = 10;

/**
 * The one pager used by every list page (Fact Explorer's design).
 *
 * Give it `total` when the API reports a total ("Page 2 of 5"); otherwise give
 * it `hasNext` (lists fetched with PAGE_SIZE + 1 rows know whether another
 * page exists) and it shows "Page 2". It hides itself when everything fits on
 * the first page.
 */
@Component({
  selector: 'app-pagination',
  standalone: true,
  template: `
    @if (page > 1 || canNext) {
      <nav class="pagination" [attr.aria-label]="label"
        ><button
          type="button"
          class="btn btn-secondary"
          [disabled]="page <= 1 || disabled"
          (click)="pageChange.emit(page - 1)"
          >← Previous</button
        ><span>Page {{ page }}{{ pageCount !== null ? ' of ' + pageCount : '' }}</span
        ><button
          type="button"
          class="btn btn-secondary"
          [disabled]="!canNext || disabled"
          (click)="pageChange.emit(page + 1)"
          >Next →</button
        ></nav
      >
    }
  `,
  styles: [
    `
      .pagination {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 24px;
        margin-top: 28px;
        span {
          font-size: 13px;
          color: var(--text-secondary);
        }
      }
      @media (max-width: 600px) {
        .pagination {
          gap: 10px;
          justify-content: space-between;
          .btn {
            padding: 10px;
            font-size: 12px;
          }
          span {
            font-size: 11px;
          }
        }
      }
    `,
  ],
})
export class PaginationComponent {
  /** Current page, 1-based. */
  @Input({ required: true }) page = 1;
  /** Total item count, when the API reports one. */
  @Input() total: number | null = null;
  /** Whether another page exists, for lists without a total. */
  @Input() hasNext = false;
  @Input() pageSize = PAGE_SIZE;
  /** Disables both buttons (e.g. while a page is loading). */
  @Input() disabled = false;
  @Input() label = 'Pages';
  @Output() pageChange = new EventEmitter<number>();

  get pageCount(): number | null {
    return this.total === null ? null : Math.max(1, Math.ceil(this.total / this.pageSize));
  }

  get canNext(): boolean {
    const count = this.pageCount;
    return count !== null ? this.page < count : this.hasNext;
  }
}
