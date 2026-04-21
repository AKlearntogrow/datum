"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type Scope } from "@/lib/api";

type LoadState =
  | { kind: "loading" }
  | { kind: "loaded"; scopes: Scope[] }
  | { kind: "error"; message: string };

export default function ScopesPage() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const list = await api.listScopes();
      setState({ kind: "loaded", scopes: list.items });
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

  async function handleDelete(scope: Scope) {
    if (!confirm(`Delete scope "${scope.name}"? This cannot be undone.`)) return;
    try {
      await api.deleteScope(scope.id);
      load();
    } catch (e) {
      alert(e instanceof Error ? e.message : "Unknown error");
    }
  }

  return (
    <div className="space-y-8">
      <header className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold">Scopes</h1>
          <p className="text-neutral-400 text-sm">
            Saved schema selections for analysis.
          </p>
        </div>
        <Link
          href="/admin/scopes/new"
          className="px-4 py-2 rounded bg-blue-700 hover:bg-blue-600 text-white font-medium text-sm"
        >
          + Create Scope
        </Link>
      </header>

      <section>
        {state.kind === "loading" && (
          <p className="text-neutral-400">Loading scopes...</p>
        )}

        {state.kind === "error" && (
          <div className="text-red-400 border border-red-900 bg-red-950/50 rounded px-4 py-3">
            <p className="font-medium mb-1">Error loading scopes</p>
            <p className="text-sm">{state.message}</p>
          </div>
        )}

        {state.kind === "loaded" && state.scopes.length === 0 && (
          <div className="text-neutral-500 text-sm border border-neutral-800 rounded px-4 py-6 text-center">
            No scopes yet.{" "}
            <Link href="/admin/scopes/new" className="text-blue-400 hover:underline">
              Create one
            </Link>{" "}
            to get started.
          </div>
        )}

        {state.kind === "loaded" && state.scopes.length > 0 && (
          <div className="space-y-3">
            {state.scopes.map((scope) => (
              <div
                key={scope.id}
                className="border border-neutral-800 rounded-lg p-4 hover:border-neutral-700 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="space-y-1 min-w-0 flex-1">
                    <Link
                      href={`/admin/scopes/${scope.id}`}
                      className="font-semibold text-neutral-100 hover:underline"
                    >
                      {scope.name}
                    </Link>
                    <p className="text-xs font-mono text-neutral-500">
                      {scope.included_schemas.join(", ")}
                    </p>
                    {scope.excluded_tables && scope.excluded_tables.length > 0 && (
                      <p className="text-xs text-neutral-600">
                        {scope.excluded_tables.length} table{scope.excluded_tables.length !== 1 ? "s" : ""} excluded
                      </p>
                    )}
                    {scope.description && (
                      <p className="text-sm text-neutral-400">{scope.description}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-3 ml-4 shrink-0">
                    <span className="text-xs text-neutral-600">
                      {new Date(scope.created_at).toLocaleString()}
                    </span>
                    <Link
                      href={`/admin/scopes/${scope.id}`}
                      className="text-xs text-neutral-400 hover:text-neutral-200"
                    >
                      View
                    </Link>
                    <button
                      type="button"
                      onClick={() => handleDelete(scope)}
                      className="text-xs text-neutral-600 hover:text-red-400"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
