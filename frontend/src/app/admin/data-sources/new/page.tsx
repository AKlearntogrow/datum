"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function NewDataSourcePage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [warehouseType, setWarehouseType] = useState("postgres");
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
      const created = await api.createDataSource({
        name: name.trim(),
        warehouse_type: warehouseType,
        connection_url: connectionUrl.trim(),
        description: description.trim() || undefined,
      });
      router.push(`/admin/data-sources/${created.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <Link
        href="/admin/data-sources"
        className="text-sm text-neutral-500 hover:text-neutral-300"
      >
        &larr; Data Sources
      </Link>

      <h1 className="text-2xl font-bold">Add Data Source</h1>

      <div className="border border-amber-800 bg-amber-950/30 rounded-lg px-4 py-3 text-sm text-amber-300">
        Credentials are stored unencrypted in this local database. Do not use
        this instance for credentials you cannot afford to leak.
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
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
            Warehouse Type
          </label>
          <select
            value={warehouseType}
            onChange={(e) => setWarehouseType(e.target.value)}
            className="w-full px-3 py-2 rounded bg-neutral-900 border border-neutral-700 text-neutral-100 text-sm focus:outline-none focus:border-neutral-500"
          >
            <option value="postgres">PostgreSQL</option>
          </select>
        </div>

        <div>
          <label className="block text-sm text-neutral-400 mb-1">
            Connection URL
          </label>
          <input
            type="text"
            value={connectionUrl}
            onChange={(e) => setConnectionUrl(e.target.value)}
            placeholder="postgresql://user:password@host:5432/dbname"
            className="w-full px-3 py-2 rounded bg-neutral-900 border border-neutral-700 text-neutral-100 text-sm font-mono focus:outline-none focus:border-neutral-500"
          />
          <p className="text-xs text-neutral-600 mt-1">
            e.g. postgresql://user:password@host:5432/dbname
          </p>
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
            {working ? "Creating..." : "Create Data Source"}
          </button>
          <Link
            href="/admin/data-sources"
            className="px-4 py-2 rounded bg-neutral-800 hover:bg-neutral-700 text-neutral-200 font-medium text-sm"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
