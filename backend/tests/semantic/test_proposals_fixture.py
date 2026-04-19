"""Verify the saved Claude proposal fixture parses through our Pydantic models.

Every time someone tweaks the proposal schema (adding/removing a field,
tightening an enum, etc.), this test ensures the change is compatible
with a real, previously-validated LLM response. If this breaks, either:

1. The schema change is backward-incompatible — either fix the schema
   or regenerate the fixture against the new prompt/schema.
2. The fixture is stale — regenerate intentionally.

No API cost, no network — pure parse test against a captured artifact.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.semantic.proposals import ProposalSet

FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "proposals"
    / "messy_warehouse_v0.json"
)


@pytest.fixture(scope="module")
def proposal_set() -> ProposalSet:
    """Load the fixture once for the whole module."""
    assert FIXTURE_PATH.exists(), f"Missing fixture: {FIXTURE_PATH}"
    text = FIXTURE_PATH.read_text(encoding="utf-8")
    return ProposalSet.model_validate_json(text)


class TestFixtureLoads:
    def test_fixture_parses(self, proposal_set: ProposalSet) -> None:
        assert isinstance(proposal_set, ProposalSet)

    def test_has_all_six_categories(self, proposal_set: ProposalSet) -> None:
        # Each should be a list, even if empty. At least some must be non-empty
        # because we know this fixture came from a rich demo warehouse.
        assert isinstance(proposal_set.entities, list)
        assert isinstance(proposal_set.measures, list)
        assert isinstance(proposal_set.dimensions, list)
        assert isinstance(proposal_set.time_dimensions, list)
        assert isinstance(proposal_set.relationships, list)
        assert isinstance(proposal_set.data_quality_flags, list)
        assert proposal_set.total_proposals > 0


class TestFixtureShapeExpectations:
    """Sanity checks reflecting what our demo data *should* produce.

    These aren't brittle exact-count assertions; they encode the minimum
    signal we expect the LLM to surface on the synthetic warehouse.
    If any of these regress, either the prompt quality degraded or
    we regenerated the fixture against a weaker prompt.
    """

    def test_at_least_one_customer_entity_span(self, proposal_set: ProposalSet) -> None:
        """At least one entity should span 2+ source columns — that's the
        core demo moment (cross-table customer linkage)."""
        multi_source = [e for e in proposal_set.entities if len(e.source_columns) >= 2]
        assert multi_source, (
            "Expected at least one multi-table entity proposal. "
            "If the fixture is correct, maybe the prompt stopped surfacing cross-table entities."
        )

    def test_multiple_measures_exist(self, proposal_set: ProposalSet) -> None:
        assert len(proposal_set.measures) >= 3

    def test_time_dimensions_detected(self, proposal_set: ProposalSet) -> None:
        """Our warehouse has 6 date/timestamp columns. Expect Claude to find
        at least half of them."""
        assert len(proposal_set.time_dimensions) >= 3

    def test_at_least_one_data_quality_flag(self, proposal_set: ProposalSet) -> None:
        """If the LLM finds zero data quality issues in our deliberately-messy
        warehouse, something is very wrong with the prompt."""
        assert len(proposal_set.data_quality_flags) >= 1


class TestFixtureFieldIntegrity:
    def test_all_entities_have_required_fields(self, proposal_set: ProposalSet) -> None:
        for e in proposal_set.entities:
            assert e.name
            assert e.display_name
            assert e.description
            assert e.source_columns
            assert e.rationale
            assert e.confidence

    def test_all_measures_have_aggregation(self, proposal_set: ProposalSet) -> None:
        for m in proposal_set.measures:
            assert m.aggregation is not None
            assert m.sql_expression
            assert m.source_tables

    def test_all_relationships_have_consistent_target_sides(self, proposal_set: ProposalSet) -> None:
        """Our validator should have rejected any inconsistent relationship
        at parse time. This test just confirms the rule held across the fixture."""
        for r in proposal_set.relationships:
            both_none = r.to_table is None and r.to_column is None
            both_set = r.to_table is not None and r.to_column is not None
            assert both_none or both_set, (
                f"relationship {r.name} has inconsistent to_table/to_column: "
                f"{r.to_table!r} / {r.to_column!r}"
            )
