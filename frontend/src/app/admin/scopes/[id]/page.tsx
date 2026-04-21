"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useParams } from "next/navigation";
import { api, type Scope, type DataSource } from "@/lib/api";

type LoadState =
  | { kind: "loading" }
  | { kind: "loaded"; scope: Scope; dataSource: DataSource }
  | { kind: "error"; message: string };

export default function ScopeDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editWorking, setEditWorking] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const scope = await api.getScope(id);
      const dataSource = await api.getDataSource(scope.data_source_id);
      setState({ kind: "loaded", scope, dataSource });
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

  function startEdit() {
    if (state.kind !== "loaded") return;
    setEditName(state.scope.name);
    setEditError(null);
    setEditing(true);
  }

  async function handleSaveName() {
    if (!editName.trim()) return;
    setEditWorking(true);
    setEditError(null);
    try {
      await api.updateScope(id, { name: editName.trim() });
      setEditing(false);
      load();
    } catch (e) {
      setEditError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setEditWorking(false);
    }
  }

  async function handleDelete() {
    if (state.kind !== "loaded") return;
    if (!confirm(`Delete scope "${state.scope.name}"? This cannot be undone.`)) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteScope(id);
      router.push("/admin/scopes");
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setDeleting(false);
    }
  }

  if (state.kind === "loading") {
    return <p className="text-neutral-400">Loading scope...</p>;
  }

  if (state.kind === "error") {
    return (
      <div className="space-y-4">
        <Link href="/admin/scopes" className="text-sm text-neutral-500 hover:text-neutral-300">
          &larr; Scopes
        </Link>
        <div className="text-red-400 border border-red-900 bg-red-950/50 rounded px-4 py-3">
          <p className="font-medium mb-1">Error</p>
          <p className="text-sm">{state.message}</p>
        </div>
      </div>
    );
  }

  const { scope, dataSource } = state;

  return (
    <div className="space-y-8">
      <Link href="/admin/scopes" className="text-sm text-neutral-500 hover:text-neutral-300">
        &larr; Scopes
      </Link>

      <header className="space-y-1">
        {editing ? (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className="text-2xl font-bold bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-neutral-100 focus:outline-none focus:border-neutral-500"
            />
            <button
              type="button"
              onClick={handleSaveName}
              disabled={editWorking || !editName.trim()}
              className="px-3 py-1 rounded bg-blue-700 hover:bg-blue-600 disabled:opacity-50 text-white text-sm font-medium"
            >
              {editWorking ? "..." : "Save"}
            </button>
            <button
              type="button"
              onClick={() => { setEditing(false); setEditError(null); }}
              disabled={editWorking}
              className="px-3 py-1 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-sm"
            >
              Cancel
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{scope.name}</h1>
            <button
              type="button"
              onClick={startEdit}
              className="text-xs text-neutral-500 hover:text-neutral-300"
            >
              Edit Name
            </button>
          </div>
        )}
        {editError && (
          <div className="text-sm text-red-400 border border-red-900 bg-red-950/50 rounded px-3 py-2">
            {editError}
          </div>
        )}
        <p className="text-xs font-mono text-neutral-500">{scope.id}</p>
      </header>

      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 text-sm">
        <dt className="text-neutral-500">Data source</dt>
        <dd>
          <Link
            href={`/admin/data-sources/${dataSource.id}`}
            className="text-blue-400 hover:underline"
          >
            {dataSource.name}
          </Link>
        </dd>
        <dt className="text-neutral-500">Included schemas</dt>
        <dd className="flex flex-wrap gap-1">
          {scope.included_schemas.map((s) => (
            <span
              key={s}
              className="bg-neutral-800 text-neutral-200 rounded px-2 py-1 text-xs font-mono"
            >
              {s}
            </span>
          ))}
        </dd>
        {scope.excluded_tables !== null && (
          <>
            <dt className="text-neutral-500">Excluded tables</dt>
            <dd>
              {scope.excluded_tables.length > 0 ? (
                <ul className="text-xs font-mono text-neutral-400 space-y-0.5">
                  {scope.excluded_tables.map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
              ) : (
                <span className="text-xs text-neutral-600 italic">No tables excluded</span>
              )}
            </dd>
          </>
        )}
        {scope.description && (
          <>
            <dt className="text-neutral-500">Description</dt>
            <dd>{scope.description}</dd>
          </>
        )}
        <dt className="text-neutral-500">Created by</dt>
        <dd>{scope.created_by}</dd>
        <dt className="text-neutral-500">Created at</dt>
        <dd>{new Date(scope.created_at).toLocaleString()}</dd>
      </dl>

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
          {deleting ? "Deleting..." : "Delete this scope"}
        </button>
      </section>
    </div>
  );
}
