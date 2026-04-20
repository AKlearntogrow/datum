"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useParams } from "next/navigation";
import { api, type DataSource, type SchemaInfo } from "@/lib/api";

type LoadState =
  | { kind: "loading" }
  | { kind: "loaded"; source: DataSource; schemas: SchemaInfo[] | null }
  | { kind: "error"; message: string };

function maskUrl(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.hostname + (parsed.port ? `:${parsed.port}` : "");
  } catch {
    return "•••";
  }
}

export default function DataSourceDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [showUrl, setShowUrl] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [loadingSchemas, setLoadingSchemas] = useState(false);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const source = await api.getDataSource(id);
      setState({ kind: "loaded", source, schemas: null });
    } catch (e) {
      setState({
        kind: "error",
        message: e instanceof Error ? e.message : "Unknown error",
      });
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleLoadSchemas() {
    setLoadingSchemas(true);
    try {
      const result = await api.listDataSourceSchemas(id);
      setState((prev) => {
        if (prev.kind !== "loaded") return prev;
        return { ...prev, schemas: result.schemas };
      });
    } catch (e) {
      // Show empty schemas on error so the button disappears
      setState((prev) => {
        if (prev.kind !== "loaded") return prev;
        return { ...prev, schemas: [] };
      });
    } finally {
      setLoadingSchemas(false);
    }
  }

  async function handleDelete() {
    if (state.kind !== "loaded") return;
    if (!confirm(`Delete data source "${state.source.name}"? This cannot be undone.`)) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteDataSource(id);
      router.push("/admin/data-sources");
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setDeleting(false);
    }
  }

  if (state.kind === "loading") {
    return <p className="text-neutral-400">Loading data source...</p>;
  }

  if (state.kind === "error") {
    return (
      <div className="space-y-4">
        <Link
          href="/admin/data-sources"
          className="text-sm text-neutral-500 hover:text-neutral-300"
        >
          &larr; Data Sources
        </Link>
        <div className="text-red-400 border border-red-900 bg-red-950/50 rounded px-4 py-3">
          <p className="font-medium mb-1">Error</p>
          <p className="text-sm">{state.message}</p>
        </div>
      </div>
    );
  }

  const { source, schemas } = state;

  return (
    <div className="space-y-8">
      <Link
        href="/admin/data-sources"
        className="text-sm text-neutral-500 hover:text-neutral-300"
      >
        &larr; Data Sources
      </Link>

      <header className="space-y-1">
        <h1 className="text-2xl font-bold">{source.name}</h1>
        <p className="text-xs font-mono text-neutral-500">{source.id}</p>
      </header>

      <div className="border border-amber-800 bg-amber-950/30 rounded-lg px-4 py-3 text-sm text-amber-300">
        Credentials are stored unencrypted in this local database. Do not use
        this instance for credentials you cannot afford to leak.
      </div>

      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 text-sm">
        <dt className="text-neutral-500">Name</dt>
        <dd>{source.name}</dd>
        <dt className="text-neutral-500">Warehouse type</dt>
        <dd>{source.warehouse_type}</dd>
        <dt className="text-neutral-500">Connection URL</dt>
        <dd className="font-mono text-xs break-all flex items-center gap-2">
          <span>{showUrl ? source.connection_url : maskUrl(source.connection_url)}</span>
          <button
            type="button"
            onClick={() => setShowUrl((v) => !v)}
            className="text-neutral-600 hover:text-neutral-400 text-xs shrink-0"
          >
            {showUrl ? "Hide" : "Show"}
          </button>
        </dd>
        {source.description && (
          <>
            <dt className="text-neutral-500">Description</dt>
            <dd>{source.description}</dd>
          </>
        )}
        <dt className="text-neutral-500">Created by</dt>
        <dd>{source.created_by}</dd>
        <dt className="text-neutral-500">Created at</dt>
        <dd>{new Date(source.created_at).toLocaleString()}</dd>
      </dl>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Visible schemas</h2>
        {schemas === null && (
          <button
            type="button"
            onClick={handleLoadSchemas}
            disabled={loadingSchemas}
            className="px-4 py-2 rounded bg-neutral-800 hover:bg-neutral-700 disabled:opacity-50 text-neutral-200 font-medium text-sm"
          >
            {loadingSchemas ? "Connecting..." : "Load schemas from warehouse"}
          </button>
        )}
        {schemas !== null && schemas.length === 0 && (
          <p className="text-sm text-neutral-500">No schemas found.</p>
        )}
        {schemas !== null && schemas.length > 0 && (
          <div className="space-y-2">
            {schemas.map((s) => (
              <div
                key={s.schema_name}
                className="border border-neutral-800 rounded px-4 py-3"
              >
                <h3 className="font-mono text-sm font-semibold text-neutral-200">
                  {s.schema_name}
                </h3>
                <p className="text-xs text-neutral-500 mt-1">
                  {s.tables.length} table{s.tables.length !== 1 ? "s" : ""}:{" "}
                  {s.tables.join(", ")}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Scopes using this data source</h2>
        <p className="text-sm text-neutral-500 italic">Scopes UI coming next.</p>
      </section>

      <section className="border-t border-neutral-800 pt-6 space-y-3">
        <h2 className="text-lg font-semibold text-red-400">Danger zone</h2>
        {deleteError && (
          <div className="text-sm text-red-400 border border-red-900 bg-red-950/50 rounded px-3 py-2">
            {deleteError}
          </div>
        )}
        <button
          type="button"
          onClick={handleDelete}
          disabled={deleting}
          className="px-4 py-2 rounded bg-red-900 hover:bg-red-800 disabled:opacity-50 disabled:cursor-not-allowed text-red-100 font-medium text-sm"
        >
          {deleting ? "Deleting..." : "Delete this data source"}
        </button>
      </section>
    </div>
  );
}
