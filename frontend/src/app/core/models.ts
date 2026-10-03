export type Role = 'worker' | 'doctor';
export type Level = 'Low' | 'Medium' | 'High';
export type Sex = 'male' | 'female' | 'other';
export interface Bilingual { en: string; hi: string }

export interface User { id: number; name: string; email: string; role: Role }
export interface Patient {
  id: number; name: string; dob: string; sex: Sex; phone: string; age: number;
  created_by_name?: string | null; created_at: string;
}
export interface Page<T> { items: T[]; total: number; page: number; page_size: number; pages: number }

export interface Option { value: string; label: Bilingual }
export interface Question {
  id: string; type: 'yesno' | 'choice' | 'number'; label: Bilingual; options?: Option[];
  visibleIf?: any; min?: number; max?: number; unit?: Bilingual;
}
export interface FormConfig { version: string; questions: Question[] }

export interface ScreeningItem {
  id: number; patient_id: number; patient_name: string; created_at: string; age_at_screening: number;
  score: number; risk_level: Level; final_level: Level; review_decision: 'accept' | 'override' | null;
  needs_reevaluation: boolean;
}
export interface AnswerView { id: string; question: string; question_hi: string; answer_label: string; answer_label_hi: string }
export interface Reevaluation {
  old_age: number; new_age: number; old_sex: string; new_sex: string; original_level: Level;
  recomputed_level: Level; unanswered_questions: string[]; ignored_answers: string[]; needs_rescreen: boolean;
}
export interface AuditEntry {
  id: number; entity: string; action: string; old_value: any; new_value: any; created_at: string; actor: string;
}
export interface AiSummary { status: 'ok' | 'unavailable'; en?: string; hi?: string; message?: string; cached?: boolean }
export interface ScreeningDetail extends ScreeningItem {
  disclaimer: string;
  patient: { id: number; name: string; sex: Sex; dob: string; phone: string };
  risk_reasons: { id: string; text: string; points: number; red_flag: boolean }[];
  answers: AnswerView[]; discarded_answers: AnswerView[];
  reevaluation: Reevaluation | null;
  reviews: { decision: string; previous_level: Level; final_level: Level; reason: string | null; created_at: string; doctor: string }[];
  ai_summary?: AiSummary | null;
  audit?: AuditEntry[];
}
