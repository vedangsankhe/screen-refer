import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../core/api';
import { Level, Page, ScreeningItem } from '../core/models';
import { LevelPill } from '../shared/shared';
import { errMsg, fmtDateTime } from '../core/util';

type Filter = 'todo' | 'High' | 'Medium' | 'all';

@Component({
  selector: 'app-review-queue',
  imports: [RouterLink, LevelPill],
  template: `
    <h1>Review queue</h1>
    <div class="chips" role="group" aria-label="Filter">
      @for (f of filters; track f.key) {
        <button type="button" class="chip" [class.on]="filter() === f.key" (click)="setFilter(f.key)">{{ f.label }}</button>
      }
    </div>
    @if (error()) { <p class="error" role="alert">{{ error() }}</p> }
    @if (data(); as d) {
      @if (d.items.length) {
        <ul class="rows">
          @for (s of d.items; track s.id) {
            <li><a class="row" [routerLink]="['/screenings', s.id]">
              <span class="main"><span class="name">{{ s.patient_name }}</span><br>
                <span class="muted">{{ dt(s.created_at) }} · score {{ s.score }}
                  @if (s.review_decision) { · reviewed }
                  @if (s.needs_reevaluation) { · needs re-check }</span></span>
              <app-level [level]="s.final_level" />
            </a></li>
          }
        </ul>
        <div class="pager">
          <button class="secondary" type="button" (click)="load(d.page - 1)" [disabled]="d.page <= 1">Previous</button>
          <span class="muted">Page {{ d.page }} of {{ d.pages }} · {{ d.total }}</span>
          <button class="secondary" type="button" (click)="load(d.page + 1)" [disabled]="d.page >= d.pages">Next</button>
        </div>
      } @else { <p class="notice">Nothing here.</p> }
    } @else if (!error()) { <p class="muted">Loading…</p> }
  `,
})
export class ReviewQueue {
  private api = inject(Api);
  dt = fmtDateTime;
  filters: { key: Filter; label: string }[] = [
    { key: 'todo', label: 'Not reviewed' }, { key: 'High', label: 'High risk' },
    { key: 'Medium', label: 'Medium risk' }, { key: 'all', label: 'All' },
  ];
  filter = signal<Filter>('todo');
  data = signal<Page<ScreeningItem> | null>(null);
  error = signal('');

  constructor() { this.load(1); }

  setFilter(f: Filter) { this.filter.set(f); this.load(1); }

  load(page: number) {
    const f = this.filter();
    this.error.set('');
    this.api.screenings({
      page, reviewed: f === 'todo' ? false : undefined, risk: f === 'High' || f === 'Medium' ? (f as Level) : undefined,
    }).subscribe({ next: d => this.data.set(d), error: e => this.error.set(errMsg(e)) });
  }
}
