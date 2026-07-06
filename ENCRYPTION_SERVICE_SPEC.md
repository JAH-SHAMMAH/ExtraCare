# Encryption-at-Rest Service — Design Spec (for review)

**Status:** decisions A–F approved 2026-07-05. **Steps 1–3 (the encryption service
itself) are now BUILT** — `app/services/crypto.py`, `EncryptedStr`, key config, and
`tests/test_crypto.py` — as a self-contained, inert unit. **Step 4 (Payment Gateways
feature) is NOT started** and won't be until this unit is reviewed.
**Author:** build session, 2026-07-05.

**Approved decisions:** A app-managed key in env · B AES-256-GCM · C new
`payments:gateways:*` scope, org_admin only · D key must NOT be co-located with DB
backups/OneDrive sync (prod hosting plan still to be confirmed for the rotation
runbook) · E Paystack + Remita + Flutterwave · F no-PAN, hosted checkout only (SAQ-A).

---

## 1. Why this exists (the actual trigger)

Right now, payment-provider secrets live in **env/config as global plaintext**:

- `PAYSTACK_SECRET_KEY`, `PAYSTACK_PUBLIC_KEY`, `REMITA_API_KEY` in `app/config.py`.

That's one set of keys for the whole deployment, injected at boot, never written to
the DB. Env-injected secrets are already reasonably protected (not in the DB, not in
backups, not in the repo).

The **Payment Gateways** feature changes that: it lets *each school/org configure its
own gateway* (their own Paystack/Flutterwave/Remita secret key, webhook signing
secret) through the UI. Those per-org secrets have to be **persisted in the database**.
The moment a live gateway secret key lands in a DB row, we've created a new at-rest
exposure that env-based secrets never had. **This service is what makes that safe.**

> **Scope clarification (materially lowers risk):** We store the *school's gateway API
> credentials*, NOT customer card numbers / PANs. Using hosted gateway checkout
> (redirect/popup) means card data never touches our servers — this keeps us in the
> lightest PCI-DSS bracket (SAQ-A) and means the vault protects **API secrets only**,
> not a cardholder-data environment. We should keep it that way: **never** accept or
> store raw PANs.

---

## 2. What data the service protects

| Data | Sensitivity | Stored where today | After Payment Gateways |
|------|-------------|--------------------|------------------------|
| Gateway **secret key** (e.g. `sk_live_…`) | Critical — can move money / issue refunds | env (global) | encrypted per-org DB row |
| Gateway **webhook signing secret** | High — forge webhooks | not stored | encrypted per-org DB row |
| Gateway **public key** | Low — public by design | env | plaintext DB column (no need to encrypt) |

Design the primitive generically (`EncryptedStr`) so the same mechanism can later cover
SMTP passwords or SMS-provider keys if those ever move into per-org config — but **v1
scope is gateway secrets only.**

---

## 3. Threat model — what we defend against (and what we don't)

**In scope (must defend):**
- **DB dump / backup leak.** A stolen `.db` file / SQL backup must not reveal live
  gateway secrets. (Especially relevant here: the dev DB can end up under a synced
  OneDrive folder — an at-rest leak vector.)
- **Repo / source leak.** No secret material in code or migrations.
- **Casual over-read via the API.** An admin (or a bug) must not be able to read a
  secret back in plaintext through any endpoint — write-only, masked on read.
- **Accidental logging / serialization.** Plaintext must never hit logs, audit
  metadata, error traces, or API responses.

**Explicitly OUT of scope (documented limitation):**
- **Full app-server compromise.** If an attacker has *both* the database *and* the
  process environment (where the master key lives), they can decrypt. App-managed
  keys cannot defend against this — only an external HSM/KMS with per-operation
  authz can, at significant added complexity. We accept this tradeoff for a
  self-hostable, Africa-first deployment (see §5, Decision A). The mitigation is
  **key/DB separation**: the key must never sit in the same place as a DB backup.

---

## 4. Cryptographic design

- **Algorithm:** AES-256-GCM (authenticated encryption — confidentiality + tamper
  detection) via the already-installed `cryptography` package (`AESGCM`).
  - Alternative considered: `Fernet` (AES-128-CBC + HMAC). Simpler, but 128-bit and
    no additional-authenticated-data support. **Recommend AES-256-GCM.**
- **Per-value random nonce** (96-bit), never reused with the same key.
- **Stored token format** (self-describing, so decrypt needs no side lookup):
  ```
  v<key_version>:<base64(nonce)>:<base64(ciphertext+tag)>
  e.g.  v1:3rf9…:8Kd2…
  ```
  The `key_version` prefix is what makes rotation possible (§6).
- **AAD (optional, recommended):** bind each ciphertext to its `org_id` + column name
  as additional-authenticated-data, so a ciphertext can't be copied from one org's
  row into another's and still decrypt.

---

## 5. Key management

**Master key:** a dedicated **`ENCRYPTION_KEY`** (32 random bytes, base64 in env) —
**separate from the existing `SECRET_KEY`** (JWT signing). Separation means rotating
one never disturbs the other, and a leaked JWT key doesn't expose stored secrets.

- Generate: `python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"`
- **Never** committed, never in the DB, never in a backup that also contains the DB.
- Lives in: dev → `.env` (git-ignored); prod → the platform's secret store / env vars.

**Fail-fast validation** (mirror the existing `config.py` production validator): if the
Payment Gateways feature is enabled and `ENCRYPTION_KEY` is missing/weak, the app
refuses to boot rather than silently storing recoverable-but-unencrypted data.

**Envelope encryption?** Not for v1. With only a handful of gateway credentials per
org, a single versioned master key is sufficient. Per-record data keys (DEK/KEK) add
moving parts we don't need yet — noted as a future option if secret volume grows.

---

## 6. Key rotation

Versioned keys make rotation non-breaking:

- Config holds a map: `ENCRYPTION_KEYS = { "1": <key1>, "2": <key2> }` and
  `ENCRYPTION_KEY_ACTIVE = "2"`.
- **Decrypt** reads the `v<n>` prefix and uses that version's key (old ciphertext keeps
  working).
- **Encrypt** always uses the *active* version.
- **Rotation procedure:** add new key version → set it active → run a background
  re-encrypt pass (decrypt-with-old, encrypt-with-active) over stored secrets →
  once none reference the old version, retire it.
- A `crypto rotate` management command performs the re-encrypt pass. No downtime.

---

## 7. Storage & ORM integration

- A SQLAlchemy **`EncryptedStr` `TypeDecorator`**: encrypts on write (`process_bind_param`),
  decrypts on read (`process_result_value`). Columns declared `Column(EncryptedStr)`
  transparently store ciphertext; the model attribute is plaintext *only in memory*.
- Gateway config table (illustrative): `org_id`, `provider` (paystack|flutterwave|remita),
  `public_key` (plain), `secret_key` (`EncryptedStr`), `webhook_secret` (`EncryptedStr`),
  `is_live`, `is_active`, timestamps.
- **Write-only secret fields:** the API accepts a secret on create/update but **never
  returns it**. Reads return a **mask** only (`sk_live_••••4242`) + metadata (last-4,
  updated_at, who set it). A `mask()` helper produces this.

---

## 8. Service API surface (`app/services/crypto.py`)

```
encrypt(plaintext: str, *, aad: str | None = None) -> str      # -> versioned token
decrypt(token: str, *, aad: str | None = None) -> str          # raises on tamper/bad key
mask(plaintext: str, visible: int = 4) -> str                  # "sk_live_••••4242"
rotate_all(db) -> int                                          # re-encrypt to active key
class EncryptedStr(TypeDecorator): ...                         # transparent column type
```

Small, dependency-light, unit-testable in isolation (round-trip, tamper-detection,
cross-version decrypt, wrong-key failure, AAD mismatch).

---

## 9. Access control & handling rules

- **RBAC:** managing gateway credentials is **not** general `payments:write`. Proposed
  new narrow scope **`payments:gateways:write`** (read = `payments:gateways:read`),
  granted to **org_admin only** by default. *(Flagging this as a decision — see below.)*
- **Decryption happens only at point of use** — when actually calling the gateway —
  never eagerly, never to render a page.
- **Audit** every create / update / rotate / delete via the existing `audit_service`,
  recording *that* a secret changed and *who* — **never the value**.
- Plaintext must be scrubbed from Pydantic response models (write-only field), logs,
  and exception handlers.

---

## 10. Rollout plan

1. ✅ **DONE** — `cryptography==46.0.7` pinned explicitly in `requirements.txt`.
2. ✅ **DONE** — `app/services/crypto.py` + `EncryptedStr` + `tests/test_crypto.py`
   (18 unit tests). Inert until a model uses it.
3. ✅ **DONE** — `ENCRYPTION_KEY` / `ENCRYPTION_KEY_VERSION` / `ENCRYPTION_KEYS_OLD`
   in `config.py` + `.env.example` (with the OneDrive-sync warning), and a
   `PAYMENT_GATEWAYS_ENABLED` flag gating a fail-fast production validator.
4. ⏳ **NOT STARTED** — build Payment Gateways on top (per-org config table using
   `EncryptedStr`, write-only masked API, `payments:gateways:*` RBAC, gateway call
   sites reading decrypted secrets in-memory).
5. ⏳ **NOT STARTED** — flip `PAYMENT_GATEWAYS_ENABLED` on once the feature ships.

Steps 1–3 are the "encryption service" (built); step 4 is the feature it unblocks
(awaiting review + the decision-D hosting confirmation).

---

## 11. Open decisions I need from you

- **A. Key custody:** app-managed master key in env (recommended — self-hostable, no
  cloud dependency, matches the Africa-first / no-heavy-infra posture) **vs** external
  KMS/Vault (stronger against full-server compromise, but adds an infra dependency).
- **B. Cipher:** AES-256-GCM (recommended) vs Fernet (simpler, 128-bit).
- **C. RBAC scope:** new `payments:gateways:*` granted to org_admin only (recommended)
  vs reuse an existing scope.
- **D. Where the prod key lives** in your actual deployment (env var / platform secret
  store) — determines the rotation runbook.
- **E. Which providers first** — Paystack + Remita already have env keys; Flutterwave
  is Africa-common. Confirm the v1 provider list.
- **F. Confirm the no-PAN stance** (hosted checkout only, never store card numbers) so
  we stay SAQ-A and this vault only ever holds API secrets.
```
