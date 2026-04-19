"""Renders a SchemaSnapshot into the Markdown form the LLM consumes.

Kept separate from the Proposer so:
- We can test rendering independently (pure function, no network)
- We can tweak the rendered format without touching LLM-call logic
- We can expose "this is what the AI analyzed" in the UI if needed
"""

from __future__ import annotations

from src.ingestion.types import ColumnSchema, SchemaSnapshot, TableSchema


def render_snapshot_for_prompt(snapshot: SchemaSnapshot) -> str:
    """Produce the Markdown representation of a snapshot for the LLM.

    Structure:
    - Heading with database name
    - One section per table: qualified name, PK, row count, sample note
    - A table of columns per table: name, type, nullable, distinct count, samples
    """
    lines: list[str] = []

    lines.append(f"# Schema snapshot: `{snapshot.source_database}`")
    lines.append("")
    lines.append(f"Tables: {len(snapshot.tables)}")
    lines.append("")

    if not snapshot.tables:
        lines.append("_(No tables found in this snapshot.)_")
        return "\n".join(lines)

    for table in snapshot.tables:
        lines.extend(_render_table(table))
        lines.append("")

    return "\n".join(lines)


def _render_table(table: TableSchema) -> list[str]:
    lines: list[str] = []
    lines.append(f"## Table: `{table.ref.qualified}`")
    lines.append("")

    if table.comment:
        lines.append(f"_Table comment: {table.comment}_")
        lines.append("")

    pk = ", ".join(f"`{c}`" for c in table.primary_key_columns) if table.primary_key_columns else "_(none detected)_"
    lines.append(f"- **Primary key:** {pk}")

    if table.row_count_estimate is not None:
        lines.append(f"- **Row count (estimate):** ~{table.row_count_estimate:,}")
    else:
        lines.append("- **Row count (estimate):** _unknown (table not yet analyzed)_")

    lines.append(
        f"- **Sample:** {table.sample_rows_returned} rows"
        f"{' (truncated, more rows exist)' if table.sample_truncated else ''}"
    )
    lines.append("")

    lines.append("### Columns")
    lines.append("")
    lines.append("| # | Name | Normalized type | Native type | Nullable | Distinct (in sample) | Sample values |")
    lines.append("|---|------|-----------------|-------------|----------|----------------------|---------------|")

    for col in table.columns:
        lines.append(_render_column_row(col))

    return lines


def _render_column_row(col: ColumnSchema) -> str:
    nullable = "yes" if col.is_nullable else "no"
    samples = _format_sample_values(col.sample_values)
    return (
        f"| {col.ordinal_position} "
        f"| `{col.name}` "
        f"| `{col.datum_type.value}` "
        f"| `{col.native_type}` "
        f"| {nullable} "
        f"| {col.distinct_sample_count} "
        f"| {samples} |"
    )


def _format_sample_values(values: tuple, limit: int = 5) -> str:
    """Format sample values as a short, reader-friendly list.

    Truncates to `limit` values and tags long strings so the rendered
    prompt stays readable even for wide columns.
    """
    if not values:
        return "_(none)_"

    shown = values[:limit]
    formatted = []
    for v in shown:
        if v is None:
            formatted.append("NULL")
        else:
            s = repr(v)
            if len(s) > 60:
                s = s[:57] + "…'"
            formatted.append(s)
    suffix = "" if len(values) <= limit else f", …(+{len(values) - limit} more)"
    return ", ".join(formatted) + suffix
