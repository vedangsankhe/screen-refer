import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_URL } from './config';
import { AiSummary, FormConfig, Level, Page, Patient, ScreeningDetail, ScreeningItem, User } from './models';

function params(obj: Record<string, any>): HttpParams {
  let p = new HttpParams();
  for (const [k, v] of Object.entries(obj)) if (v !== undefined && v !== null && v !== '') p = p.set(k, String(v));
  return p;
}

@Injectable({ providedIn: 'root' })
export class Api {
  private http = inject(HttpClient);
  private u = (path: string) => `${API_URL}${path}`;

  login(email: string, password: string) { return this.http.post<{ token: string; user: User }>(this.u('/auth/login'), { email, password }); }
  formConfig() { return this.http.get<FormConfig>(this.u('/form-config')); }

  patients(q: string, page: number) { return this.http.get<Page<Patient>>(this.u('/patients'), { params: params({ q, page, page_size: 10 }) }); }
  patient(id: number) { return this.http.get<Patient>(this.u(`/patients/${id}`)); }
  createPatient(body: any) { return this.http.post<Patient>(this.u('/patients'), body); }
  updatePatient(id: number, body: any) { return this.http.patch<Patient>(this.u(`/patients/${id}`), body); }
  deletePatient(id: number) { return this.http.delete(this.u(`/patients/${id}`)); }

  submitScreening(body: { patient_id: number; client_uuid: string; answers: Record<string, any> }) {
    return this.http.post<ScreeningDetail>(this.u('/screenings'), body);
  }
  screenings(opts: { patient_id?: number; reviewed?: boolean; risk?: Level; page?: number }) {
    return this.http.get<Page<ScreeningItem>>(this.u('/screenings'), { params: params({ page_size: 20, ...opts }) });
  }
  screening(id: number) { return this.http.get<ScreeningDetail>(this.u(`/screenings/${id}`)); }
  review(id: number, body: { decision: 'accept' | 'override'; final_level?: Level; reason?: string }) {
    return this.http.post<ScreeningDetail>(this.u(`/screenings/${id}/review`), body);
  }
  summary(id: number, refresh = false) { return this.http.post<AiSummary>(this.u(`/screenings/${id}/summary`), null, { params: params({ refresh }) }); }
}
