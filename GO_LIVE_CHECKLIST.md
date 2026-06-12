# Fairview School Portal — Go-Live Checklist

**Version 1.0.** Work top to bottom. Do not launch with any **Security**,
**Backups**, or **Credentials** item unchecked.

---

## Security
- [ ] `ENVIRONMENT=production`, `DEBUG=false`, `ENABLE_API_DOCS=false`
- [ ] `SECRET_KEY` set to a fresh 32-byte random value (`openssl rand -hex 32`)
- [ ] `ALLOWED_ORIGINS` = production domain only
- [ ] `/api/docs` returns 404 in production
- [ ] Domain gate verified: non-`@fairviewschoolng.com` login → 403
- [ ] Rate limiting active (login 20/min, refresh 60/min); lockout after 5 failed logins
- [ ] `/register` shows the "by invitation" notice (no public signup)
- [ ] Security headers present (HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy)

## Backups
- [ ] `scripts/backup_db.py` runs and produces a snapshot
- [ ] Nightly cron installed; backups copied **off-box** to another region, encrypted
- [ ] One full **restore drill** completed; RTO/RPO recorded (`BACKUP.md`)
- [ ] Pre-deploy backup taken before first launch

## Credentials
- [ ] Seeded **principal** password rotated (`principal@fairviewschoolng.com`)
- [ ] Seeded **teacher** passwords rotated or accounts removed if not real staff
- [ ] Legacy dev users on non-Fairview domains purged
- [ ] Real Paystack **live** keys set (`sk_live_…`, `pk_live_…`)
- [ ] DB credentials least-privilege; `.env` not committed to source control

## Domain configuration
- [ ] DNS resolves the portal domain to the host
- [ ] `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_SITE_URL` set to public HTTPS URLs
- [ ] web image **rebuilt** with the correct `NEXT_PUBLIC_API_URL`
- [ ] nginx `server_name` matches the real domain

## SSL
- [ ] Valid TLS cert installed (`./certs/fullchain.pem`, `privkey.pem`)
- [ ] HTTP → HTTPS redirect works
- [ ] HSTS header served; cert auto-renewal configured (e.g. certbot timer)

## Email configuration
- [ ] **ACK: email is NOT implemented** — no SMTP sender exists in the app
- [ ] Password resets / invites handled **manually** (admin sets credentials)
- [ ] Stakeholders informed that email-dependent flows are out of scope for v1

## Attendance testing
- [ ] `POST /attendance/manual` (check_in) → daily record shows present/late per the 08:00 cutoff (Africa/Lagos)
- [ ] `POST /attendance/events/ingest` with a repeated `external_ref` → deduped (no duplicate)
- [ ] Admin **Attendance Insights** shows correct present/late/absent + late-arrivals + absentees
- [ ] Teacher **Class Attendance** records check-in/out for a class

## Parent notification testing
- [ ] Linked parent receives the **arrival** alert: "… has successfully checked into Fairview School at H:MM AM/PM" with correct local time
- [ ] Linked parent receives the **departure** alert
- [ ] A non-guardian parent **cannot** see another child's attendance (403)
- [ ] Alerts appear in the parent's Attendance dashboard; "mark all read" works

## Final smoke (≤ 30 min — see DEPLOYMENT.md)
- [ ] All services healthy; `alembic current` = head (`002_add_attendance_events`)
- [ ] `/health` returns `{"status":"ok","environment":"production"}`
- [ ] Principal login + dashboard; create test student + parent link + class
- [ ] Fees: parent fee lookup works; admin reconcile screens load
- [ ] One Paystack test payment → webhook verified, transaction recorded
- [ ] Audit Log shows login + attendance events; no browser console/network errors

**Sign-off:** ______________________  **Date:** ____________
