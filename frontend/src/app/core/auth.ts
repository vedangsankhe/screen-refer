import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { User } from './models';

@Injectable({ providedIn: 'root' })
export class Auth {
  private router = inject(Router);
  token = signal<string | null>(localStorage.getItem('sr_token'));
  user = signal<User | null>(this.readUser());
  isDoctor = computed(() => this.user()?.role === 'doctor');

  private readUser(): User | null {
    try { return JSON.parse(localStorage.getItem('sr_user') || 'null'); } catch { return null; }
  }

  setSession(token: string, user: User) {
    localStorage.setItem('sr_token', token);
    localStorage.setItem('sr_user', JSON.stringify(user));
    this.token.set(token);
    this.user.set(user);
  }

  logout() {
    localStorage.removeItem('sr_token');
    localStorage.removeItem('sr_user');
    this.token.set(null);
    this.user.set(null);
    this.router.navigateByUrl('/login');
  }
}
