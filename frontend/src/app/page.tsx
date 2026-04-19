"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Entity, type EntityStatus } from "@/lib/api";
import { EntityCard } from "@/components/EntityCard";
import { IngestButton } from "@/components/IngestButton";

type LoadState =
  | { kind: "loading" }
  | { kind: "loaded"; entities: Entity[] }
  | { kind: "error"; message: string };

const FILTERS: { label: string; value: EntityStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Proposed", value: "proposed" },
  { label: "Approved", value: "approved" },
  { label: "Rejected", value: "rejected" },
];

export default function Home() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [filter, setFilter] = useState<EntityStatus | "all">("all");

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const statusFilter = filter === "all" ? undefined : filter;
      const list = await api.listEntities(statusFilter);
      setState({ kind: "loaded", entities: list.items });
    } catch (e) {
      setState({
        kind: "error",
        message: e instanceof Error ? e.message : "Unknown error",
      });
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  function handleEntityChanged(updated: Entity) {
    setState((prev) => {
      if (prev.kind !== "loaded") return prev;
      return {
        kind: "loaded",
        entities: prev.entities.map((e) => (e.id === updated.id ? updated : e)),
      };
    });
  }

  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-100 p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <header className="space-y-2">
          <h1 className="text-3xl font-bold">Datum</h1>
          <p className="text-neutral-400">
            AI-assisted semantic layer — entity proposals
          </p>
        </header>

        <section className="space-y-4">
          <IngestButton onCompleted={load} />
        </section>

        <nav className="flex gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              onClick={() => setFilter(f.value)}
              className={
                "px-3 py-1 rounded text-sm font-medium " +
                (filter === f.value
                  ? "bg-neutral-200 text-neutral-900"
                  : "bg-neutral-900 text-neutral-400 border border-neutral-800 hover:border-neutral-700")
              }
            >
              {f.label}
            </button>
          ))}
        </nav>

        <section>
          {state.kind === "loading" && (
            <p className="text-neutral-400">Loading entities…</p>
          )}

          {state.kind === "error" && (
            <div className="text-red-400 border border-red-900 bg-red-950/50 rounded px-4 py-3">
              <p className="font-medium mb-1">Error loading entities</p>
              <p className="text-sm">{state.message}</p>
              <p className="text-xs mt-2 text-neutral-500">
                Is the backend running at {process.env.NEXT_PUBLIC_API_URL}?
              </p>
            </div>
          )}

          {state.kind === "loaded" && state.entities.length === 0 && (
            <div className="text-neutral-500 text-sm border border-neutral-800 rounded px-4 py-6 text-center">
              No entities{filter !== "all" ? ` with status "${filter}"` : ""}. Run ingestion to generate proposals.
            </div>
          )}

          {state.kind === "loaded" && state.entities.length > 0 && (
            <div className="space-y-4">
              {state.entities.map((e) => (
                <EntityCard key={e.id} entity={e} onChanged={handleEntityChanged} />
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
