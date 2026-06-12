"""
Pure-function coverage of CBT live-window enforcement. `_is_live` is the
single predicate that gates `start_attempt` — a bug here either lets students
start closed exams or blocks them during the scheduled window.
"""

from datetime import datetime, timezone, timedelta

import pytest

from app.routers.modules.cbt import _is_live
from app.models.modules.school import CBTExam, ExamStatus


NOW = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)


def _exam(**kw) -> CBTExam:
    defaults = dict(
        title="T",
        status=ExamStatus.PUBLISHED,
        start_time=NOW - timedelta(hours=1),
        end_time=NOW + timedelta(hours=1),
        duration_minutes=60,
        created_by="u",
        org_id="o",
    )
    defaults.update(kw)
    return CBTExam(**defaults)


def test_published_during_window_is_live():
    assert _is_live(_exam(), NOW) is True


def test_active_during_window_is_live():
    assert _is_live(_exam(status=ExamStatus.ACTIVE), NOW) is True


def test_draft_never_live():
    assert _is_live(_exam(status=ExamStatus.DRAFT), NOW) is False


def test_closed_never_live():
    assert _is_live(_exam(status=ExamStatus.CLOSED), NOW) is False


def test_before_start_is_not_live():
    e = _exam(start_time=NOW + timedelta(minutes=5))
    assert _is_live(e, NOW) is False


def test_after_end_is_not_live():
    e = _exam(end_time=NOW - timedelta(minutes=5))
    assert _is_live(e, NOW) is False


def test_no_start_no_end_is_live_when_published():
    """Exams without a scheduled window rely on status alone."""
    e = _exam(start_time=None, end_time=None)
    assert _is_live(e, NOW) is True


def test_only_start_set_before_is_not_live():
    e = _exam(start_time=NOW + timedelta(minutes=1), end_time=None)
    assert _is_live(e, NOW) is False


def test_only_end_set_after_is_not_live():
    e = _exam(start_time=None, end_time=NOW - timedelta(minutes=1))
    assert _is_live(e, NOW) is False


@pytest.mark.parametrize("delta_secs", [-1, 0, 1])
def test_boundary_at_start(delta_secs):
    """At exactly start_time the exam is live (>= boundary handled inclusively)."""
    e = _exam(start_time=NOW + timedelta(seconds=delta_secs))
    expected = delta_secs <= 0
    assert _is_live(e, NOW) is expected
