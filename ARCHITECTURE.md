# ExtraCare ERP — System Architecture

## Vision
A multi-tenant enterprise SaaS platform serving Schools, Hospitals, and Businesses. Each organization gets a fully isolated workspace, modular feature set, and role-based access control.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | Next.js 15 + Tailwind CSS | SSR, App Router, edge-ready |
| State | Zustand + TanStack Query | Server cache + client state, no Redux complexity |
| Backend | FastAPI (Python 3.12) | Fast, async, auto-docs, you already use it |
| Database | SQLite (dev) → MySQL/TiDB (prod) | Lightweight dev, horizontally scalable prod |
| Cache | Redis (optional) | Session cache, rate limiting, pub/sub |
| Auth | JWT (access + refresh) | Stateless, tenant-scoped |
| Deployment | Docker + Docker Compose | Runs on any $5 VPS |

### Why NOT PostgreSQL?
- **SQLite** works for teams < 1000 users with zero infra cost
- **TiDB** (MySQL-compatible, distributed) scales to 1M+ users with horizontal sharding
- **Turso** (libSQL) = distributed SQLite with edge nodes — perfect for Africa latency
- Swap just the `DATABASE_URL` to move between them

---

## Multi-Tenancy Strategy

```
Strategy: Subdomain-based tenant routing
acme-school.extracare.app  →  org_slug = "acme-school"  →  org_id = UUID
```

- Every DB table with tenant data has an `org_id` column (indexed)
- The `TenantMixin` enforces this in every model
- Every API query filters by `org_id` — no cross-tenant data leakage possible
- `X-Org-Slug` header for mobile/API clients
- No shared tables / row-level security at the app layer

---

## RBAC Model

```
Permissions are additive strings: "resource:action"
  e.g. "users:read", "students:write", "modules:*"

Roles contain arrays of permissions.
Users can have multiple roles (union of permissions).
Wildcard "*" = super admin.
```

**System roles (auto-created per org):**
- `org_admin` — full org control
- `manager` — read/write users + modules
- `staff` — read users + modules
- `viewer` — read only

Custom roles can be created per org with any permission combination.

---

## Module System

Modules are enabled per organization via `org.modules_enabled` (JSON array).
A FastAPI dependency `require_module("school")` guards every module route.

```
modules_enabled = ["hr", "school", "attendance", "grades", "notifications"]
```

**Available modules:**
| Key | Features |
|---|---|
| `hr` | Employee profiles, org chart |
| `payroll` | Payslips, deductions, payroll runs |
| `school` | Students, classes, timetable |
| `attendance` | Daily roll, summaries |
| `grades` | Gradebook, report cards |
| `hospital` | Patient records, EMR-lite |
| `appointments` | Doctor scheduling |
| `emr` | Medical history, prescriptions |
| `billing` | Invoices for hospital |
| `inventory` | Stock management |
| `analytics` | Dashboard KPIs |
| `notifications` | Email/push alerts |

---

## Database Schema Overview

```
organizations
  └── users (org_id FK)
       └── user_roles (many-to-many)
  └── roles (org_id FK)
  └── audit_logs (org_id FK)

  └── students (org_id FK)         [school module]
  └── school_classes
  └── subjects
  └── attendance_records
  └── grades
  └── timetables

  └── patients (org_id FK)         [hospital module]
  └── appointments
  └── medical_records
  └── medical_invoices

  └── employees (org_id FK)        [business module]
  └── leave_requests
  └── payslips
  └── inventory_items
```

All tables use UUID primary keys (no sequential IDs that leak count info).
All tenant tables have `org_id` FK + index.
Soft deletes everywhere (`is_deleted`, `deleted_at`).

---

## API Structure

```
/api/v1/
  /auth/
    POST /register          → create org + first admin
    POST /login             → returns JWT pair
    POST /refresh           → rotate tokens
    GET  /me                → current user info

  /users/
    GET  /                  → paginated list (with search/filter)
    POST /                  → create user
    POST /invite            → invite by email
    GET  /{id}              → get user
    PATCH /{id}             → update user
    PATCH /{id}/status      → suspend/activate
    PATCH /{id}/roles       → assign roles
    DELETE /{id}            → soft delete

  /analytics/
    GET  /overview          → dashboard KPIs
    GET  /activity-feed     → recent audit logs

  /school/
    GET/POST /students
    POST     /attendance
    GET      /attendance/summary
    POST     /grades
    GET      /students/{id}/report-card

  /hospital/
    GET/POST /patients
    GET/POST /appointments
    PATCH    /appointments/{id}/status
    POST     /records
    GET      /patients/{id}/history

  /business/
    GET      /employees
    POST     /leave-requests
    PATCH    /leave-requests/{id}/review
    GET/POST /payroll
    POST     /payroll/run
    GET/POST /inventory
```

---

## Frontend Structure

```
frontend/
├── app/
│   ├── (auth)/login/        ← Login page
│   ├── (auth)/register/     ← Org registration (onboarding)
│   └── (dashboard)/
│       ├── layout.tsx        ← Auth guard + Sidebar + TopBar
│       ├── dashboard/        ← Main KPI dashboard
│       ├── users/            ← User directory (from your prototype)
│       ├── analytics/        ← Charts, reports
│       └── modules/
│           ├── school/       ← Students, attendance, grades
│           ├── hospital/     ← Patients, appointments, EMR
│           └── business/     ← HR, payroll, inventory
├── components/
│   ├── layout/              ← Sidebar, TopBar, MobileNav
│   ├── dashboard/           ← MetricsGrid, ActivityFeed
│   └── users/               ← UserTable, UserModal, filters
├── hooks/                   ← useAuth, useUsers (React Query)
├── lib/
│   ├── api.ts               ← Axios client + all API calls
│   ├── store.ts             ← Zustand (auth + UI state)
│   └── utils.ts             ← Helpers
└── types/                   ← Full TypeScript interfaces
```

---

## Security Measures

1. **JWT with short TTL** (30min access, 7d refresh) — auto-rotated
2. **bcrypt password hashing** (Passlib)
3. **Org isolation** — every query filtered by `org_id`
4. **Account lockout** — 5 failed logins locks account
5. **Audit log** — every state change is logged (immutable)
6. **Soft deletes** — no data lost, full recovery possible
7. **Permission system** — fine-grained, checked per endpoint
8. **CORS** — whitelist-only origins
9. **Rate limiting** — via Redis (add SlowAPI in production)
10. **HTTPS** — enforced via Nginx in production

---

## Deployment (Step by Step)

### Development (local)
```bash
# Backend
cd backend
python -m venv venv
source venv/Scripts/activate  # Windows
pip install -r requirements.txt
cp ../.env.example .env       # edit SECRET_KEY
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
cp ../.env.example .env.local  # set NEXT_PUBLIC_API_URL
npm run dev
```

### Production (Docker)
```bash
cp .env.example .env
# Set: SECRET_KEY, ENVIRONMENT=production, DOMAIN
docker compose up -d
```

### Upgrade to TiDB/MySQL (when ready to scale)
```
DATABASE_URL=mysql+aiomysql://root:password@tidb-host:4000/extracare
```
Zero other code changes needed.

---

## Monetization Tiers

| Tier | Price | Users | Modules |
|---|---|---|---|
| Free | $0 | 10 | Core + 1 module |
| Starter | $29/mo | 50 | Core + 2 modules |
| Growth | $99/mo | 500 | All modules |
| Enterprise | Custom | Unlimited | All + SLA + custom domain |

**Add-on modules:** $15/mo each (e.g. AI assistant, advanced analytics, white-label)

---

## Advanced Features Roadmap

### Phase 2 (3-6 months)
- **WebSocket realtime** — live attendance, appointment queue updates
- **AI assistant** — Claude API integration for report generation, anomaly detection
- **Offline-first** — Service Worker + IndexedDB for low-connectivity Africa regions
- **Mobile apps** — React Native sharing business logic with web

### Phase 3 (6-12 months)
- **Parent portal** — separate login for school parents
- **WhatsApp integration** — attendance alerts, appointment reminders via WhatsApp API
- **Paystack/Flutterwave** — African payment gateway for subscriptions
- **Multi-language** — Yoruba, Hausa, Igbo, Swahili, French

---

## What Makes This Beat educare.school

| Feature | educare.school | ExtraCare ERP |
|---|---|---|
| Industries | Education only | School + Hospital + Business |
| Architecture | Monolith | Multi-tenant SaaS |
| Customization | Limited | Per-org modules + custom roles |
| API | No public API | Full REST API (docs at /api/docs) |
| Offline | No | PWA + Service Worker (Phase 2) |
| AI insights | No | Claude API integration (Phase 2) |
| White-label | No | Enterprise tier |
| Africa payments | No | Paystack/Flutterwave (Phase 3) |
