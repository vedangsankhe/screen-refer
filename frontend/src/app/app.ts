import { Component, inject } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';
import { Auth } from './core/auth';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink],
  template: `
    <header class="topbar">
      <a class="brand" routerLink="/">Screen &amp; Refer</a>
      @if (auth.user(); as u) {
        <nav>
          <a routerLink="/patients">Patients</a>
          @if (auth.isDoctor()) { <a routerLink="/review">Review queue</a> }
        </nav>
        <span class="who">{{ u.name }}</span>
        <button type="button" (click)="auth.logout()">Log out</button>
      }
    </header>
    <main class="wrap"><router-outlet /></main>
  `,
})
export class App {
  auth = inject(Auth);
}
