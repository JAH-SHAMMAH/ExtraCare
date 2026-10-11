# Working rules for this repository

## Secrets never enter the repository

**No credential, token, password or connection string may be written into any
tracked file, commit message, commit body, script, test fixture, documentation
example or log line.** Not temporarily. Not "just for a dry run". Not in a
comment.

This is not a style preference. On **2026-08-23** a file called
`backend/scripts/student_credentials_output.csv` was committed with 450 rows of
`(student_id, email, temp_password)` — every password populated — into a
repository that was **public**. It sat there for seven weeks. In the same
repository were two live PostgreSQL passwords, inline in 40 diagnostic scripts,
and three more scripts that set a real account's password from a literal in the
source.

None of it was deliberate. They were one-off scripts written against the live
database and committed along with everything else. That is exactly why the rule
has to be absolute rather than a matter of judgement in the moment: the failure
mode is *forgetting*, and a rule with exceptions is one you have to remember to
apply.

### Where secrets go instead

| what | where |
|---|---|
| anything the deployed app needs | the host's environment / secret settings (Render → Environment) |
| anything a local script needs | an environment variable, **or a hidden prompt** |
| anything a developer needs locally | their own untracked `.env`, which `.gitignore` already covers |

**Use a dedicated variable name for scripts**, never `DATABASE_URL`. That name
is what alembic, the app and `docker-compose` read, so setting it in a shell so
a diagnostic can run arms all three — one absent-minded `alembic upgrade head`
in that shell afterwards migrates the live database. `backend/_dsn.py` reads
`ADHOC_DATABASE_URL`; the audit and deactivation scripts read their own names.

**Never take a secret from `sys.argv`.** An address or password on the command
line is recorded in shell history and is visible in the process list to any
other user on the machine. Every script in `backend/scripts/` refuses an
argument that looks like a connection string and prompts hidden instead.

**Never print one.** Not on success, not in a usage message, and not in an error
— driver exceptions embed the whole DSN, so redact `user:password@` before any
exception reaches a terminal (`redact()` in the audit script). A password echoed
into a terminal cannot be un-echoed: it is in the scrollback, the shell history
file and any CI log.

### Generated, not chosen

Seed, demo and reset scripts **generate** a password at runtime with
`secrets.token_urlsafe` and print it once. They do not carry a default, and they
do not write it to a file. A committed default password is a credential for
every deployment that ever used the script.

### The automated guards

Two, and with the repository private they are the only ones:

1. **`tools/scan_secrets.py` + `.githooks/pre-commit`** — blocks the commit.
   Enable it once per clone; git will not do it for you:

   ```
   git config core.hooksPath .githooks
   ```

2. **`.github/workflows/secret-scan.yml`** — gitleaks plus the same scanner, on
   every push and pull request. This is the one that does not depend on anyone
   remembering, which is why it has no bypass flag and is a required check.

Neither prints a matched value. A guard that echoed the secret would copy it
into the terminal, the shell history and the CI log, turning a prevented leak
into a second one.

### If a secret does reach a commit

**Rotate it.** Immediately, and before anything else. Deleting the file does not
un-publish it: forks, clones and GitHub's own caches persist, and on a public
repository you must assume it was read. Removing the file and rewriting history
are tidying; rotation is the fix.

Then record it, so the next person understands why these rules look paranoid.

## Data on disk

The working copy lives under **OneDrive**, which syncs to the cloud. Files that
`.gitignore` excludes from git are **not** excluded from OneDrive —
`backend/*.db`, `backend/backups/`, `backend/uploads/` and any `.dump` all sync.
Before real pupil data goes in, move the working copy out of OneDrive.

`GO_LIVE_DELETION_CHECKLIST.md` lists the paths holding copies of production
data that must be deleted at cutover.
