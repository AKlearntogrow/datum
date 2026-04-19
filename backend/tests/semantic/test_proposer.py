"""Tests for the Proposer class using a fake Anthropic client.

These tests never touch the network. A fake client returns pre-canned
responses so we can verify:

1. The Proposer passes the right system prompt and messages.
2. It parses the fake response correctly.
3. It produces clear errors on bad responses.
4. Prompt caching headers are set correctly.

For integration against the real Claude API, see scripts/smoke_proposer.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from src.connectors.types import TableRef
from src.ingestion.types import ColumnSchema, DatumType, SchemaSnapshot, TableSchema
from src.semantic.proposer import (
    DEFAULT_MODEL,
    PROMPT_VERSION,
    Proposer,
    ProposerError,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "proposals"
    / "messy_warehouse_v0.json"
)


# --------------------------------------------------------------
# Fake client infrastructure
# --------------------------------------------------------------

@dataclass
class _FakeContentBlock:
    type: str
    text: str


@dataclass
class _FakeResponse:
    content: list[_FakeContentBlock]


class _FakeClient:
    """Fake Anthropic client that records calls and returns canned responses."""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.calls: list[dict[str, Any]] = []

    def messages_create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        return _FakeResponse(content=[_FakeContentBlock(type="text", text=self._response_text)])


def _minimal_snapshot() -> SchemaSnapshot:
    col = ColumnSchema(
        name="id",
        datum_type=DatumType.INTEGER,
        native_type="integer",
        is_nullable=False,
        ordinal_position=1,
    )
    tbl = TableSchema(
        ref=TableRef(database="db", schema="public", name="orders"),
        columns=(col,),
        primary_key_columns=("id",),
    )
    return SchemaSnapshot(
        id="test",
        captured_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
        source_database="db",
        tables=(tbl,),
    )


# --------------------------------------------------------------
# Tests
# --------------------------------------------------------------

class TestProposerCall:
    def test_calls_client_with_model_and_system_prompt(self) -> None:
        fake = _FakeClient('{"entities":[],"measures":[],"dimensions":[],"time_dimensions":[],"relationships":[],"data_quality_flags":[]}')
        proposer = Proposer(client=fake)
        proposer.propose(_minimal_snapshot())

        assert len(fake.calls) == 1
        call = fake.calls[0]
        assert call["model"] == DEFAULT_MODEL
        # system is a list with one text block carrying the prompt and cache_control
        assert isinstance(call["system"], list)
        assert call["system"][0]["type"] == "text"
        assert "semantic layer analyst" in call["system"][0]["text"].lower() or "semantic" in call["system"][0]["text"].lower()
        assert call["system"][0].get("cache_control") == {"type": "ephemeral"}

    def test_user_message_contains_rendered_snapshot(self) -> None:
        fake = _FakeClient('{"entities":[],"measures":[],"dimensions":[],"time_dimensions":[],"relationships":[],"data_quality_flags":[]}')
        proposer = Proposer(client=fake)
        proposer.propose(_minimal_snapshot())

        user_content = fake.calls[0]["messages"][0]["content"]
        assert "db.public.orders" in user_content
        assert "`id`" in user_content

    def test_respects_custom_model(self) -> None:
        fake = _FakeClient('{"entities":[],"measures":[],"dimensions":[],"time_dimensions":[],"relationships":[],"data_quality_flags":[]}')
        proposer = Proposer(client=fake, model="claude-opus-4-7")
        proposer.propose(_minimal_snapshot())
        assert fake.calls[0]["model"] == "claude-opus-4-7"

    def test_prompt_version_accessor(self) -> None:
        fake = _FakeClient('{"entities":[],"measures":[],"dimensions":[],"time_dimensions":[],"relationships":[],"data_quality_flags":[]}')
        proposer = Proposer(client=fake)
        assert proposer.prompt_version == PROMPT_VERSION


class TestProposerParsing:
    def test_parses_empty_response(self) -> None:
        fake = _FakeClient('{"entities":[],"measures":[],"dimensions":[],"time_dimensions":[],"relationships":[],"data_quality_flags":[]}')
        proposer = Proposer(client=fake)
        result = proposer.propose(_minimal_snapshot())
        assert result.total_proposals == 0

    def test_parses_real_fixture(self) -> None:
        """Use the captured Claude output as the fake response. End-to-end
        parse test of what the real LLM actually produces."""
        fixture_text = FIXTURE_PATH.read_text(encoding="utf-8")
        fake = _FakeClient(fixture_text)
        proposer = Proposer(client=fake)
        result = proposer.propose(_minimal_snapshot())
        assert result.total_proposals > 0
        assert len(result.entities) >= 1

    def test_strips_markdown_code_fence(self) -> None:
        fenced = '```json\n{"entities":[],"measures":[],"dimensions":[],"time_dimensions":[],"relationships":[],"data_quality_flags":[]}\n```'
        fake = _FakeClient(fenced)
        proposer = Proposer(client=fake)
        # Should succeed — fence stripped before parsing
        result = proposer.propose(_minimal_snapshot())
        assert result.total_proposals == 0

    def test_tolerates_surrounding_prose(self) -> None:
        prose = 'Sure, here is the proposal:\n{"entities":[],"measures":[],"dimensions":[],"time_dimensions":[],"relationships":[],"data_quality_flags":[]}\nHope that helps!'
        fake = _FakeClient(prose)
        proposer = Proposer(client=fake)
        result = proposer.propose(_minimal_snapshot())
        assert result.total_proposals == 0


class TestProposerErrors:
    def test_raises_on_unparseable_response(self) -> None:
        fake = _FakeClient("not json at all")
        proposer = Proposer(client=fake)
        with pytest.raises(ProposerError) as excinfo:
            proposer.propose(_minimal_snapshot())
        # Error message should include the raw text for debugging
        assert "not json" in str(excinfo.value).lower() or "invalid json" in str(excinfo.value).lower()

    def test_raises_on_invalid_schema(self) -> None:
        """Valid JSON but missing required fields should fail validation."""
        bad = '{"entities":[{"name":"x"}],"measures":[],"dimensions":[],"time_dimensions":[],"relationships":[],"data_quality_flags":[]}'
        fake = _FakeClient(bad)
        proposer = Proposer(client=fake)
        with pytest.raises(ProposerError):
            proposer.propose(_minimal_snapshot())
