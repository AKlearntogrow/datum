"""Pydantic models for the semantic layer proposals produced by the LLM.

These models are the contract between the LLM's JSON output and every
downstream consumer — the review UI, the app database, the query layer.

See ADR 0005 for the design. If the shape changes, that ADR changes first.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ----------------------------------------------------------------------
# Enums — every constrained field. If the LLM returns anything else,
# Pydantic raises a clean validation error instead of silently accepting.
# ----------------------------------------------------------------------

class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Aggregation(str, Enum):
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    CUSTOM = "custom"


class CardinalityHint(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class GranularityHint(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class RelationshipType(str, Enum):
    EXACT_MATCH = "exact_match"
    FUZZY_MATCH = "fuzzy_match"
    DERIVED = "derived"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_MANY = "many_to_many"
    UNLINKED_DIMENSION = "unlinked_dimension"


class FormatHint(str, Enum):
    INTEGER = "integer"
    DECIMAL = "decimal"
    PERCENT = "percent"
    CURRENCY_USD = "currency_usd"
    CURRENCY_UNKNOWN = "currency_unknown"
    DURATION_DAYS = "duration_days"


# ----------------------------------------------------------------------
# Shared base — all proposals forbid extra fields so we catch prompt drift.
# ----------------------------------------------------------------------

class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ----------------------------------------------------------------------
# Small reusable shapes
# ----------------------------------------------------------------------

class ColumnRef(_Strict):
    """A reference to one column in one table."""
    table: str = Field(..., description="Fully qualified table name, e.g., 'public.sales_opportunities'")
    column: str


# ----------------------------------------------------------------------
# The six proposal categories
# ----------------------------------------------------------------------

class EntityProposal(_Strict):
    name: str = Field(..., description="snake_case machine identifier")
    display_name: str
    description: str
    source_columns: list[ColumnRef] = Field(..., min_length=1)
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    confidence: Confidence


class MeasureProposal(_Strict):
    name: str
    display_name: str
    description: str
    aggregation: Aggregation
    sql_expression: str
    source_tables: list[str] = Field(..., min_length=1)
    filter_expression: str | None = None
    format_hint: FormatHint | None = None
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    confidence: Confidence
    caveats: list[str] = Field(default_factory=list)


class DimensionProposal(_Strict):
    name: str
    display_name: str
    description: str
    source_column: ColumnRef
    cardinality_hint: CardinalityHint
    sample_values: list[str] = Field(default_factory=list, max_length=10)
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    confidence: Confidence


class TimeDimensionProposal(_Strict):
    name: str
    display_name: str
    description: str
    source_column: ColumnRef
    granularity_hint: GranularityHint
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    confidence: Confidence


class RelationshipProposal(_Strict):
    """A relationship between two tables, or a flagged dangling dimension.

    For `unlinked_dimension`, `to_table` and `to_column` are null:
    the point is that there is no target. For every other relationship
    type, both sides must be populated.
    """

    name: str
    display_name: str
    description: str
    from_table: str
    from_column: str
    to_table: str | None = None
    to_column: str | None = None
    relationship_type: RelationshipType
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    confidence: Confidence

    @model_validator(mode="after")
    def _validate_target_sides(self) -> RelationshipProposal:
        """Enforce the two real-world cases:
        - unlinked_dimension: to_table and to_column MUST be null
        - every other type: to_table and to_column MUST both be populated
        """
        both_none = self.to_table is None and self.to_column is None
        both_set = self.to_table is not None and self.to_column is not None

        if not (both_none or both_set):
            raise ValueError(
                "to_table and to_column must both be set or both be null"
            )

        if self.relationship_type == RelationshipType.UNLINKED_DIMENSION:
            if not both_none:
                raise ValueError(
                    "unlinked_dimension relationships must have null to_table and to_column"
                )
        else:
            if not both_set:
                raise ValueError(
                    f"relationship_type '{self.relationship_type.value}' requires to_table and to_column"
                )

        return self


class DataQualityFlag(_Strict):
    severity: Severity
    title: str
    description: str
    affected_columns: list[ColumnRef] = Field(..., min_length=1)
    rationale: str
    evidence: list[str] = Field(default_factory=list)


# ----------------------------------------------------------------------
# The top-level container — what the LLM returns per snapshot.
# ----------------------------------------------------------------------

class ProposalSet(_Strict):
    """The full JSON response from one LLM run against one SchemaSnapshot."""

    entities: list[EntityProposal] = Field(default_factory=list)
    measures: list[MeasureProposal] = Field(default_factory=list)
    dimensions: list[DimensionProposal] = Field(default_factory=list)
    time_dimensions: list[TimeDimensionProposal] = Field(default_factory=list)
    relationships: list[RelationshipProposal] = Field(default_factory=list)
    data_quality_flags: list[DataQualityFlag] = Field(default_factory=list)

    @property
    def total_proposals(self) -> int:
        """Quick count for logging and UI summaries."""
        return (
            len(self.entities)
            + len(self.measures)
            + len(self.dimensions)
            + len(self.time_dimensions)
            + len(self.relationships)
            + len(self.data_quality_flags)
        )
