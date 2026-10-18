#!/usr/bin/env python3
"""Refuse to let a credential into the repository. Prints no secret, ever.

~~~ WHY THIS EXISTS ~~~
On 2026-08-23 a file called `backend/scripts/student_credentials_output.csv` was
committed: 450 rows of (student_id, email, temp_password), every password
populated. It sat in a PUBLIC repository for seven weeks. Alongside it, 39
tracked scripts carried a live PostgreSQL password inline, and three more set a
real account's password from a literal in the source.

None of that was malicious and none of it was obvious -- they were one-off
diagnostics written against the live database and committed with everything
else. A person cannot reliably notice this in a diff; a hook can.

~~~ WHAT IT WILL NOT DO ~~~
It never prints a matched value, only the pattern's name, the file and the line.
A failure that echoed the secret would write it into the terminal scrollback,
the shell's history file and any CI log -- turning a prevented leak into a
second copy. The point is to stop the commit, not to show the finding.

~~~ MODES ~~~
    python tools/scan_secrets.py              # staged content (what the hook runs)
    python tools/scan_secrets.py --worktree   # files on disk, committed or not
    python tools/scan_secrets.py --tree       # every tracked file as of HEAD
    python tools/scan_secrets.py --history    # every blob in every commit (slow)

`--tree` reads HEAD, so it will NOT show work you have not committed yet; use
`--worktree` for that. Confusing the two once made an already-fixed file look
unfixed.

Exit status 1 means something blocking was found. For a value that is genuinely
not a secret, put `# pragma: allowlist-secret` on that line. `--no-verify`
bypasses the hook entirely, which should be rare and worth a note in the commit
message.

INSTALL THE HOOK (once per clone; git does not do this for you):
    git config core.hooksPath .githooks
"""
from __future__ import annotations

import re
import subprocess
import sys

ALLOW = re.compile(r"pragma:\s*allowlist-secret", re.I)

#: Things that are a credential if they appear at all. These BLOCK everywhere,
#: test files included -- a real key does not become safe by living in a test.
#:
#: The `[^$]` guards on the connection-string pattern keep ${VAR} templates out:
#: docker-compose builds its DSN from ${DB_USER}:${DB_PASSWORD}@, which is a
#: template rather than a credential, and flagging it would teach people to
#: ignore this hook. `<>` does the same for <user>:<password> in docs.
HIGH = [
    ("connection string with a password",
     re.compile(rb"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)"
                rb"(?:\+\w+)?://[^\s:/@\"'$<>]+:[^\s@/\"'$<>][^\s@/\"'<>]{2,}@")),
    ("cloudinary url with secret",
     re.compile(rb"cloudinary://\d+:[A-Za-z0-9_\-]{10,}@")),
    ("private key block",
     re.compile(rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("aws access key id", re.compile(rb"\bAKIA[0-9A-Z]{16}\b")),
    ("aws secret access key",
     re.compile(rb"(?i)aws_secret_access_key\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{35,}")),
    ("github token", re.compile(rb"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b")),
    ("github fine-grained token", re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{50,}\b")),
    ("slack token", re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("stripe/paystack live secret", re.compile(rb"\bsk_live_[A-Za-z0-9]{16,}\b")),
    ("flutterwave secret", re.compile(rb"\bFLWSECK(?:_TEST)?-[A-Za-z0-9]{10,}\b")),
    ("google api key", re.compile(rb"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("anthropic api key", re.compile(rb"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("sendgrid api key",
     re.compile(rb"\bSG\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}\b")),
    ("json web token",
     re.compile(rb"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.")),
]

#: Assignments that are usually a secret. Placeholders are filtered out, and a
#: value under 8 characters is almost always a fixture rather than a credential.
ASSIGNED = re.compile(
    rb"(?i)\b([a-z0-9_]*(?:password|passwd|pwd|secret|token|api_?key|private_?key)"
    rb"[a-z0-9_]*)\s*[:=]\s*([\"'])([^\"'\n]{8,})\2")

#: The literal "passwords" docs and templates use inside a DSN, e.g.
#: postgresql://user:pass@host/db. Matched against the whole connection string.
CONN_PLACEHOLDER_PW = re.compile(
    rb"(?i)://[^:/@]+:(?:pass|password|passwd|pwd|secret|changeme|change_me|postgres|root|admin)@")

PLACEHOLDER = re.compile(
    rb"(?i)\A(?:your[-_ ]|changeme|change_me|example|placeholder|dummy|replace|"
    rb"redacted|xxx+|\*{3,}|none|null|true|false|\$\{|\$[A-Z_]+|<|\{\{|"
    rb"os\.environ|getenv|secrets?\.|token_urlsafe|test[-_]?)"
    rb"|(?:example|placeholder|changeme|redacted)\Z")

#: A credential-shaped column in a data file means it is a credential dump,
#: whatever the file is called.
CRED_COLUMN = re.compile(
    rb"(?i)\b(?:temp_?password|password|passwd|pwd|secret|api_?key|private_?key|"
    rb"token|otp|pin)\b")

SKIP_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".woff",
            ".woff2", ".ttf", ".eot", ".zip", ".gz", ".pyc", ".mp4", ".dump",
            ".lock", ".svg")
SKIP_PATH = ("/node_modules/", "/.next/", "/venv/", "/__pycache__/",
             "package-lock.json", "tools/scan_secrets.py")

NUL = bytes([0])


def interesting(path: str) -> bool:
    low = path.lower()
    return not (low.endswith(SKIP_EXT) or any(s in path for s in SKIP_PATH))


def is_fixture(path: str) -> bool:
    """A test file's assigned passwords are fixtures by convention.

    They are still REPORTED, but they do not fail the commit: twenty
    conventional `password="..."` lines across the payment and auth tests would
    otherwise make every contributor reach for --no-verify, which costs more
    than it saves. The HIGH patterns -- real key formats, connection strings,
    private keys -- still block here, so a genuine credential in a test is
    still caught.
    """
    low = path.replace("\\", "/").lower()
    base = low.rsplit("/", 1)[-1]
    return ("/tests/" in low or low.startswith("tests/")
            or base.startswith("test_") or "/test_" in low
            or base.endswith((".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")))


def findings(path: str, blob: bytes):
    """[(pattern name, line, blocking)] for each hit. The VALUE is never returned."""
    out = []
    lines = blob.split(b"\n")

    def allowed(line_no: int) -> bool:
        if 1 <= line_no <= len(lines):
            return bool(ALLOW.search(lines[line_no - 1].decode("utf-8", "replace")))
        return False

    for name, rx in HIGH:
        for m in rx.finditer(blob):
            if name.startswith("connection string") and CONN_PLACEHOLDER_PW.search(m.group(0)):
                continue    # user:password@host in a doc or template, not a credential
            ln = blob[:m.start()].count(b"\n") + 1
            if not allowed(ln):
                out.append((name, ln, True))

    fixture = is_fixture(path)
    for m in ASSIGNED.finditer(blob):
        var, val = m.group(1), m.group(3)
        if PLACEHOLDER.search(val):
            continue
        # A value containing a space is prose, not a credential:
        #     newErrors.password = "Password is required"
        # Passwords with spaces exist but are vanishingly rare next to the
        # number of validation messages this would otherwise flag.
        if b" " in val:
            continue
        # An enum member whose value restates its own name:
        #     PASSWORD_RESET = "auth.password_reset"
        # Compared ignoring case, separators and any dotted namespace prefix.
        norm = lambda b: re.sub(rb"[^a-z0-9]", b"", b.lower())
        if norm(val).endswith(norm(var)):
            continue
        ln = blob[:m.start()].count(b"\n") + 1
        if allowed(ln):
            continue
        out.append((f"assigned {m.group(1).decode().lower()}", ln, not fixture))

    if path.lower().endswith((".csv", ".tsv")) and lines and CRED_COLUMN.search(lines[0]):
        out.append(("credential column in a data file", 1, True))
    return out


def _git_blob(ref: str) -> bytes:
    return subprocess.run(["git", "show", ref], capture_output=True).stdout


def staged():
    names = subprocess.run(["git", "diff", "--cached", "--name-only",
                            "--diff-filter=ACMR"],
                           capture_output=True, text=True).stdout.split("\n")
    for p in filter(None, names):
        if interesting(p):
            blob = _git_blob(f":{p}")
            if NUL not in blob[:4096]:
                yield p, blob


def worktree():
    """Files on disk. `--tree` reads HEAD and cannot see uncommitted work."""
    names = subprocess.run(["git", "ls-files", "--cached", "--others",
                            "--exclude-standard"],
                           capture_output=True, text=True).stdout.split("\n")
    for p in filter(None, names):
        if not interesting(p):
            continue
        try:
            with open(p, "rb") as fh:
                blob = fh.read()
        except OSError:
            continue
        if NUL not in blob[:4096]:
            yield p, blob


def tree():
    names = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD"],
                           capture_output=True, text=True).stdout.split("\n")
    for p in filter(None, names):
        if interesting(p):
            blob = _git_blob(f"HEAD:{p}")
            if NUL not in blob[:4096]:
                yield p, blob


def history():
    objs = subprocess.run(["git", "rev-list", "--objects", "--all"],
                          capture_output=True).stdout.split(b"\n")
    for line in objs:
        if b" " not in line:
            continue
        sha, _, raw = line.partition(b" ")
        p = raw.decode("utf-8", "replace")
        if not interesting(p):
            continue
        blob = subprocess.run(["git", "cat-file", "blob", sha.decode()],
                              capture_output=True).stdout
        if NUL not in blob[:4096]:
            yield p, blob


def main() -> int:
    mode = "staged"
    for flag in ("worktree", "tree", "history"):
        if f"--{flag}" in sys.argv:
            mode = flag
            break
    source = {"staged": staged, "worktree": worktree,
              "tree": tree, "history": history}[mode]

    blocking, warning, scanned = {}, {}, 0
    for path, blob in source():
        scanned += 1
        for name, ln, blocks in findings(path, blob):
            (blocking if blocks else warning).setdefault(path, set()).add((name, ln))

    def safe(t: str) -> str:
        return t.encode("ascii", "backslashreplace").decode()

    def report(title, d):
        print(title)
        for path in sorted(d):
            print(f"  {safe(path)}")
            for name, ln in sorted(d[path], key=lambda x: x[1]):
                print(f"      line {ln}: {name}")
        print()

    if warning:
        print(f"\nscan_secrets: {len(warning)} test/fixture file(s) carry "
              f"credential-shaped values. Not blocking.\n")
        report("-- fixtures (reported, allowed) --", warning)

    if not blocking:
        print(f"scan_secrets: {scanned} file(s) scanned ({mode}), nothing blocking.")
        return 0

    print(f"scan_secrets: REFUSING -- credential-shaped content in "
          f"{len(blocking)} file(s). Values are deliberately not shown.\n")
    report("== blocking ==", blocking)
    print("If one of these is genuinely not a secret, put")
    print("    # pragma: allowlist-secret")
    print("on that line. Do not work around it by rewording the value.")
    print("If a real credential reached a commit, ROTATE IT -- removing the")
    print("file does not un-publish it.\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
