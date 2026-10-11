# Go-live deletion checklist

Paths holding copies of production data, to delete at cutover.

**Paths only. No credentials, no connection strings, no data, no counts of
anything identifying.** This file is tracked, so it must stay safe to read.

Inventory taken 2026-10-11. Re-check before cutover: a dump written after that
date will not be listed here.

---

## 1. Copies of the production database

- [ ] `C:\Users\SHAMMAH\fairview-backups\fairview_138.dump`
      — a full dump. Carries every user row and password hash.
      **Keep until the cutover is complete**, then delete. It is the only test
      bed the audit and deactivation scripts have, and rehearsing against it has
      caught several faults that unit tests could not.
- [ ] `C:\Users\SHAMMAH\fairview-backups\` — the remaining subdirectories and
      manifest files from the migration work. The manifests record pupil and
      mark rows.
- [ ] Any `.dump`, `.sql`, `.sql.gz` or `.pgdump` written after this inventory.
      Find them with:
      `Get-ChildItem $HOME -Recurse -Include *.dump,*.sql,*.sql.gz,*.pgdump -ErrorAction SilentlyContinue`

## 2. Working copies extracted from the database

- [ ] `%LOCALAPPDATA%\Temp\claude\<project>\<session-id>\scratchpad\`
      — per-session working directories. The `raw_*.sql` table extracts from the
      2026-10-11 session were deleted that day; later sessions may create more.
      Check each session folder for `raw_*.sql`, `*.tsv`, `*.csv`.

## 3. Local databases and uploads inside the repository

All are git-ignored, so none of these can be committed — but they exist on disk
and, while the repository sits under OneDrive, **they sync to the cloud**.

- [ ] `backend/extracare.db`
- [ ] `backend/extracare.db.backup-*`
- [ ] `backend/extracare.db.pre-phase2-backup`
- [ ] `backend/fairview.db`
- [ ] `backend/backups/`
- [ ] `backend/uploads/`

## 4. Tooling (no data — delete only to tidy)

- [ ] `C:\Users\SHAMMAH\pgsql\` — PostgreSQL client/server binaries used to
      rehearse scripts against a restored dump. No data.
- [ ] `C:\Users\SHAMMAH\erp-worktrees\` — git worktrees.
      **Remove with `git worktree remove <path>`, not `rm`**, or the repository
      keeps a stale registration and `git worktree list` lies.
- [ ] Throwaway PostgreSQL data directories. None are outstanding as of this
      inventory; each rehearsal stops its server and deletes its data directory.
      Confirm with: `Get-Process postgres -ErrorAction SilentlyContinue`

---

## Before any real pupil data goes in

- [ ] **Move the working copy out of OneDrive.** `.gitignore` keeps the local
      databases, backups and uploads out of *git*; it does nothing about
      OneDrive, which syncs them to the cloud regardless. A database of real
      children's records should not be replicated to consumer file sync.
- [ ] **Rotate every credential that was ever committed.** Deleting a file does
      not un-publish it — forks, clones and provider caches persist, and the
      repository was public for seven weeks. Rotation is the fix; deletion is
      tidying.
- [ ] Enable the local hook in every clone: `git config core.hooksPath .githooks`
- [ ] Confirm the `secret-scan` workflow is a **required** status check on the
      default branch.

## Not on this list, and why

Build caches (`frontend/.next`, `node_modules`) hold no database data. They are
large and junctioned out of OneDrive already; deleting them only costs a rebuild.
