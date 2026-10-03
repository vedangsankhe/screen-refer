import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Auth } from './auth';

// These only improve the experience (no pointless screens). The server is what actually enforces access.
export const authGuard: CanActivateFn = () => {
  const router = inject(Router);
  return inject(Auth).token() ? true : router.createUrlTree(['/login']);
};

export const doctorGuard: CanActivateFn = () => {
  const auth = inject(Auth);
  const router = inject(Router);
  if (!auth.token()) return router.createUrlTree(['/login']);
  return auth.isDoctor() ? true : router.createUrlTree(['/patients']);
};
