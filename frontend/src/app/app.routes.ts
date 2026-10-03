import { Routes } from '@angular/router';
import { authGuard, doctorGuard } from './core/guards';

export const routes: Routes = [
  { path: 'login', loadComponent: () => import('./pages/login').then(m => m.Login) },
  { path: 'patients', canActivate: [authGuard], loadComponent: () => import('./pages/patients').then(m => m.Patients) },
  { path: 'patients/new', canActivate: [authGuard], loadComponent: () => import('./pages/patient-form').then(m => m.PatientForm) },
  { path: 'patients/:id/edit', canActivate: [authGuard], loadComponent: () => import('./pages/patient-form').then(m => m.PatientForm) },
  { path: 'patients/:id/screen', canActivate: [authGuard], loadComponent: () => import('./pages/screening-form').then(m => m.ScreeningForm) },
  { path: 'patients/:id', canActivate: [authGuard], loadComponent: () => import('./pages/patient-detail').then(m => m.PatientDetail) },
  { path: 'screenings/:id', canActivate: [authGuard], loadComponent: () => import('./pages/screening-result').then(m => m.ScreeningResult) },
  { path: 'review', canActivate: [doctorGuard], loadComponent: () => import('./pages/review-queue').then(m => m.ReviewQueue) },
  { path: '', pathMatch: 'full', redirectTo: 'patients' },
  { path: '**', redirectTo: 'patients' },
];
