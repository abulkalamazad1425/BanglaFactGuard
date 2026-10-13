import { Component, EventEmitter, Input, Output } from '@angular/core';

export const PAGE_SIZE = 10;

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
  @Input({ required: true }) page = 1;
  @Input() total: number | null = null;
  @Input() hasNext = false;
  @Input() pageSize = PAGE_SIZE;
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
