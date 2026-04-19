"""The Proposer: turns a SchemaSnapshot into a validated ProposalSet.

Loads the versioned system prompt from disk, renders the snapshot,
calls the Anthropic API, and parses the JSON response. No retries,
no fallbacks; callers handle failure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from src.core.config import get_settings
from src.ingestion.types import SchemaSnapshot
from src.semantic.proposals import ProposalSet
from src.semantic.renderer import render_snapshot_for_prompt


# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------

PROMPT_VERSION = "v0"
"""Bumped when the system prompt changes materially. Stored alongside
every proposal in the app database for audit (ADR 0003, ADR 0005)."""

DEFAULT_MODEL = "claude-sonnet-4-5"
"""Development default. Overridden by ANTHROPIC_MODEL env var."""

MAX_OUTPUT_TOKENS = 8192
"""Enough for a full ProposalSet on a realistic warehouse. Raise only
if we see empty tail arrays that look truncated."""

SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parent / "prompts" / "system.md"
)


# ----------------------------------------------------------------------
# Client protocol — lets us inject a fake client in tests.
# ----------------------------------------------------------------------

class AnthropicClientProtocol(Protocol):
    """Minimal subset of the Anthropic SDK client we actually use.

    The real SDK satisfies this automatically. Tests provide a fake
    that returns pre-canned responses without hitting the network.
    """

    def messages_create(self, **kwargs: Any) -> Any:
        ...


class _RealClient:
    """Thin wrapper around the real Anthropic SDK that matches our Protocol."""

    def __init__(self, api_key: str) -> None:
        # Import here so tests that don't need the SDK can skip it.
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)

    def messages_create(self, **kwargs: Any) -> Any:
        return self._client.messages.create(**kwargs)


# ----------------------------------------------------------------------
# The Proposer
# ----------------------------------------------------------------------

class ProposerError(Exception):
    """Raised when the LLM response cannot be parsed or validated."""


class Proposer:
    """Produces ProposalSets from SchemaSnapshots by calling the LLM."""

    def __init__(
        self,
        client: AnthropicClientProtocol | None = None,
        model: str | None = None,
    ) -> None:
        settings = get_settings()
        self._model = model or DEFAULT_MODEL
        self._system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

        if client is not None:
            self._client = client
        else:
            if not settings.anthropic_api_key:
                raise ProposerError(
                    "ANTHROPIC_API_KEY is not set. "
                    "Add it to .env or pass a client explicitly."
                )
            self._client = _RealClient(settings.anthropic_api_key)

    @property
    def model(self) -> str:
        return self._model

    @property
    def prompt_version(self) -> str:
        return PROMPT_VERSION

    def propose(self, snapshot: SchemaSnapshot) -> ProposalSet:
        """Run the full pipeline: render → call → parse → validate."""
        rendered = render_snapshot_for_prompt(snapshot)

        response = self._client.messages_create(
            model=self._model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": self._system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {"role": "user", "content": rendered},
            ],
        )

        text = _extract_text(response)
        cleaned = _strip_json_wrappers(text)
        try:
            return ProposalSet.model_validate_json(cleaned)
        except Exception as exc:
            raise ProposerError(
                f"Could not parse or validate LLM response: {exc}\n\n"
                f"Raw response (first 500 chars):\n{text[:500]}"
            ) from exc


# ----------------------------------------------------------------------
# Response extraction helpers
# ----------------------------------------------------------------------

def _extract_text(response: Any) -> str:
    """Pull the single text block out of an Anthropic response.

    The SDK returns a Message with a list of content blocks. For our
    use case we expect exactly one text block containing the JSON.
    """
    content = getattr(response, "content", None)
    if not content:
        raise ProposerError(f"LLM response has no content: {response!r}")

    for block in content:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            text = getattr(block, "text", None)
            if text is None:
                raise ProposerError("LLM text block missing 'text' field")
            return text

    raise ProposerError(f"LLM response has no text block: {content!r}")


def _strip_json_wrappers(text: str) -> str:
    """Remove common LLM packaging around JSON responses.

    Handles:
    - Leading/trailing whitespace
    - Markdown code fences: ```json ... ``` or ``` ... ```
    - Explanatory prose before or after the JSON object

    Strategy: find the first '{' and last '}'; take everything between.
    This is forgiving because the JSON body itself is validated strictly
    by Pydantic afterwards. If the slice isn't valid JSON, Pydantic fails
    with a clear error anyway.
    """
    stripped = text.strip()

    # Fast path: already clean JSON.
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    # Locate the JSON object by its outermost braces. Works regardless
    # of whether wrappers are code fences, prose, or both.
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        # Nothing JSON-like in here. Let Pydantic produce the error.
        return stripped
    return stripped[start : end + 1]
