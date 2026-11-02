"""One-time restore page for a fresh database.

Disabled (404) unless the RESTORE_TOKEN environment variable is set, and it only
ever runs while the database has NO users. Set the token, restore, then delete the
token again. Nothing is stored; the token is never logged.
"""
from __future__ import annotations

import hmac
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from app.database import engine
from app.services.db_restore import restore_into

router = APIRouter(prefix="/restore", tags=["restore"], include_in_schema=False)

_PAGE = """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">
<body style="font-family:system-ui;max-width:28rem;margin:2rem auto;padding:0 1rem">
<h2>Restore backup</h2>
<p>Only works on an empty database. Remove RESTORE_TOKEN afterwards.</p>
<form method=post enctype=multipart/form-data>
<p><input name=token type=password placeholder="Restore token" required style="width:100%;padding:.6rem"></p>
<p><input name=file type=file accept=".gz" required></p>
<p><button style="padding:.7rem 1.2rem;font-size:1rem">Restore</button></p></form></body>"""


def _enabled() -> str:
    tok = os.environ.get("RESTORE_TOKEN", "")
    if len(tok) < 12:
        raise HTTPException(status_code=404, detail="Not found")
    return tok


@router.get("", response_class=HTMLResponse)
async def page():
    _enabled()
    return _PAGE


@router.post("", response_class=HTMLResponse)
async def run(token: str = Form(...), file: UploadFile = File(...)):
    expected = _enabled()
    if not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Wrong token.")
    with tempfile.NamedTemporaryFile(suffix=".gz", delete=False) as tmp:
        while chunk := await file.read(1024 * 1024):
            tmp.write(chunk)
        name = tmp.name
    try:
        written = await restore_into(engine, Path(name))
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=409, detail=str(e))
    finally:
        os.unlink(name)
    total = sum(written.values())
    return f"<body style='font-family:system-ui;padding:1rem'><h2>Restored {total:,} rows into {len(written)} tables.</h2><p>Now delete RESTORE_TOKEN in Render, then log in.</p></body>"
