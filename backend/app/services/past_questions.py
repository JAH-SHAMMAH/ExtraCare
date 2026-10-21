"""JAMB / WAEC / NECO past questions for student practice.

Questions come from an external provider (configured by PAST_QUESTIONS_API_URL and
PAST_QUESTIONS_API_TOKEN — the token lives in the host's environment, never in the
repo) and are cached in the question bank (exam_body/exam_year/external_id) so a
paper is served from our own database whenever it can be, and the provider is only
hit for what we don't have yet.

The past questions remain the intellectual property of JAMB, WAEC and NECO and are
used here for educational practice only.
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.modules.school import QuestionBankItem, QuestionType

logger = logging.getLogger("extracare.past_questions")

# Our key → (label, the provider's `type` value)
BODIES: dict[str, tuple[str, str]] = {
    "jamb": ("JAMB (UTME)", "utme"),
    "waec": ("WAEC (WASSCE)", "wassce"),
    "neco": ("NECO (SSCE)", "neco"),
}

# Used when the provider's live subject list can't be read.
FALLBACK_SUBJECTS: list[tuple[str, str]] = [
    ("english", "English Language"), ("mathematics", "Mathematics"), ("physics", "Physics"),
    ("chemistry", "Chemistry"), ("biology", "Biology"), ("economics", "Economics"),
    ("government", "Government"), ("commerce", "Commerce"), ("accounting", "Accounting"),
    ("englishlit", "Literature in English"), ("geography", "Geography"),
    ("crk", "Christian Religious Studies"), ("irk", "Islamic Studies"),
    ("agriculture", "Agricultural Science"), ("civiceducation", "Civic Education"),
    ("history", "History"),
]
YEARS = list(range(2024, 1999, -1))

_subject_cache: dict = {"at": 0.0, "items": None}


class PastQuestionsUnavailable(Exception):
    """Provider not configured / unreachable. `.status` is the HTTP status to surface."""

    def __init__(self, message: str, status: int = 503):
        super().__init__(message)
        self.message, self.status = message, status


def configured() -> bool:
    return bool((get_settings().PAST_QUESTIONS_API_TOKEN or "").strip())


def _client() -> httpx.AsyncClient:
    s = get_settings()
    return httpx.AsyncClient(
        base_url=s.PAST_QUESTIONS_API_URL.rstrip("/"), timeout=15.0,
        headers={"AccessToken": s.PAST_QUESTIONS_API_TOKEN.strip(), "Accept": "application/json"},
    )


def _humanise(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


def parse_subjects(payload) -> list[tuple[str, str]]:
    """Tolerant of the provider returning a list of strings, a list of
    {slug,name} objects, or a {slug: name} mapping, optionally under `data`."""
    data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
    out: list[tuple[str, str]] = []
    if isinstance(data, dict):
        out = [(str(k), str(v)) for k, v in data.items() if isinstance(v, (str, int))]
    elif isinstance(data, list):
        for it in data:
            if isinstance(it, str):
                out.append((it, _humanise(it)))
            elif isinstance(it, dict):
                slug = it.get("slug") or it.get("subject") or it.get("id") or it.get("name")
                if slug:
                    out.append((str(slug), str(it.get("name") or it.get("title") or _humanise(str(slug)))))
    return out


async def list_subjects() -> list[tuple[str, str]]:
    if _subject_cache["items"] and time.time() - _subject_cache["at"] < 6 * 3600:
        return _subject_cache["items"]
    items: list[tuple[str, str]] = []
    if configured():
        try:
            async with _client() as c:
                r = await c.get("/subjects")
                r.raise_for_status()
                items = parse_subjects(r.json())
        except Exception:  # noqa: BLE001 — fall back to the built-in list
            logger.warning("past_questions.subjects_failed", exc_info=True)
    items = items or FALLBACK_SUBJECTS
    _subject_cache.update(at=time.time(), items=items)
    return items


@dataclass
class Fetched:
    external_id: str
    text: str
    options: list[dict]
    answer: str
    solution: str | None
    year: int | None


def _clean(html: str | None) -> str:
    from app.routers.modules.cbt import _sanitize_html  # same whitelist the Question Bank uses
    return _sanitize_html((html or "").strip())


def parse_questions(payload) -> list[Fetched]:
    data = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(data, dict):
        data = [data]
    out: list[Fetched] = []
    for q in data or []:
        if not isinstance(q, dict):
            continue
        opts_raw = q.get("option") or q.get("options") or {}
        if not isinstance(opts_raw, dict):
            continue
        options = [{"key": str(k).lower(), "text": _clean(str(v))} for k, v in opts_raw.items() if str(v or "").strip()]
        answer = str(q.get("answer") or "").strip().lower()
        text = _clean(q.get("question"))
        section = _clean(q.get("section"))
        if not text or len(options) < 2 or answer not in {o["key"] for o in options}:
            continue
        if section:
            text = f"<p><em>{section}</em></p>{text}"
        year = q.get("examyear")
        out.append(Fetched(
            external_id=str(q.get("id")), text=text, options=options, answer=answer,
            solution=_clean(q.get("solution")) or None,
            year=int(year) if str(year or "").isdigit() else None,
        ))
    return out


async def _cached(db: AsyncSession, org_id: str, body: str, subject: str, year: int | None) -> list[QuestionBankItem]:
    q = select(QuestionBankItem).where(
        QuestionBankItem.org_id == org_id, QuestionBankItem.exam_body == body, QuestionBankItem.topic == subject,
    )
    if year:
        q = q.where(QuestionBankItem.exam_year == year)
    return list((await db.execute(q)).scalars().all())


async def _fetch_remote(body: str, subject: str, year: int | None, limit: int) -> list[Fetched]:
    if not configured():
        raise PastQuestionsUnavailable(
            "Past questions aren't connected yet. Ask your administrator to add the past-questions key.", 503)
    params = {"subject": subject, "type": BODIES[body][1], "limit": limit}
    if year:
        params["year"] = year
    try:
        async with _client() as c:
            r = await c.get("/q", params=params)
    except httpx.HTTPError:
        logger.warning("past_questions.unreachable", exc_info=True)
        raise PastQuestionsUnavailable("Couldn't reach the past-questions service. Try again shortly.", 502)
    if r.status_code in (401, 403):
        raise PastQuestionsUnavailable("The past-questions key was rejected. Tell your administrator.", 503)
    if r.status_code == 429:
        raise PastQuestionsUnavailable("The past-questions service is busy. Try again in a minute.", 503)
    if r.status_code == 404:
        return []
    if r.status_code >= 400:
        logger.warning("past_questions.http_%s %s", r.status_code, r.text[:200])
        raise PastQuestionsUnavailable("Couldn't get past questions right now. Try again shortly.", 502)
    try:
        return parse_questions(r.json())
    except ValueError:
        raise PastQuestionsUnavailable("Couldn't read the past-questions response.", 502)


async def get_paper(
    db: AsyncSession, org_id: str, body: str, subject: str, year: int | None, count: int,
) -> list[QuestionBankItem]:
    """Up to `count` cached questions for the choice, topping up from the provider."""
    have = await _cached(db, org_id, body, subject, year)
    if len(have) < count:
        known = {h.external_id for h in have}
        tries = 0
        try:
            while len(have) < count and tries < 3:
                tries += 1
                new = [f for f in await _fetch_remote(body, subject, year, min(count * 2, 40)) if f.external_id not in known]
                if not new:
                    break
                for f in new:
                    known.add(f.external_id)
                    item = QuestionBankItem(
                        subject_id=None, topic=subject, difficulty="medium", question_text=f.text,
                        question_type=QuestionType.MCQ, options=f.options, correct_answer=f.answer,
                        points=1.0, tags=["past-question"], explanation=f.solution,
                        exam_body=body, exam_year=f.year or year, external_id=f.external_id, org_id=org_id,
                    )
                    db.add(item)
                    have.append(item)
                await db.flush()
        except PastQuestionsUnavailable:
            if not have:  # nothing cached to fall back on
                raise
    if not have:
        return []
    return random.sample(have, min(count, len(have)))
