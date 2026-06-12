# ExtraCare ERP Workspace Isolation Architecture

## Architecture Audit

ExtraCare ERP already had strong shared foundations: tenant-scoped models, shared authentication, shared subscriptions, audit logs, notifications, analytics, imports, and admin screens. The leakage came from product-surface decisions being made in several places at once:

- `Organization.modules_enabled` was treated as a raw UI source, so legacy rows with `school` enabled could leak into business or hospital shells.
- Default roles granted cross-vertical permissions such as `school:*`, `business:*`, and `hospital:*` together.
- The sidebar and dashboard assembled school-first UI without consistently checking the organization industry.
- Analytics and dashboard endpoints counted all vertical entities unless each caller guarded the output.

## Workspace Type Engine

`backend/app/core/workspace.py` is the backend source of truth. It defines the supported workspaces:

- `school`
- `business`
- `hospital`
- `hybrid` for legacy multi-vertical tenants

The engine exposes helpers for:

- resolving an organization industry to a workspace definition
- deriving effective modules without mutating legacy database rows
- checking module ownership by workspace
- blocking cross-workspace permission namespaces
- seeding safe default modules for new tenants

`frontend/lib/workspace.ts` mirrors the same registry for hydration-safe UI rendering. The backend remains authoritative.

## Module Isolation

New tenants are seeded with one primary module only:

- School: `["school"]`
- Business: `["business"]`
- Hospital: `["hospital"]`
- Hybrid: `["business", "hospital", "school"]`

Submodules such as `transport`, `sms`, `inventory`, `crm`, `pharmacy`, and `lab` map back to their owning workspace. Existing tenants are not destructively migrated. Instead, responses and guards use effective modules, so stale raw values stop rendering or authorizing unrelated product surfaces.

## Sidebar and Routing

The sidebar now renders workspace sections through `moduleAllowedForOrg`. Business tenants see business modules; school tenants see school modules; hospital tenants see healthcare modules. `ModuleGate` also checks the workspace before rendering vertical route groups.

Existing route URLs are preserved:

- `/dashboard/modules/school/*`
- `/dashboard/modules/business/*`
- `/dashboard/modules/hospital/*`

This keeps bookmarks and API contracts stable while preventing the wrong workspace shell from appearing.

## Scoped RBAC

Role presets are now generated per industry:

- School roles receive school permissions only, plus shared core admin scopes where appropriate.
- Business roles receive business, payroll, finance, inventory, and CRM scopes.
- Hospital roles receive hospital scopes.

`PermissionChecker` rejects cross-vertical permission namespaces even if an old role row still contains them. This is the key backward-compatibility guard: old data can exist, but it cannot authorize the wrong workspace.

## School HR Enhancement

School HR is intentionally kept on the shared HR engine instead of being duplicated. Schools retain school-specific staff structures while gaining the richer HR foundation already used by business workspaces: staff records, leave, birthdays, attendance-adjacent data, payroll-ready metadata, and shared HR permissions.

## SEO System

The frontend now includes:

- global metadata strategy in `frontend/app/layout.tsx`
- canonical URLs
- OpenGraph and Twitter metadata
- `robots.txt` via `frontend/app/robots.ts`
- sitemap generation via `frontend/app/sitemap.ts`
- structured `SoftwareApplication` and `FAQPage` JSON-LD
- semantic industry landing pages:
  - `/erp-for-schools`
  - `/business-management-erp`
  - `/hospital-management-system`

The landing pages target high-intent searches around school ERP, business record keeping, and hospital management ERP while linking internally between workspace pages.

## Migration Strategy

No destructive migration is required for this phase.

Recommended production rollout:

1. Deploy the workspace engine and effective-module reads.
2. Run startup role synchronization to create missing workspace roles and align system role permissions.
3. Audit tenants where `modules_configured` differs from `modules_enabled` in `/auth/me`.
4. Optionally add a non-destructive data migration later to clean raw `modules_enabled` rows after customer review.

## Testing Strategy

Focused tests cover:

- JWT module claims by industry
- school-to-hospital rejection
- business tenants seeded without school or hospital modules
- legacy business tenants with stray school modules still being filtered
- frontend workspace module filtering
- frontend cross-workspace permission blocking

Recommended follow-up coverage:

- Playwright smoke tests for each workspace sidebar
- permission matrix tests for doctor, nurse, teacher, parent, employee, HR officer, and accountant roles
- SEO route snapshot tests for metadata, canonical, and structured data

## Backward Compatibility and Performance

The implementation preserves existing database tables, route paths, authentication, billing, notifications, and admin framework. Effective module filtering is computed from existing org fields and uses simple set membership, so runtime overhead is minimal. Dashboard and analytics endpoints continue to use tenant-scoped queries and now skip vertical counts that do not belong to the active workspace.
