"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, type DataSource, type SchemaInfo } from "@/lib/api";
import { SchemaPicker, type SchemaSelection } from "@/components/SchemaPicker";

type SourcesState =
  | { kind: "loading" }
  | { kind: "loaded"; sources: DataSource[] }
  | { kind: "error"; message: string };

type SchemasState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; schemas: SchemaInfo[] }
  | { kind: "error"; message: string };

export default function NewScopePage() {
  return (
    <Suspense fallback={<p className="text-neutral-400">Loading...</p>}>
      <NewScopeForm />
    </Suspense>
  );
}

function NewScopeForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedDsId = searchParams.get("data_source_id");

  const [sourcesState, setSourcesState] = useState<SourcesState>({ kind: "loading" });
  const [schemasState, setSchemasState] = useState<SchemasState>({ kind: "idle" });
  const [dataSourceId, setDataSourceId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selection, setSelection] = useState<SchemaSelection>({
    included_schemas: [],
    excluded_tables: null,
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Load data sources on mount
  useEffect(() => {
    (async () => {
      try {
        const list = await api.listDataSources();
        setSourcesState({ kind: "loaded", sources: list.items });
        // Pre-select if query param present and valid
        if (preselectedDsId && list.items.some((ds) => ds.id === preselectedDsId)) {
          setDataSourceId(preselectedDsId);
        }
      } catch (e) {
        setSourcesState({
          kind: "error",
          message: e instanceof Error ? e.message : "Unknown error",
        });
      }
    })();
  }, [preselectedDsId]);

  // Fetch schemas when data source changes
  const fetchSchemas = useCallback(async (dsId: string) => {
    if (!dsId) {
      setSchemasState({ kind: "idle" });
      return;
    }
    setSchemasState({ kind: "loading" });
    try {
      const result = await api.listDataSourceSchemas(dsId);
      setSchemasState({ kind: "loaded", schemas: result.schemas });
    } catch (e) {
      setSchemasState({
        kind: "error",
        message: e instanceof Error ? e.message : "Unknown error",
      });
    }
  }, []);

  useEffect(() => {
    if (dataSourceId) {
      fetchSchemas(dataSourceId);
    } else {
      setSchemasState({ kind: "idle" });
    }
  }, [dataSourceId, fetchSchemas]);

  function handleDataSourceChange(nextId: string) {
    setDataSourceId(nextId);
    // Reset selection — schemas from one data source don't apply to another
    setSelection({ included_schemas: [], excluded_tables: null });
    setSubmitError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!dataSourceId || selection.included_schemas.length === 0 || !name.trim()) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await api.createScope({
        data_source_id: dataSourceId,
        name: name.trim(),
        included_schemas: selection.included_schemas,
        excluded_tables: selection.excluded_tables ?? undefined,
        description: description.trim() || undefined,
      });
      router.push(`/admin/scopes/${created.id}`);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit =
    !!dataSourceId &&
    selection.included_schemas.length > 0 &&
    !!name.trim() &&
    !submitting;

  return (
    <div className="space-y-6 max-w-3xl">
      <Link
        href="/admin/scopes"
        className="text-sm text-neutral-500 hover:text-neutral-300"
      >
        &larr; Scopes
      </Link>

      <h1 className="text-2xl font-bold">Create Scope</h1>

      {sourcesState.kind === "loading" && (
        <p className="text-neutral-400">Loading data sources...</p>
      )}

      {sourcesState.kind === "error" && (
        <div className="text-red-400 border border-red-900 bg-red-950/50 rounded px-4 py-3">
          <p className="text-sm">{sourcesState.message}</p>
        </div>
      )}

      {sourcesState.kind === "loaded" && sourcesState.sources.length === 0 && (
        <div className="text-neutral-500 text-sm border border-neutral-800 rounded px-4 py-6 text-center">
          No data sources yet.{" "}
          <Link href="/admin/data-sources/new" className="text-blue-400 hover:underline">
            Add one first
          </Link>.
        </div>
      )}

      {sourcesState.kind === "loaded" && sourcesState.sources.length > 0 && (
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm text-neutral-400 mb-1">
              Data Source
            </label>
            <select
              value={dataSourceId}
              onChange={(e) => handleDataSourceChange(e.target.value)}
              className="w-full px-3 py-2 rounded bg-neutral-900 border border-neutral-700 text-neutral-100 text-sm focus:outline-none focus:border-neutral-500"
            >
              <option value="">Select a data source...</option>
              {sourcesState.sources.map((ds) => (
                <option key={ds.id} value={ds.id}>
                  {ds.name} ({ds.warehouse_type})
                </option>
              ))}
            </select>
          </div>

          {schemasState.kind === "loading" && (
            <p className="text-neutral-400 text-sm">Loading schemas...</p>
          )}

          {schemasState.kind === "error" && (
            <div className="text-red-400 border border-red-900 bg-red-950/50 rounded px-4 py-3">
              <p className="font-medium mb-1">Could not connect to warehouse</p>
              <p className="text-sm">{schemasState.message}</p>
            </div>
          )}

          {schemasState.kind === "loaded" && (
            <>
              <div>
                <label className="block text-sm text-neutral-400 mb-2">
                  Select schemas to include
                </label>
                <SchemaPicker
                  schemas={schemasState.schemas}
                  selection={selection}
                  onChange={setSelection}
                />
                {selection.included_schemas.length > 0 && (
                  <p className="text-xs text-neutral-500 mt-2">
                    {selection.included_schemas.length} schema{selection.included_schemas.length !== 1 ? "s" : ""} selected
                    {selection.excluded_tables && selection.excluded_tables.length > 0
                      ? `, ${selection.excluded_tables.length} table${selection.excluded_tables.length !== 1 ? "s" : ""} excluded`
                      : ""}
                  </p>
                )}
              </div>

              <div>
                <label className="block text-sm text-neutral-400 mb-1">
                  Scope Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Sales + Finance"
                  className="w-full px-3 py-2 rounded bg-neutral-900 border border-neutral-700 text-neutral-100 text-sm focus:outline-none focus:border-neutral-500"
                />
              </div>

              <div>
                <label className="block text-sm text-neutral-400 mb-1">
                  Description (optional)
                </label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What this scope covers"
                  className="w-full px-3 py-2 rounded bg-neutral-900 border border-neutral-700 text-neutral-100 text-sm focus:outline-none focus:border-neutral-500"
                />
              </div>

              {submitError && (
                <div className="text-sm text-red-400 border border-red-900 bg-red-950/50 rounded px-3 py-2">
                  {submitError}
                </div>
              )}

              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={!canSubmit}
                  className="px-4 py-2 rounded bg-blue-700 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium text-sm"
                >
                  {submitting ? "Creating..." : "Create Scope"}
                </button>
                <Link
                  href="/admin/scopes"
                  className="px-4 py-2 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 font-medium text-sm"
                >
                  Cancel
                </Link>
              </div>
            </>
          )}
        </form>
      )}
    </div>
  );
}
