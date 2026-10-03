import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Api } from '../core/api';
import { Patient, ScreeningItem } from '../core/models';
import { LevelPill } from '../shared/shared';
import { errMsg, fmtDate, fmtDateTime, fmtPhone } from '../core/util';

@Component({
  selector: 'app-patient-detail',
  imports: [RouterLink, LevelPill],
  template: `
    @if (error()) { <p class="error" role="alert">{{ error() }}</p> }
    @if (p(); as p) {
      <h1>{{ p.name }}</h1>
      <section class="card">
        <dl class="facts">
          <dt>Age</dt><dd>{{ p.age }} years ({{ date(p.dob) }})</dd>
          <dt>Sex</dt><dd>{{ p.sex }}</dd>
          <dt>Mobile</dt><dd>{{ phone(p.phone) }}</dd>
        </dl>
        <div class="actions">
          <a class="btn primary" [routerLink]="['/patients', p.id, 'screen']">Start screening</a>
          <a class="btn secondary" [routerLink]="['/patients', p.id, 'edit']">Edit</a>
          <button class="danger" type="button" (click)="remove(p)">Delete</button>
        </div>
      </section>

      <h2>Screenings</h2>
      @if (history().length) {
        <ul class="rows">
          @for (s of history(); track s.id) {
            <li><a class="row" [routerLink]="['/screenings', s.id]">
              <span class="main">{{ dt(s.created_at) }}
                @if (s.needs_reevaluation) { <span class="muted"> · needs re-check</span> }</span>
              <app-level [level]="s.final_level" />
            </a></li>
          }
        </ul>
      } @else { <p class="notice">No screenings yet.</p> }
    }
  `,
})
export class PatientDetail {
  private api = inject(Api);
  private router = inject(Router);
  private id = Number(inject(ActivatedRoute).snapshot.paramMap.get('id'));
  p = signal<Patient | null>(null);
  history = signal<ScreeningItem[]>([]);
  error = signal('');
  phone = fmtPhone; date = fmtDate; dt = fmtDateTime;

  constructor() {
    this.api.patient(this.id).subscribe({ next: p => this.p.set(p), error: e => this.error.set(errMsg(e)) });
    this.api.screenings({ patient_id: this.id }).subscribe({ next: r => this.history.set(r.items), error: () => {} });
  }

  remove(p: Patient) {
    if (!confirm(`Delete ${p.name}? Their record will be hidden from the lists.`)) return;
    this.api.deletePatient(p.id).subscribe({
      next: () => this.router.navigateByUrl('/patients'),
      error: e => this.error.set(errMsg(e)),
    });
  }
}
