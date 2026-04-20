"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type DataSource } from "@/lib/api";
import { DataSourceCard } from "@/components/DataSourceCard";

type LoadState =
  | { kind: "loading" }
  | { kind: "loaded"; sources: DataSource[] }
  | { kind: "error"; message: string };

export default function DataSourcesPage() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const list = await api.listDataSources();
      setState({ kind: "loaded", sources: list.items });
    } catch (e) {
      setState({
        kind: "error",
        message: e instanceof Error ? e.message : "Unknown error",
      });
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-8">
      <header className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold">Data Sources</h1>
          <p className="text-neutral-400 text-sm">
            Warehouse connections Datum can analyze.
          </p>
        </div>
        <Link
          href="/admin/data-sources/new"
          className="px-4 py-2 rounded bg-blue-700 hover:bg-blue-600 text-white font-medium text-sm"
        >
          + Add Data Source
        </Link>
      </header>

      <section>
        {state.kind === "loading" && (
          <p className="text-neutral-400">Loading data sources...</p>
        )}

        {state.kind === "error" && (
          <div className="text-red-400 border border-red-900 bg-red-950/50 rounded px-4 py-3">
            <p className="font-medium mb-1">Error loading data sources</p>
            <p className="text-sm">{state.message}</p>
          </div>
        )}

        {state.kind === "loaded" && state.sources.length === 0 && (
          <div className="text-neutral-500 text-sm border border-neutral-800 rounded px-4 py-6 text-center">
            No data sources yet.{" "}
            <Link href="/admin/data-sources/new" className="text-blue-400 hover:underline">
              Add one
            </Link>{" "}
            to get started.
          </div>
        )}

        {state.kind === "loaded" && state.sources.length > 0 && (
          <div className="space-y-3">
            {state.sources.map((ds) => (
              <DataSourceCard key={ds.id} source={ds} onDeleted={load} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
