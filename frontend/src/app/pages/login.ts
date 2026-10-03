import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Api } from '../core/api';
import { Auth } from '../core/auth';
import { errMsg } from '../core/util';

@Component({
  selector: 'app-login',
  template: `
    <section class="card narrow" style="margin: 2rem auto">
      <h1>Log in</h1>
      <label>Email
        <input type="email" autocomplete="username" [value]="email()" (input)="email.set($any($event.target).value)">
      </label>
      <label>Password
        <input type="password" autocomplete="current-password" [value]="password()"
               (input)="password.set($any($event.target).value)" (keyup.enter)="go()">
      </label>
      @if (error()) { <p class="error" role="alert">{{ error() }}</p> }
      <button class="primary" type="button" (click)="go()" [disabled]="busy()">{{ busy() ? 'Logging in…' : 'Log in' }}</button>
    </section>
  `,
})
export class Login {
  private api = inject(Api);
  private auth = inject(Auth);
  private router = inject(Router);
  email = signal('');
  password = signal('');
  error = signal('');
  busy = signal(false);

  go() {
    if (!this.email().trim() || !this.password()) { this.error.set('Enter your email and password.'); return; }
    this.busy.set(true);
    this.error.set('');
    this.api.login(this.email().trim(), this.password()).subscribe({
      next: r => {
        this.auth.setSession(r.token, r.user);
        this.router.navigateByUrl(r.user.role === 'doctor' ? '/review' : '/patients');
      },
      error: e => { this.error.set(errMsg(e)); this.busy.set(false); },
    });
  }
}
