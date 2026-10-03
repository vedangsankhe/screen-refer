/** Turns any server/network error into a message a health worker can act on. */
export function errMsg(e: any): string {
  if (e?.status === 0) return 'No connection to the server. Check your internet and try again.';
  const d = e?.error?.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) return d.map((x: any) => x.msg ?? String(x)).join('. ');
  if (d?.errors?.length) return `${d.message}: ${d.errors.join('; ')}`;
  if (d?.message) return d.message;
  return 'Something went wrong. Please try again.';
}

export const fmtPhone = (p: string) => `+91 ${p.slice(0, 5)} ${p.slice(5)}`;
export const fmtDate = (iso: string) => new Date(iso + (iso.length === 10 ? 'T00:00:00' : '')).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
export const fmtDateTime = (iso: string) => new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });

export function newId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : 'id-' + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
}
