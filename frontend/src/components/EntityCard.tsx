"use client";

import { useState } from "react";
import { api, type Entity } from "@/lib/api";

const CONFIDENCE_STYLES: Record<Entity["confidence"], string> = {
  high: "bg-green-900/40 text-green-300 border border-green-800",
  medium: "bg-amber-900/40 text-amber-300 border border-amber-800",
  low: "bg-neutral-800 text-neutral-300 border border-neutral-700",
};

const STATUS_STYLES: Record<Entity["status"], string> = {
  proposed: "bg-blue-900/30 text-blue-300 border border-blue-800",
  approved: "bg-green-900/50 text-green-200 border border-green-700",
  rejected: "bg-red-900/30 text-red-300 border border-red-800",
  superseded: "bg-neutral-800 text-neutral-400 border border-neutral-700",
};

type Props = {
  entity: Entity;
  onChanged: (updated: Entity) => void;
};

export function EntityCard({ entity, onChanged }: Props) {
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isTerminal = entity.status !== "proposed";

  async function handleApprove() {
    setWorking(true);
    setError(null);
    try {
      const updated = await api.approveEntity(entity.id);
      onChanged(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setWorking(false);
    }
  }

  async function handleReject() {
    setWorking(true);
    setError(null);
    try {
      const updated = await api.rejectEntity(entity.id);
      onChanged(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setWorking(false);
    }
  }

  async function handleReopen() {
    setWorking(true);
    setError(null);
    try {
      const updated = await api.reopenEntity(entity.id);
      onChanged(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setWorking(false);
    }
  }

  return (
    <article className="border border-neutral-800 rounded-lg p-6 bg-neutral-950 space-y-4">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-neutral-100">{entity.display_name}</h3>
          <p className="text-xs text-neutral-500 font-mono">{entity.name}</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <span className={`text-xs px-2 py-1 rounded ${CONFIDENCE_STYLES[entity.confidence]}`}>
            {entity.confidence} confidence
          </span>
          <span className={`text-xs px-2 py-1 rounded ${STATUS_STYLES[entity.status]}`}>
            {entity.status}
          </span>
        </div>
      </header>

      <p className="text-sm text-neutral-300">{entity.description}</p>

      <section>
        <h4 className="text-xs uppercase tracking-wide text-neutral-500 mb-1">Source columns</h4>
        <ul className="text-sm font-mono text-neutral-300 space-y-1">
          {entity.source_columns.map((sc) => (
            <li key={sc.snapshot_column_id}>
              <span className="text-neutral-500">{sc.table}</span>
              <span className="text-neutral-600">.</span>
              <span className="text-neutral-200">{sc.column}</span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h4 className="text-xs uppercase tracking-wide text-neutral-500 mb-1">Rationale</h4>
        <p className="text-sm text-neutral-300">{entity.rationale}</p>
      </section>

      {entity.evidence.length > 0 && (
        <section>
          <h4 className="text-xs uppercase tracking-wide text-neutral-500 mb-1">Evidence</h4>
          <ul className="text-xs font-mono text-neutral-400 space-y-1 list-disc list-inside">
            {entity.evidence.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </section>
      )}

      {isTerminal && (
        <footer className="text-xs text-neutral-500 space-y-1">
          {entity.status === "approved" && entity.approved_by && entity.approved_at && (
            <div>Approved by {entity.approved_by} on {new Date(entity.approved_at).toLocaleString()}</div>
          )}
          {entity.status === "rejected" && entity.rejected_by && entity.rejected_at && (
            <div>Rejected by {entity.rejected_by} on {new Date(entity.rejected_at).toLocaleString()}</div>
          )}
          {entity.reopened_at && (
            <div className="text-neutral-600 italic">Previously reviewed; reopened on {new Date(entity.reopened_at).toLocaleString()}</div>
          )}
        </footer>
      )}

      {error && (
        <div className="text-sm text-red-400 border border-red-900 bg-red-950/50 rounded px-3 py-2">
          {error}
        </div>
      )}

      {!isTerminal && (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleApprove}
            disabled={working}
            className="flex-1 px-4 py-2 rounded bg-green-700 hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium"
          >
            {working ? "…" : "Approve"}
          </button>
          <button
            type="button"
            onClick={handleReject}
            disabled={working}
            className="flex-1 px-4 py-2 rounded bg-neutral-800 hover:bg-neutral-700 disabled:opacity-50 disabled:cursor-not-allowed text-neutral-200 font-medium"
          >
            {working ? "…" : "Reject"}
          </button>
        </div>
      )}

      {isTerminal && entity.status !== "superseded" && (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleReopen}
            disabled={working}
            className="flex-1 px-4 py-2 rounded bg-neutral-800 hover:bg-neutral-700 disabled:opacity-50 disabled:cursor-not-allowed text-neutral-200 font-medium border border-neutral-700"
          >
            {working ? "…" : "Reopen for review"}
          </button>
        </div>
      )}
    </article>
  );
}
