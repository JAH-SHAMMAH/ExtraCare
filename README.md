# school-portal

Dedicated school portal (single-school deployment of the underlying ERP core).
Backend: FastAPI + async SQLAlchemy + Alembic. Frontend: Next.js (App Router) +
React Query + Tailwind.

> Repo identifier: **school-portal**. The working directory is still named
> `ExtraCare ERP`; only the project/repo identity is `school-portal`.

## Layout

- `backend/` — FastAPI app, models, routers, services, Alembic migrations, tests.
- `frontend/` — Next.js app (dashboard, modules, components, hooks).

## Local dev

Backend:

```bash
cd backend
./venv/Scripts/python.exe -m uvicorn app.main:app --reload
./venv/Scripts/python.exe -m pytest -q          # tests
./venv/Scripts/alembic.exe upgrade head         # migrations
```

Frontend:

```bash
cd frontend
npm run dev
npx tsc --noEmit                                 # type-check
```

## Notes

- `node_modules/`, `.next/`, and `venv/` are Windows junctions to `C:\dev-cache`
  and are git-ignored. Re-junction `node_modules` after any `npm install`.
- Secrets live in `.env` (git-ignored); see `.env.example`. The encryption key
  (`ENCRYPTION_KEY`) must never be committed or co-located with DB backups —
  see `ENCRYPTION_SERVICE_SPEC.md` / `KEY_MANAGEMENT_RUNBOOK.md`.
- Deferred work and tickets are tracked in `POST_LAUNCH_BACKLOG.md`.
- No git remote is configured; commit locally per session, no push/PR unless asked.
