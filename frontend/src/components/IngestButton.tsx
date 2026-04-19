"use client";

import { useState } from "react";
import { api } from "@/lib/api";

// v0 hardcodes the messy_warehouse URL. Real UI will collect this from a form.
const DEFAULT_WAREHOUSE_URL =
  "postgresql://datum:datum_dev_password@localhost:5432/messy_warehouse";

type Props = {
  onCompleted: () => void;
};

export function IngestButton({ onCompleted }: Props) {
  const [running, setRunning] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setRunning(true);
    setError(null);
    setSummary(null);
    try {
      const res = await api.runIngest(DEFAULT_WAREHOUSE_URL);
      if (res.skipped) {
        const when = res.last_snapshot_captured_at
          ? new Date(res.last_snapshot_captured_at).toLocaleString()
          : "unknown time";
        setSummary(
          `No changes detected since the last ingestion on ${when}. Nothing new to propose.`
        );
      } else {
        setSummary(
          `Ingested ${res.tables_ingested} tables (${res.columns_ingested} columns); ` +
            `proposed ${res.entities_proposed} entities, ${res.measures_proposed} measures, ` +
            `${res.dimensions_proposed} dimensions, ${res.time_dimensions_proposed} time dimensions, ` +
            `${res.relationships_proposed} relationships, ${res.data_quality_flags_proposed} flags. ` +
            `${res.entities_persisted} entities persisted.`
        );
      }
      onCompleted();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={handleClick}
        disabled={running}
        className="px-4 py-2 rounded bg-blue-700 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium"
      >
        {running ? "Analyzing… (this may take 15-30 seconds)" : "Run ingestion on messy_warehouse"}
      </button>
      {summary && (
        <p className="text-sm text-neutral-400">{summary}</p>
      )}
      {error && (
        <p className="text-sm text-red-400 border border-red-900 bg-red-950/50 rounded px-3 py-2">
          {error}
        </p>
      )}
    </div>
  );
}
