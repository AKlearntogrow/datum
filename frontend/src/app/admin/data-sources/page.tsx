"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type DataSource } from "@/lib/api";
import { DataSourceCreateForm } from "@/components/DataSourceCreateForm";

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
      <header className="space-y-2">
        <h1 className="text-2xl font-bold">Data Sources</h1>
        <p className="text-neutral-400 text-sm">
          Warehouse connections Datum can analyze.
        </p>
      </header>

      <DataSourceCreateForm onCreated={load} />

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
            No data sources yet. Add one above to get started.
          </div>
        )}

        {state.kind === "loaded" && state.sources.length > 0 && (
          <div className="space-y-3">
            {state.sources.map((ds) => (
              <Link
                key={ds.id}
                href={`/admin/data-sources/${ds.id}`}
                className="block border border-neutral-800 rounded-lg p-4 hover:border-neutral-700 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-neutral-100">{ds.name}</h3>
                    <p className="text-xs font-mono text-neutral-500 mt-1">
                      {ds.warehouse_type} &middot; {ds.connection_url}
                    </p>
                    {ds.description && (
                      <p className="text-sm text-neutral-400 mt-1">{ds.description}</p>
                    )}
                  </div>
                  <span className="text-xs text-neutral-600">
                    {new Date(ds.created_at).toLocaleDateString()}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
