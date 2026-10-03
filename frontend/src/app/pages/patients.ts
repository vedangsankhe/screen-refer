import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Api } from '../core/api';
import { Auth } from '../core/auth';
import { Page, Patient } from '../core/models';
import { errMsg, fmtPhone } from '../core/util';

@Component({
  selector: 'app-patients',
  imports: [RouterLink],
  template: `
    <h1>Patients</h1>
    <div class="toolbar">
      <input type="search" placeholder="Search name or phone" aria-label="Search patients"
             [value]="q()" (input)="onSearch($any($event.target).value)">
      <a class="btn primary" routerLink="/patients/new">Register</a>
    </div>
    @if (error()) { <p class="error" role="alert">{{ error() }}</p> }
    @if (data(); as d) {
      @if (d.items.length) {
        <ul class="rows">
          @for (p of d.items; track p.id) {
            <li>
              <a class="row" [routerLink]="['/patients', p.id]">
                <span class="main">
                  <span class="name">{{ p.name }}</span><br>
                  <span class="muted">{{ p.age }} yrs · {{ p.sex }} · {{ phone(p.phone) }}
                    @if (auth.isDoctor() && p.created_by_name) { · by {{ p.created_by_name }} }</span>
                </span>
              </a>
            </li>
          }
        </ul>
        <div class="pager">
          <button class="secondary" type="button" (click)="go(d.page - 1)" [disabled]="d.page <= 1">Previous</button>
          <span class="muted">Page {{ d.page }} of {{ d.pages }} · {{ d.total }} patients</span>
          <button class="secondary" type="button" (click)="go(d.page + 1)" [disabled]="d.page >= d.pages">Next</button>
        </div>
      } @else {
        <p class="notice">{{ q() ? 'No patients match this search.' : 'No patients yet. Register the first one.' }}</p>
      }
    } @else if (!error()) {
      <p class="muted">Loading…</p>
    }
  `,
})
export class Patients {
  private api = inject(Api);
  auth = inject(Auth);
  phone = fmtPhone;
  q = signal('');
  data = signal<Page<Patient> | null>(null);
  error = signal('');
  private timer: any;

  constructor() { this.load(1); }

  onSearch(v: string) {
    this.q.set(v);
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.load(1), 300);  // wait until typing pauses
  }

  go(page: number) { this.load(page); }

  private load(page: number) {
    this.error.set('');
    this.api.patients(this.q().trim(), page).subscribe({
      next: d => this.data.set(d),
      error: e => this.error.set(errMsg(e)),
    });
  }
}
