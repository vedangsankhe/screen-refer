# NOTES

**Stack.** Angular + FastAPI + PostgreSQL (SQLite locally). Angular because the form is one generic renderer over a JSON config; FastAPI because
validation, auth and scoring sit in one small service; Postgres because Render's free disk is wiped on restart.
The first page load is about 78 KB, which suits weak connections.

## Things that must not break

- **DOB corrected after screening.** Each screening stores the age, DOB and sex it was done with, so history never changes. On a DOB or sex edit the
  server re-runs branching and scoring with the new values and attaches a warning (new age, new result, questions never asked). The doctor sees a banner
  and a "screen again" button. The edit and the flag are in the audit log.
- **Connection drops / refresh.** Answers autosave on the phone after every tap and are restored on reload, also offline. Each form has one `client_uuid`,
  so a retried submit returns the same screening and never creates a second one. If sending fails, the form waits and retries when the connection returns.
- **Same person twice.** The phone is reduced to 10 digits. Same phone plus a similar name (Devanagari is turned into rough Latin first, so "राहुल", "Rahul" and "Rahool" match)
  or the same DOB gives a 409 listing the matches. It is a warning, not a block, because families share phones ("save as new person").
- **Devanagari and phone formats.** UTF-8 and NFC normalisation throughout. `+91`, `0` prefix, `0091`, spaces and Devanagari digits all become the same 10 digits. Tests cover each.
- **Worker calls a doctor API.** 403 from `require_doctor`. Workers also cannot read other workers' patients or screenings: one query helper adds the owner filter and returns 404.
- **Answer changed, follow-up disappears.** Visibility cascades (hiding a parent hides its whole chain). The screen asks before hiding answered questions. The server scores only visible
  questions and keeps the dropped answers separately (`discarded_answers`) instead of losing them silently.

## One thing an AI tool got wrong that I caught

The generated timestamp helper converted timezone-aware times with `astimezone()`, which uses the server's own timezone, so the same code would show different
times on my laptop and on Render. Fixed to always convert to UTC (`access.iso`) and let the browser show local time.

## New requirement: SMS to the patient on High risk

**Change:** a consent flag and a verified phone on the patient; a background job or queue that fires when the *final* level becomes High; an SMS provider (India needs DLT template registration);
a neutral template that does not name a condition; a `notifications` table with an idempotency key so retries never send twice; audit entries. Decide whether to send on the calculated High or only after the doctor accepts it.
**Leave alone:** scoring rules, form config, role enforcement, the AI summary. SMS only listens to the final level, so none of them needs to know it exists.
