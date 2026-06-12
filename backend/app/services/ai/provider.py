"""
AI provider abstraction.

Mirrors the BillingProvider pattern: a narrow Protocol with a single
Noop implementation that returns deterministic output, swapped at
startup when a real adapter (OpenAI, local model, etc.) is wired in.

The Noop provider is NOT a stub — it's the current production path.
Every module handler already produces a fully-formed, useful response
without calling out to an LLM. The provider exists so that when we DO
want to route a task through an external model, the call site is a
one-line `await provider.generate(prompt)` rather than a scattered
if-branch.
"""

from __future__ import annotations

from typing import Any, Protocol


class AIProvider(Protocol):
    """What every concrete provider must implement. Kept narrow so new
    adapters ship without adding dead interface methods."""

    name: str

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        ...


class NoopAIProvider:
    """Null implementation — returns the prompt verbatim. The module
    handlers don't currently route their templated output through the
    provider, so this is only reached by callers that explicitly opt in
    (e.g. a future free-form `ask` task). Never wire this in production
    once a real adapter exists."""

    name = "noop"

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        return prompt


_provider: AIProvider = NoopAIProvider()


def get_ai_provider() -> AIProvider:
    return _provider


def set_ai_provider(provider: AIProvider) -> None:
    """Used by app startup (and tests) to swap the active provider."""
    global _provider
    _provider = provider
