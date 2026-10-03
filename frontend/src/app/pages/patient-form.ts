import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Api } from '../core/api';
import { Patient, Sex } from '../core/models';
import { errMsg, fmtPhone } from '../core/util';

@Component({
  selector: 'app-patient-form',
  imports: [RouterLink],
  template: `
    <h1>{{ id ? 'Edit patient' : 'Register patient' }}</h1>
    <section class="card">
      <label>Full name (English or हिन्दी)
        <input type="text" autocomplete="off" [value]="name()" (input)="name.set($any($event.target).value)">
      </label>
      <label>Date of birth
        <input type="date" [value]="dob()" (input)="dob.set($any($event.target).value)">
      </label>
      @if (id && dobChanged()) {
        <p class="banner">Changing the date of birth marks this person's earlier screenings for a re-check, because questions depend on age.</p>
      }
      <label>Sex
        <select [value]="sex()" (change)="sex.set($any($event.target).value)">
          <option value="male">Male</option>
          <option value="female">Female</option>
          <option value="other">Other</option>
        </select>
      </label>
      <label>Mobile number
        <input type="tel" inputmode="tel" placeholder="+91 98765 43210, 098765 43210 or 9876543210"
               [value]="phone()" (input)="phone.set($any($event.target).value)">
      </label>
      @if (error()) { <p class="error" role="alert">{{ error() }}</p> }
    </section>

    @if (dupes(); as d) {
      <section class="banner bad" role="alert">
        <strong>This person may already be registered.</strong>
        @for (c of d.candidates; track c.id) {
          <p style="margin: .5rem 0 0"><a [routerLink]="['/patients', c.id]">{{ c.name }}</a>
            <span class="muted"> · {{ c.age }} yrs · {{ fmt(c.phone) }}</span></p>
        }
        @if (d.hidden_matches) {
          <p style="margin: .5rem 0 0">{{ d.hidden_matches }} similar record(s) belong to another health worker and cannot be shown here.</p>
        }
        <p style="margin: .6rem 0 0">Same phone numbers are common in families. If this is a different person, you can still save.</p>
        <div class="actions">
          <button class="primary" type="button" (click)="save(true)" [disabled]="busy()">Save as a new person</button>
        </div>
      </section>
    }

    <div class="actions">
      <button class="primary" type="button" (click)="save(false)" [disabled]="busy()">{{ busy() ? 'Saving…' : 'Save' }}</button>
      <a class="btn secondary" [routerLink]="id ? ['/patients', id] : ['/patients']">Cancel</a>
    </div>
  `,
})
export class PatientForm {
  private api = inject(Api);
  private router = inject(Router);
  id = Number(inject(ActivatedRoute).snapshot.paramMap.get('id')) || 0;
  fmt = fmtPhone;
  name = signal('');
  dob = signal('');
  sex = signal<Sex>('male');
  phone = signal('');
  error = signal('');
  busy = signal(false);
  dupes = signal<{ candidates: Patient[]; hidden_matches: number } | null>(null);
  private original: Patient | null = null;

  constructor() {
    if (this.id) {
      this.api.patient(this.id).subscribe({
        next: p => { this.original = p; this.name.set(p.name); this.dob.set(p.dob); this.sex.set(p.sex); this.phone.set(p.phone); },
        error: e => this.error.set(errMsg(e)),
      });
    }
  }

  dobChanged() { return !!this.original && this.dob() !== this.original.dob; }

  save(force: boolean) {
    this.error.set('');
    if (!this.name().trim() || !this.dob() || !this.phone().trim()) { this.error.set('Name, date of birth and mobile number are required.'); return; }
    const body = { name: this.name(), dob: this.dob(), sex: this.sex(), phone: this.phone(), force_create: force };
    this.busy.set(true);
    const call = this.id ? this.api.updatePatient(this.id, body) : this.api.createPatient(body);
    call.subscribe({
      next: p => this.router.navigate(['/patients', p.id]),
      error: e => {
        this.busy.set(false);
        const d = e?.error?.detail;
        if (e.status === 409 && d?.code === 'possible_duplicate') { this.dupes.set(d); return; }
        this.dupes.set(null);
        this.error.set(errMsg(e));
      },
    });
  }
}
