"use client";

import { useState } from "react";
import type { SchemaInfo } from "@/lib/api";

export type SchemaSelection = {
  included_schemas: string[];
  excluded_tables: string[] | null;
};

type Props = {
  schemas: SchemaInfo[];
  selection: SchemaSelection;
  onChange: (next: SchemaSelection) => void;
  disabled?: boolean;
};

export function SchemaPicker({ schemas, selection, onChange, disabled }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  if (schemas.length === 0) {
    return (
      <div className="text-neutral-500 text-sm border border-neutral-800 rounded px-4 py-6 text-center">
        No schemas found in this data source.
      </div>
    );
  }

  function toggleExpand(schemaName: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(schemaName)) {
        next.delete(schemaName);
      } else {
        next.add(schemaName);
        // First expansion transitions excluded_tables from null to []
        if (selection.excluded_tables === null) {
          onChange({ ...selection, excluded_tables: [] });
        }
      }
      return next;
    });
  }

  function toggleSchema(schemaName: string) {
    const included = selection.included_schemas.includes(schemaName);
    const nextIncluded = included
      ? selection.included_schemas.filter((s) => s !== schemaName)
      : [...selection.included_schemas, schemaName];
    // Don't clear excluded_tables when unchecking — preserves user intent
    onChange({ ...selection, included_schemas: nextIncluded });
  }

  function toggleTable(qualifiedTable: string) {
    const currentExcluded = selection.excluded_tables ?? [];
    const isExcluded = currentExcluded.includes(qualifiedTable);
    const nextExcluded = isExcluded
      ? currentExcluded.filter((t) => t !== qualifiedTable)
      : [...currentExcluded, qualifiedTable];
    onChange({ ...selection, excluded_tables: nextExcluded });
  }

  return (
    <div className="border border-neutral-800 rounded-lg overflow-hidden">
      {schemas.map((schema) => {
        const isIncluded = selection.included_schemas.includes(schema.schema_name);
        const isExpanded = expanded.has(schema.schema_name);
        const currentExcluded = selection.excluded_tables ?? [];

        return (
          <div key={schema.schema_name} className="border-b border-neutral-800 last:border-b-0">
            <div className="flex items-center gap-3 px-4 py-3">
              <input
                type="checkbox"
                checked={isIncluded}
                onChange={() => toggleSchema(schema.schema_name)}
                disabled={disabled}
                className="accent-blue-500 shrink-0"
              />
              <button
                type="button"
                onClick={() => toggleExpand(schema.schema_name)}
                disabled={disabled}
                className="text-neutral-500 hover:text-neutral-300 text-sm shrink-0 w-4 text-center"
              >
                {isExpanded ? "▾" : "▸"}
              </button>
              <span className="font-mono text-sm text-neutral-200">{schema.schema_name}</span>
              <span className="text-xs text-neutral-600">
                {schema.tables.length} table{schema.tables.length !== 1 ? "s" : ""}
              </span>
            </div>

            {isExpanded && (
              <div className="bg-neutral-900/50 border-t border-neutral-800">
                {schema.tables.map((table) => {
                  const qualified = `${schema.schema_name}.${table}`;
                  const isExcluded = currentExcluded.includes(qualified);
                  const tableDisabled = disabled || !isIncluded;

                  return (
                    <div
                      key={qualified}
                      className="flex items-center gap-3 pl-12 pr-4 py-2"
                    >
                      <input
                        type="checkbox"
                        checked={!isExcluded}
                        onChange={() => toggleTable(qualified)}
                        disabled={tableDisabled}
                        className="accent-blue-500 shrink-0"
                      />
                      <span
                        className={
                          "font-mono text-xs " +
                          (tableDisabled ? "text-neutral-600" : "text-neutral-300")
                        }
                      >
                        {table}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
