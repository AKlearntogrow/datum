"use client";

import { useState } from "react";
import Link from "next/link";
import { api, type DataSource } from "@/lib/api";

function maskUrl(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.hostname + (parsed.port ? `:${parsed.port}` : "");
  } catch {
    return "•••";
  }
}

type Props = {
  source: DataSource;
  onDeleted: () => void;
};

export function DataSourceCard({ source, onDeleted }: Props) {
  const [showUrl, setShowUrl] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete(e: React.MouseEvent) {
    e.preventDefault(); // don't navigate via the parent Link
    e.stopPropagation();
    if (!confirm(`Delete data source "${source.name}"? This cannot be undone.`)) return;
    setDeleting(true);
    setError(null);
    try {
      await api.deleteDataSource(source.id);
      onDeleted();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setDeleting(false);
    }
  }

  function handleToggleUrl(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setShowUrl((v) => !v);
  }

  return (
    <div className="border border-neutral-800 rounded-lg p-4 hover:border-neutral-700 transition-colors">
      <div className="flex items-start justify-between">
        <div className="space-y-1 min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Link
              href={`/admin/data-sources/${source.id}`}
              className="font-semibold text-neutral-100 hover:underline"
            >
              {source.name}
            </Link>
            <span className="text-xs px-2 py-0.5 rounded bg-neutral-800 text-neutral-400 border border-neutral-700">
              {source.warehouse_type}
            </span>
          </div>
          <div className="text-xs font-mono text-neutral-500 flex items-center gap-2">
            <span>{showUrl ? source.connection_url : maskUrl(source.connection_url)}</span>
            <button
              type="button"
              onClick={handleToggleUrl}
              className="text-neutral-600 hover:text-neutral-400 text-xs"
            >
              {showUrl ? "Hide" : "Show"}
            </button>
          </div>
          {source.description && (
            <p className="text-sm text-neutral-400">{source.description}</p>
          )}
        </div>
        <div className="flex items-center gap-3 ml-4 shrink-0">
          <span className="text-xs text-neutral-600">
            {new Date(source.created_at).toLocaleDateString()}
          </span>
          <Link
            href={`/admin/data-sources/${source.id}`}
            className="text-xs text-neutral-400 hover:text-neutral-200"
          >
            View
          </Link>
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="text-xs text-neutral-600 hover:text-red-400 disabled:opacity-50"
          >
            {deleting ? "..." : "Delete"}
          </button>
        </div>
      </div>
      {error && (
        <div className="mt-2 text-sm text-red-400 border border-red-900 bg-red-950/50 rounded px-3 py-2">
          {error}
        </div>
      )}
    </div>
  );
}
