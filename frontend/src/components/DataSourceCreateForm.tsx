"use client";

import { useState } from "react";
import { api } from "@/lib/api";

type Props = {
  onCreated: () => void;
};

export function DataSourceCreateForm({ onCreated }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [name, setName] = useState("");
  const [connectionUrl, setConnectionUrl] = useState("");
  const [description, setDescription] = useState("");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !connectionUrl.trim()) return;
    setWorking(true);
    setError(null);
    try {
      await api.createDataSource({
        name: name.trim(),
        warehouse_type: "postgres",
        connection_url: connectionUrl.trim(),
        description: description.trim() || undefined,
      });
      setName("");
      setConnectionUrl("");
      setDescription("");
      setExpanded(false);
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setWorking(false);
    }
  }

  if (!expanded) {
    return (
      <button
        type="button"
        onClick={() => setExpanded(true)}
        className="px-4 py-2 rounded bg-blue-700 hover:bg-blue-600 text-white font-medium text-sm"
      >
        Add data source
      </button>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="border border-neutral-800 rounded-lg p-6 space-y-4"
    >
      <h3 className="text-lg font-semibold">Add a data source</h3>

      <div className="border border-amber-800 bg-amber-950/30 rounded px-3 py-2 text-xs text-amber-300">
        Credentials are stored unencrypted. Use throwaway credentials for evaluation.
      </div>

      <div className="space-y-3">
        <div>
          <label className="block text-sm text-neutral-400 mb-1">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Acme Production Warehouse"
            className="w-full px-3 py-2 rounded bg-neutral-900 border border-neutral-700 text-neutral-100 text-sm focus:outline-none focus:border-neutral-500"
          />
        </div>

        <div>
          <label className="block text-sm text-neutral-400 mb-1">
            Connection URL
          </label>
          <input
            type="text"
            value={connectionUrl}
            onChange={(e) => setConnectionUrl(e.target.value)}
            placeholder="postgresql://user:pass@host:5432/database"
            className="w-full px-3 py-2 rounded bg-neutral-900 border border-neutral-700 text-neutral-100 text-sm font-mono focus:outline-none focus:border-neutral-500"
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
            placeholder="What this warehouse contains"
            className="w-full px-3 py-2 rounded bg-neutral-900 border border-neutral-700 text-neutral-100 text-sm focus:outline-none focus:border-neutral-500"
          />
        </div>

        <p className="text-xs text-neutral-600">
          Warehouse type: Postgres (v0 only supports Postgres)
        </p>
      </div>

      {error && (
        <div className="text-sm text-red-400 border border-red-900 bg-red-950/50 rounded px-3 py-2">
          {error}
        </div>
      )}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={working || !name.trim() || !connectionUrl.trim()}
          className="px-4 py-2 rounded bg-blue-700 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium text-sm"
        >
          {working ? "Creating..." : "Create"}
        </button>
        <button
          type="button"
          onClick={() => {
            setExpanded(false);
            setError(null);
          }}
          disabled={working}
          className="px-4 py-2 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 font-medium text-sm"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
