"""Bulk-create teacher accounts: email from the name, a temporary password the
teacher MUST change at first sign-in, the Teacher role, and the section their
department names.

Pure helpers here (`email_for`, `temp_password`); the endpoint in
`routers/modules/school.py` does the database work.
"""
from __future__ import annotations

import re
import secrets
import unicodedata

# No 0/O/1/l/I: the password is read off a phone screen and typed by someone else.
_PW_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
_DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


def temp_password(length: int = 10) -> str:
    """Random, unambiguous, with at least one upper, lower and digit."""
    while True:
        pw = "".join(secrets.choice(_PW_ALPHABET) for _ in range(length))
        if (any(c.isupper() for c in pw) and any(c.islower() for c in pw)
                and any(c.isdigit() for c in pw)):
            return pw


def email_local_part(first_name: str) -> str:
    """'Chiamaka' -> 'chiamaka'; accents and punctuation dropped."""
    ascii_name = unicodedata.normalize("NFKD", first_name or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_name.lower())


def valid_domain(domain: str) -> bool:
    return bool(_DOMAIN_RE.match((domain or "").strip().lower()))


def email_for(first_name: str, domain: str) -> str | None:
    local = email_local_part(first_name)
    return f"{local}@{domain.strip().lower()}" if local else None
