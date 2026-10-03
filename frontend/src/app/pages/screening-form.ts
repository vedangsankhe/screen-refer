import { Component, HostListener, computed, effect, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Api } from '../core/api';
import { FormConfig, Patient, Question } from '../core/models';
import { errMsg, newId } from '../core/util';
import { resolveVisible } from '../core/visibility';

interface Draft {
  uuid: string; version: string; answers: Record<string, any>;
  patient: Pick<Patient, 'id' | 'name' | 'age' | 'sex'>;
}

@Component({
  selector: 'app-screening-form',
  imports: [RouterLink],
  template: `
    @if (patient(); as p) {
      <h1>Screening: {{ p.name }}</h1>
      <p class="muted">{{ p.age }} years · {{ p.sex }}. Questions change with age and sex.</p>
    }
    @if (!online()) { <p class="banner" role="status">You are offline. Your answers are saved on this phone and nothing is lost.</p> }
    @if (loadError()) { <p class="error" role="alert">{{ loadError() }}</p> }
    @if (restored()) { <p class="notice">Your earlier answers were restored.</p> }

    @if (config(); as c) {
      <div class="progress" aria-hidden="true"><div [style.width.%]="percent()"></div></div>
      @for (q of visibleQuestions(); track q.id) {
        <fieldset class="q">
          <legend>{{ q.label.en }}<span class="hi"><br>{{ q.label.hi }}</span></legend>
          @if (q.type === 'number') {
            <input type="number" inputmode="numeric" [attr.min]="q.min" [attr.max]="q.max"
                   [value]="answers()[q.id] ?? ''" (input)="setNumber(q, $any($event.target).value)"
                   [attr.aria-label]="q.label.en">
            @if (q.unit) { <span class="muted">{{ q.unit.en }} / {{ q.unit.hi }}</span> }
          } @else {
            <div class="opts">
              @for (o of q.options; track o.value) {
                <button type="button" class="opt" [class.on]="answers()[q.id] === o.value"
                        [attr.aria-pressed]="answers()[q.id] === o.value" (click)="setAnswer(q, o.value)">
                  {{ o.label.en }}<span class="hi">{{ o.label.hi }}</span>
                </button>
              }
            </div>
          }
        </fieldset>
      }

      @if (message()) { <p [class]="messageIsError() ? 'error' : 'notice'" role="alert">{{ message() }}</p> }
      <div class="sticky">
        <button class="primary" type="button" (click)="submit()" [disabled]="busy() || !complete()">
          {{ busy() ? 'Submitting…' : pending() ? 'Try again now' : 'See result' }}
        </button>
        <a class="btn secondary" [routerLink]="['/patients', id]" style="margin-left:.5rem">Back</a>
        <span class="muted" style="margin-left:.5rem">{{ answered() }} of {{ visibleQuestions().length }} answered</span>
      </div>
    }
  `,
})
export class ScreeningForm {
  private api = inject(Api);
  private router = inject(Router);
  id = Number(inject(ActivatedRoute).snapshot.paramMap.get('id'));
  private draftKey = `sr_draft_${this.id}`;
  private uuid = newId();   // one id per screening: if the submit is retried, the server returns the same result

  patient = signal<Draft['patient'] | null>(null);
  config = signal<FormConfig | null>(null);
  answers = signal<Record<string, any>>({});   // includes answers of currently hidden questions (kept in case they come back)
  loadError = signal('');
  message = signal('');
  messageIsError = signal(false);
  busy = signal(false);
  pending = signal(false);    // a submit is waiting for the connection
  restored = signal(false);
  online = signal(navigator.onLine);

  visibleIds = computed(() => {
    const c = this.config(), p = this.patient();
    return c && p ? resolveVisible(c.questions, p.age, p.sex, this.answers()) : [];
  });
  visibleQuestions = computed(() => {
    const ids = new Set(this.visibleIds());
    return (this.config()?.questions ?? []).filter(q => ids.has(q.id));
  });
  answered = computed(() => this.visibleQuestions().filter(q => this.hasAnswer(this.answers()[q.id])).length);
  complete = computed(() => this.visibleQuestions().length > 0 && this.answered() === this.visibleQuestions().length);
  percent = computed(() => (this.visibleQuestions().length ? (100 * this.answered()) / this.visibleQuestions().length : 0));

  constructor() {
    // Auto-save after every change, so a refresh or a dropped connection loses nothing.
    effect(() => {
      const p = this.patient(), c = this.config(), answers = this.answers();
      if (!p || !c) return;
      const draft: Draft = { uuid: this.uuid, version: c.version, answers, patient: p };
      try { localStorage.setItem(this.draftKey, JSON.stringify(draft)); } catch { /* storage full: ignore */ }
    });
    this.load();
  }

  @HostListener('window:online') onOnline() {
    this.online.set(true);
    if (this.pending()) this.submit();   // connection is back: send the waiting screening
  }
  @HostListener('window:offline') onOffline() { this.online.set(false); }

  private load() {
    const draft = this.readDraft();
    // The patient and the form config come from the server; if we are offline we fall back to what was saved.
    this.api.patient(this.id).subscribe({
      next: p => this.patient.set({ id: p.id, name: p.name, age: p.age, sex: p.sex }),
      error: e => { if (draft) this.patient.set(draft.patient); else this.loadError.set(errMsg(e)); },
    });
    this.api.formConfig().subscribe({
      next: c => {
        try { localStorage.setItem('sr_form_config', JSON.stringify(c)); } catch { /* ignore */ }
        this.useConfig(c, draft);
      },
      error: e => {
        const cached = this.readCachedConfig();
        if (cached) this.useConfig(cached, draft); else this.loadError.set(errMsg(e));
      },
    });
  }

  private useConfig(c: FormConfig, draft: Draft | null) {
    if (draft && draft.version === c.version) {
      this.uuid = draft.uuid;
      this.answers.set(draft.answers);
      this.restored.set(Object.keys(draft.answers).length > 0);
    }
    this.config.set(c);
  }

  private readDraft(): Draft | null {
    try { return JSON.parse(localStorage.getItem(this.draftKey) || 'null'); } catch { return null; }
  }
  private readCachedConfig(): FormConfig | null {
    try { return JSON.parse(localStorage.getItem('sr_form_config') || 'null'); } catch { return null; }
  }
  private hasAnswer(v: any) { return v !== undefined && v !== null && v !== ''; }

  setAnswer(q: Question, value: any) {
    const next = { ...this.answers(), [q.id]: value };
    // Would this change hide questions the person has already answered? If so, say so before doing it.
    const p = this.patient()!, qs = this.config()!.questions;
    const after = new Set(resolveVisible(qs, p.age, p.sex, next));
    const lost = this.visibleIds().filter(id => id !== q.id && !after.has(id) && this.hasAnswer(this.answers()[id]));
    if (lost.length && !confirm(`Changing this will hide ${lost.length} follow-up answer(s). They will not count towards the result. Continue?`)) return;
    this.answers.set(next);
    this.message.set('');
  }

  setNumber(q: Question, raw: string) {
    const next = { ...this.answers() };
    if (raw === '') delete next[q.id]; else next[q.id] = Number(raw);
    this.answers.set(next);
  }

  submit() {
    if (this.busy() || !this.complete()) return;
    const visible = new Set(this.visibleIds());
    const answers = Object.fromEntries(Object.entries(this.answers()).filter(([k]) => visible.has(k)));  // hidden answers are never sent
    this.busy.set(true);
    this.message.set('');
    this.api.submitScreening({ patient_id: this.id, client_uuid: this.uuid, answers }).subscribe({
      next: s => {
        localStorage.removeItem(this.draftKey);
        this.router.navigate(['/screenings', s.id]);
      },
      error: e => {
        this.busy.set(false);
        if (e.status === 0 || e.status >= 500) {
          // network problem: keep everything, retry automatically when the connection returns
          this.pending.set(true);
          this.messageIsError.set(false);
          this.message.set('Could not reach the server. Your answers are saved on this phone and will be sent when the connection is back.');
        } else {
          this.pending.set(false);
          this.messageIsError.set(true);
          this.message.set(errMsg(e));
        }
      },
    });
  }
}
