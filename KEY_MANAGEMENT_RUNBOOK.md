# Encryption Key Management — Runbook

> ⚠️ **PLACEHOLDER — REVISIT ONCE INFRASTRUCTURE IS CHOSEN.**
> Hosting is not yet decided. This runbook assumes the simplest target: **one
> production Linux host**, with the encryption key supplied as an **OS-level
> environment variable**. When we pick real infrastructure (managed VPS,
> container platform, secrets manager, multi-host, etc.) this document must be
> rewritten to match — the *procedures* stay the same, only *where the key lives*
> and *how it's injected* change. Decision D in `ENCRYPTION_SERVICE_SPEC.md`.

Covers `ENCRYPTION_KEY` — the AES-256-GCM master key that protects stored gateway
secrets (`app/services/crypto.py`). Separate from `SECRET_KEY` (JWT signing).

---

## The one rule that must never be broken

**The key and the database must never be recoverable from the same place.**

If a DB dump (or a synced/backed-up folder that contains the `.db` file) also
carries the key, encryption-at-rest provides **zero** protection — whoever has that
one bundle has both halves. This is why:

- ❌ The prod key must **NOT** live in a `.env` file inside a **OneDrive-synced**
  folder (the current dev working directory *is* such a folder).
- ❌ The prod key must **NOT** be committed to git.
- ❌ The prod key must **NOT** be included in the same backup set as the database.
- ✅ The prod key **lives only in the host's environment** (see below), and DB
  backups are taken *without* it.

Dev is exempt only because the dev key protects throwaway data — but dev and prod
are separated **by configuration, not by convention**: both read the same
`ENCRYPTION_KEY` env var, so nothing code-level assumes a location. Whatever host we
choose later just needs to set that variable from its own secret store.

---

## 1. Generate a key

```bash
python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
# → a 44-char base64 string decoding to 32 bytes
```

## 2. Install it on the production host (placeholder: single Linux host)

Set it as an environment variable for the app process **only** — not in a
world-readable file, not in the repo, not in a synced directory.

- **systemd service** (recommended for a single host): put it in a root-owned
  drop-in that is `chmod 600`, e.g. `/etc/extracare/portal.env`:
  ```
  ENCRYPTION_KEY=<base64 key>
  ENCRYPTION_KEY_VERSION=1
  ```
  and reference it from the unit: `EnvironmentFile=/etc/extracare/portal.env`.
  This file is on the host's own disk, outside any sync/backup of the database.
- Confirm it is loaded (never print the value in shared logs):
  ```bash
  systemctl show extracare-portal -p Environment | grep -o ENCRYPTION_KEY
  ```
- Set `PAYMENT_GATEWAYS_ENABLED=true` to turn the feature on. With
  `ENVIRONMENT=production`, boot will **fail fast** if the key is missing.

> When infra is chosen, replace this section with that platform's secret
> mechanism (e.g. a secrets manager injected as env at deploy). Nothing else here
> changes.

## 3. Back up the key — separately from the database

Store the key in a password manager / offline vault that is **not** part of the
database backup rotation. Losing the key means every stored gateway secret becomes
permanently unreadable (the school just re-enters them, but avoid the scramble).

---

## 4. Rotate the key

Non-breaking, thanks to versioned ciphertext (`v<n>:…`):

1. Generate a new key (step 1).
2. Move the current active key into the retired map and set the new one active:
   ```
   ENCRYPTION_KEYS_OLD={"1":"<old base64 key>"}
   ENCRYPTION_KEY=<new base64 key>
   ENCRYPTION_KEY_VERSION=2
   ```
   Old ciphertext (`v1:…`) still decrypts via `ENCRYPTION_KEYS_OLD`; new writes use
   `v2`.
3. Re-encrypt stored secrets to the active version. The primitive exists
   (`crypto.reencrypt` / `crypto.needs_rotation`); the table-walking command lands
   with the feature that stores secrets. Until then, an admin re-saving each
   gateway's secret in the UI re-encrypts it under the active key.
4. Once nothing references `v1`, drop it from `ENCRYPTION_KEYS_OLD`.

## 5. Suspected key compromise

1. Rotate immediately (step 4) **and** rotate the actual gateway credentials at the
   provider (Paystack/Remita/Flutterwave dashboard) — a leaked key means the stored
   secrets themselves must be considered exposed.
2. Re-enter fresh provider secrets in the Payment Gateways screen.
3. Review the audit log for `PaymentGateway` record events.

---

## Open items to resolve when infra is chosen (Decision D)

- [ ] Where the prod key actually lives (systemd env-file vs secrets manager).
- [ ] Whether prod is single-host or multi-host (key distribution changes).
- [ ] DB backup process — confirm it provably excludes the key.
- [ ] Automate the re-encrypt rotation pass as a management command.
