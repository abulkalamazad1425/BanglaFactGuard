import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { ExpertService } from '../../../services/expert.service';
import { ExpertQueueItem } from '../../../models/expert.model';
import { VerdictBadgeComponent } from '../../../shared/components/verdict-badge/verdict-badge.component';

@Component({
  selector: 'app-expert-queue',
  standalone: true,
  imports: [CommonModule, RouterLink, VerdictBadgeComponent],
  templateUrl: './expert-queue.html',
  styleUrls: ['./expert-queue.scss']
})
export class ExpertQueueComponent implements OnInit {
  private readonly expertSvc = inject(ExpertService);

  readonly loading = signal(true);
  readonly queue = signal<ExpertQueueItem[]>([]);
  readonly offset = signal(0);
  readonly limit = 20;
  readonly page = () => Math.floor(this.offset() / this.limit) + 1;

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.expertSvc.getQueue(this.limit, this.offset())
      .subscribe({ next: q => { this.queue.set(q); this.loading.set(false); }, error: () => this.loading.set(false) });
  }

  prev(): void { this.offset.update(o => Math.max(0, o - this.limit)); this.load(); }
  next(): void { this.offset.update(o => o + this.limit); this.load(); }

  getHost(url: string): string {
    try { return new URL(url).hostname.replace('www.', ''); } catch { return ''; }
  }
}
