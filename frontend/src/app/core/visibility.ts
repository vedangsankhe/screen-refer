/**
 * Same rule language and same behaviour as backend/app/services/visibility.py.
 * The server is the authority (it re-checks everything on submit); this copy only decides what to show.
 */
export function evaluate(cond: any, ctx: Record<string, any>): boolean {
  if (!cond) return true;
  if (cond.all) return cond.all.every((c: any) => evaluate(c, ctx));
  if (cond.any) return cond.any.some((c: any) => evaluate(c, ctx));
  if (cond.not) return !evaluate(cond.not, ctx);
  const v = ctx[cond.q];
  const ops = Object.keys(cond).filter(k => k !== 'q');
  if (!ops.length) throw new Error('Condition has no operator');
  const has = v !== undefined && v !== null;
  return ops.every(op => {
    const x = cond[op];
    switch (op) {
      case 'eq': return v === x;
      case 'neq': return has && v !== x;
      case 'in': return x.includes(v);
      case 'gt': return has && v > x;
      case 'gte': return has && v >= x;
      case 'lt': return has && v < x;
      case 'lte': return has && v <= x;
      default: throw new Error(`Unknown operator ${op}`);
    }
  });
}

/** Questions are visible only if their rule passes using age, sex and the answers to VISIBLE earlier questions. */
export function resolveVisible(questions: { id: string; visibleIf?: any }[], age: number, sex: string, answers: Record<string, any>): string[] {
  const ctx: Record<string, any> = { age, sex };
  const visible: string[] = [];
  for (const q of questions) {
    if (evaluate(q.visibleIf, ctx)) {
      visible.push(q.id);
      if (q.id in answers) ctx[q.id] = answers[q.id];
    }
  }
  return visible;
}
