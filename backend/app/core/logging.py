"""
Logging configuration.

Two formats:
  - `pretty`  → human-readable single line, default for dev.
  - `json`    → one JSON object per line, default for staging/prod. The keys
                match what log shippers (CloudWatch, Loki, Datadog) expect out
                of the box so no parsing rules are needed downstream.

Structured events emitted via `core.events.log_event` already attach their
fields to LogRecord.extra; the JSON formatter lifts them to top-level keys
so `event=cbt_attempt_rejected` queries work without a regex step.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


# Attributes attached to every LogRecord by Python's logging module.
# Anything NOT in this set is treated as user-supplied `extra` and promoted
# to a top-level key in the JSON output.
_STD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "asctime", "taskName",
}


class JSONFormatter(logging.Formatter):
    """Emit one JSON object per log line, safe for log shippers."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        # Promote extras (event=..., org_id=..., etc.) to top-level fields.
        for key, value in record.__dict__.items():
            if key in _STD_ATTRS or key.startswith("_"):
                continue
            payload[key] = _safe(value)

        return json.dumps(payload, default=str, separators=(",", ":"))


def _safe(value: Any) -> Any:
    """Coerce non-JSON-native values so a single bad extra doesn't drop the line."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple, dict)):
        return value
    return str(value)


def configure_logging(level: str = "INFO", fmt: str = "pretty") -> None:
    """Idempotent root-logger setup. Call once at app startup."""
    root = logging.getLogger()
    # Strip any handlers installed by libraries / prior calls so repeat calls
    # in tests or reloads don't stack up duplicate output.
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
            datefmt="%H:%M:%S",
        ))

    root.addHandler(handler)
    root.setLevel(level.upper())

    # Uvicorn access logs are noisy; keep them at INFO but let users turn them
    # down via LOG_LEVEL if they bump the root level.
    logging.getLogger("uvicorn.access").setLevel(level.upper())
