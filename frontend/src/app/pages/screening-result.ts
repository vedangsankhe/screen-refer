import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Api } from '../core/api';
import { Auth } from '../core/auth';
import { AiSummary, Level, ScreeningDetail } from '../core/models';
import { errMsg, fmtDate, fmtDateTime } from '../core/util';
import { Disclaimer, LevelPill } from '../shared/shared';

const ACTIONS: Record<string, string> = {
  create: 'Registered patient', update: 'Edited patient details', soft_delete: 'Deleted patient', submit: 'Submitted screening',
  review_accept: 'Accepted the risk level', review_override: 'Overrode the risk level',
  flagged_for_reevaluation: 'Flagged for re-screening after a correction',
};

@Component({
  selector: 'app-screening-result',
  imports: [RouterLink, Disclaimer, LevelPill],
  template: `
    @if (error()) { <p class="error" role="alert">{{ error() }}</p> }
    @if (s(); as s) {
      <p class="muted"><a [routerLink]="['/patients', s.patient_id]">← {{ s.patient.name }}</a> · screened {{ dt(s.created_at) }}</p>

      @if (s.reevaluation; as r) {
        <section class="banner bad" role="alert">
          <strong>Details were corrected after this screening.</strong>
          Age was {{ r.old_age }}, now {{ r.new_age }}.
          Re-scored with the corrected details the result would be <app-level [level]="r.recomputed_level" /> (shown below: {{ s.risk_level }}).
          @if (r.unanswered_questions.length) { {{ r.unanswered_questions.length }} question(s) that now apply were never asked. }
          This result is kept as it was recorded. Please screen again.
          <div class="actions"><a class="btn primary" [routerLink]="['/patients', s.patient_id, 'screen']">Screen again</a></div>
        </section>
      }

      <section class="result" [class]="'result lvl-' + s.final_level">
        <div>
          <div class="sub">Risk level{{ s.final_level !== s.risk_level ? ' (doctor decision)' : '' }}</div>
          <div class="level">{{ s.final_level }}</div>
        </div>
        <div class="sub">
          Calculated: {{ s.risk_level }} · score {{ s.score }}
          @if (s.review_decision) { <br>Doctor {{ s.review_decision === 'accept' ? 'accepted' : 'changed' }} this }
        </div>
      </section>
      <app-disclaimer />

      <h2>Why this result</h2>
      @if (s.risk_reasons.length) {
        <ul class="rows">
          @for (r of s.risk_reasons; track r.id) {
            <li style="padding:.6rem 1rem">{{ r.text }}
              <span class="muted">{{ r.red_flag ? '· red flag, always High' : '· +' + r.points }}</span></li>
          }
        </ul>
      } @else { <p class="notice">Nothing concerning was reported.</p> }

      @if (auth.isDoctor()) {
        <h2>AI summary for the doctor</h2>
        <section class="card">
          @switch (summaryState()) {
            @case ('loading') { <p class="muted">Writing summary…</p> }
            @case ('ok') {
              <p><strong>English</strong><br>{{ summary()?.en }}</p>
              <p><strong>हिन्दी</strong><br>{{ summary()?.hi }}</p>
              <p class="muted">Written by AI from the answers above. Check it against the answers.</p>
            }
            @case ('unavailable') {
              <p class="notice" role="status">AI summary unavailable. The screening result is unaffected.</p>
              <button class="secondary" type="button" (click)="loadSummary(true)">Try again</button>
            }
            @default { <button class="secondary" type="button" (click)="loadSummary(false)">Write summary (English + हिन्दी)</button> }
          }
        </section>

        <h2>Doctor review</h2>
        <section class="card">
          @for (r of s.reviews; track $index) {
            <p class="muted">{{ dt(r.created_at) }} · {{ r.doctor }}: {{ r.decision === 'accept' ? 'accepted' : 'overrode ' + r.previous_level + ' → ' + r.final_level }}
              @if (r.reason) { — "{{ r.reason }}" }</p>
          }
          <label class="radio"><input type="radio" name="d" [checked]="decision() === 'accept'" (change)="decision.set('accept')"> Accept {{ s.risk_level }}</label>
          <label class="radio"><input type="radio" name="d" [checked]="decision() === 'override'" (change)="decision.set('override')"> Override</label>
          @if (decision() === 'override') {
            <label>New risk level
              <select [value]="newLevel()" (change)="newLevel.set($any($event.target).value)">
                @for (l of levels; track l) { @if (l !== s.final_level) { <option [value]="l">{{ l }}</option> } }
              </select>
            </label>
            <label>Reason (required)
              <textarea [value]="reason()" (input)="reason.set($any($event.target).value)"></textarea>
            </label>
          }
          @if (reviewError()) { <p class="error" role="alert">{{ reviewError() }}</p> }
          <button class="primary" type="button" (click)="saveReview(s)" [disabled]="reviewBusy()">Save decision</button>
        </section>
      }

      <h2>Answers</h2>
      <ul class="rows">
        @for (a of s.answers; track a.id) {
          <li style="padding:.6rem 1rem">{{ a.question }}<br><strong>{{ a.answer_label }}</strong> <span class="hi">{{ a.answer_label_hi }}</span></li>
        }
      </ul>
      @if (s.discarded_answers.length) {
        <p class="muted">Not counted (follow-up questions that were no longer relevant): {{ s.discarded_answers.length }}</p>
      }

      @if (s.audit) {
        <h2>History of changes</h2>
        <ul class="card log">
          @for (e of s.audit; track e.id) {
            <li><strong>{{ label(e.action) }}</strong> · {{ e.actor }} · {{ dt(e.created_at) }}
              @if (e.old_value) { <br><span class="muted">Before: {{ fmt(e.old_value) }}</span> }
              @if (e.new_value) { <br><span class="muted">After: {{ fmt(e.new_value) }}</span> }
            </li>
          }
        </ul>
      }
      <app-disclaimer />
    }
  `,
})
export class ScreeningResult {
  private api = inject(Api);
  auth = inject(Auth);
  private id = Number(inject(ActivatedRoute).snapshot.paramMap.get('id'));
  levels: Level[] = ['Low', 'Medium', 'High'];
  dt = fmtDateTime; date = fmtDate;

  s = signal<ScreeningDetail | null>(null);
  error = signal('');
  summary = signal<AiSummary | null>(null);
  summaryState = signal<'idle' | 'loading' | 'ok' | 'unavailable'>('idle');
  decision = signal<'accept' | 'override'>('accept');
  newLevel = signal<Level>('High');
  reason = signal('');
  reviewError = signal('');
  reviewBusy = signal(false);

  constructor() {
    this.api.screening(this.id).subscribe({
      next: s => { this.setScreening(s); if (s.ai_summary?.status === 'ok') { this.summary.set(s.ai_summary); this.summaryState.set('ok'); } },
      error: e => this.error.set(errMsg(e)),
    });
  }

  private setScreening(s: ScreeningDetail) {
    this.s.set(s);
    this.newLevel.set(this.levels.find(l => l !== s.final_level) ?? 'High');
  }

  label = (a: string) => ACTIONS[a] ?? a;
  fmt(v: Record<string, any>) {
    return Object.entries(v).map(([k, x]) => `${k.replace(/_/g, ' ')}: ${Array.isArray(x) ? x.join(', ') || 'none' : x ?? 'none'}`).join(' · ');
  }

  loadSummary(refresh: boolean) {
    this.summaryState.set('loading');
    this.api.summary(this.id, refresh).subscribe({
      next: r => { this.summary.set(r); this.summaryState.set(r.status === 'ok' ? 'ok' : 'unavailable'); },
      error: () => this.summaryState.set('unavailable'),   // even a network error just means "no AI box"; the rest still works
    });
  }

  saveReview(s: ScreeningDetail) {
    this.reviewError.set('');
    if (this.decision() === 'override' && !this.reason().trim()) { this.reviewError.set('Please give a reason for the override.'); return; }
    this.reviewBusy.set(true);
    const body = this.decision() === 'accept'
      ? { decision: 'accept' as const }
      : { decision: 'override' as const, final_level: this.newLevel(), reason: this.reason().trim() };
    this.api.review(s.id, body).subscribe({
      next: r => { r.ai_summary = this.summary(); this.setScreening(r); this.reason.set(''); this.decision.set('accept'); this.reviewBusy.set(false); },
      error: e => { this.reviewError.set(errMsg(e)); this.reviewBusy.set(false); },
    });
  }
}
