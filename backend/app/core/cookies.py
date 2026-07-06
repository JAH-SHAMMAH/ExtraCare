"""
Cookie-auth helpers (Priority 2).

Centralises the httpOnly access/refresh cookie + the readable CSRF token so the
auth router and the logout endpoint stay consistent. All settings (Secure,
SameSite, domain, lifetimes) come from config — no hard-coded flags.

Cookie layout:
  • access_token  — httpOnly, path "/",                lifetime = access TTL.
  • refresh_token — httpOnly, path "/api/v1/auth",     lifetime = refresh TTL.
      Restricting the refresh cookie to the auth path means it is only ever
      sent to /auth/refresh (and /auth/logout), shrinking its exposure.
  • csrf_token    — NOT httpOnly (the SPA reads it and echoes it back in the
      X-CSRF-Token header → double-submit), path "/".
"""

from fastapi import Response

from app.config import get_settings
from app.core.security import generate_secure_token

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
REFRESH_PATH = "/api/v1/auth"


def issue_csrf_token() -> str:
    return generate_secure_token(32)


def set_auth_cookies(response: Response, access_token: str, refresh_token: str, csrf_token: str) -> None:
    s = get_settings()
    domain = s.COOKIE_DOMAIN or None
    response.set_cookie(
        ACCESS_COOKIE, access_token, httponly=True, secure=s.COOKIE_SECURE,
        samesite=s.COOKIE_SAMESITE, domain=domain, path="/",
        max_age=s.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh_token, httponly=True, secure=s.COOKIE_SECURE,
        samesite=s.COOKIE_SAMESITE, domain=domain, path=REFRESH_PATH,
        max_age=s.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )
    response.set_cookie(
        CSRF_COOKIE, csrf_token, httponly=False, secure=s.COOKIE_SECURE,
        samesite=s.COOKIE_SAMESITE, domain=domain, path="/",
        max_age=s.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def clear_auth_cookies(response: Response) -> None:
    s = get_settings()
    domain = s.COOKIE_DOMAIN or None
    response.delete_cookie(ACCESS_COOKIE, path="/", domain=domain)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH, domain=domain)
    response.delete_cookie(CSRF_COOKIE, path="/", domain=domain)
