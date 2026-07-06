"""
SMS coverage — recipient phone normalisation (who actually gets messaged).

The SMS send path's RBAC (admin-only), per-org rate limiting, and audit-row
writing are exercised by test_rate_limit.py + test_audit_coverage.py + the
full-suite import. Here we lock the E.164 normaliser, which decides which
contacts are messageable and guards against sending to junk numbers.
"""

from app.services.sms import normalise_phone_e164


def test_none_and_empty_return_none():
    assert normalise_phone_e164(None) is None
    assert normalise_phone_e164("") is None


def test_junk_and_too_short_return_none():
    assert normalise_phone_e164("not-a-number") is None
    assert normalise_phone_e164("123") is None


def test_nigerian_local_trunk_becomes_e164():
    assert normalise_phone_e164("08031234567") == "+2348031234567"
    # punctuation/spacing is stripped before normalising
    assert normalise_phone_e164("0803 123 4567") == "+2348031234567"


def test_already_e164_is_preserved():
    assert normalise_phone_e164("+2348031234567") == "+2348031234567"


def test_double_zero_international_prefix():
    assert normalise_phone_e164("002348031234567") == "+2348031234567"
