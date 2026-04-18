"use client";

import { useEffect, useState } from "react";
import { api, type HealthDbResponse } from "@/lib/api";

type Status =
  | { kind: "loading" }
  | { kind: "success"; data: HealthDbResponse }
  | { kind: "error"; message: string };

export default function Home() {
  const [status, setStatus] = useState<Status>({ kind: "loading" });

  useEffect(() => {
    api
      .healthDb()
      .then((data) => setStatus({ kind: "success", data }))
      .catch((err: Error) => setStatus({ kind: "error", message: err.message }));
  }, []);

  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-100 p-8 font-mono">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">Datum</h1>
        <p className="text-neutral-400 mb-8">
          AI-assisted semantic layer — system status
        </p>

        <section className="border border-neutral-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">Backend health</h2>

          {status.kind === "loading" && (
            <p className="text-neutral-400">Checking…</p>
          )}

          {status.kind === "error" && (
            <div className="text-red-400">
              <p className="font-semibold mb-2">Error</p>
              <p className="text-sm">{status.message}</p>
              <p className="text-xs text-neutral-500 mt-4">
                Is the backend running on{" "}
                {process.env.NEXT_PUBLIC_API_URL}? Start it with{" "}
                <code className="bg-neutral-800 px-1 rounded">
                  uvicorn src.main:app --reload --port 8000
                </code>
              </p>
            </div>
          )}

          {status.kind === "success" && (
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-neutral-400">Status</dt>
                <dd className="text-green-400">{status.data.status}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-neutral-400">Database</dt>
                <dd>{status.data.database}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-neutral-400">pgvector version</dt>
                <dd>{status.data.pgvector_version}</dd>
              </div>
            </dl>
          )}
        </section>
      </div>
    </main>
  );
}
