"use client";

import Link from "next/link";

export default function AdminHome() {
  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold">Admin</h1>
        <p className="text-neutral-400 text-sm">
          Manage warehouse connections and analysis scopes.
        </p>
      </header>

      <div className="border border-amber-800 bg-amber-950/30 rounded-lg px-4 py-3 text-sm text-amber-300">
        Credentials are stored unencrypted in this local database. Do not use
        this instance for credentials you cannot afford to leak.
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Link
          href="/admin/data-sources"
          className="border border-neutral-800 rounded-lg p-6 hover:border-neutral-700 transition-colors"
        >
          <h2 className="text-lg font-semibold mb-1">Data Sources</h2>
          <p className="text-sm text-neutral-400">
            Add and manage warehouse connections (Postgres, BigQuery, Snowflake).
          </p>
        </Link>
      </div>
    </div>
  );
}
