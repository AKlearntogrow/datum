/**
 * API client for the Datum backend.
 *
 * Centralized here so there's a single place that knows how to talk to the
 * backend. Every page/component imports from this file rather than calling
 * fetch directly.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL;

if (!API_URL) {
  throw new Error(
    "NEXT_PUBLIC_API_URL is not set. Check frontend/.env.local — see .env.example for the expected value."
  );
}

// ---------------------------------------------------------------------
// Response types — mirror backend/src/schemas/entities.py
// ---------------------------------------------------------------------

export type HealthDbResponse = {
  status: string;
  database: string;
  pgvector_version: string;
};

export type Confidence = "low" | "medium" | "high";

export type EntityStatus = "proposed" | "approved" | "rejected" | "superseded";

export type SourceColumnRef = {
  snapshot_column_id: string;
  table: string;
  column: string;
};

export type Entity = {
  id: string;
  name: string;
  display_name: string;
  description: string;
  rationale: string;
  evidence: string[];
  confidence: Confidence;
  source_columns: SourceColumnRef[];
  status: EntityStatus;
  proposed_by: string;
  proposed_at: string;
  approved_by: string | null;
  approved_at: string | null;
  rejected_by: string | null;
  rejected_at: string | null;
  rejected_reason: string | null;
  reopened_at: string | null;
  prompt_version: string | null;
  model: string | null;
};

export type EntityList = {
  items: Entity[];
  total: number;
};

export type IngestResponse = {
  skipped: boolean;
  reason: string | null;
  last_snapshot_id: string | null;
  last_snapshot_captured_at: string | null;
  snapshot_id: string | null;
  source_database: string;
  tables_ingested: number;
  columns_ingested: number;
  entities_proposed: number;
  measures_proposed: number;
  dimensions_proposed: number;
  time_dimensions_proposed: number;
  relationships_proposed: number;
  data_quality_flags_proposed: number;
  entities_persisted: number;
};

// Mirrors backend/src/schemas/data_sources.py
export type DataSource = {
  id: string;
  name: string;
  warehouse_type: string;
  connection_url: string;
  description: string | null;
  created_by: string;
  created_at: string;
};

export type DataSourceList = {
  items: DataSource[];
  total: number;
};

export type DataSourceCreate = {
  name: string;
  warehouse_type: string;
  connection_url: string;
  description?: string;
};

export type SchemaInfo = {
  schema_name: string;
  tables: string[];
};

export type SchemaList = {
  schemas: SchemaInfo[];
};

// Mirrors backend/src/schemas/scopes.py
export type Scope = {
  id: string;
  data_source_id: string;
  name: string;
  included_schemas: string[];
  excluded_tables: string[] | null;
  description: string | null;
  created_by: string;
  created_at: string;
};

export type ScopeList = {
  items: Scope[];
  total: number;
};

export type ScopeCreate = {
  data_source_id: string;
  name: string;
  included_schemas: string[];
  excluded_tables?: string[];
  description?: string;
};

export type ScopeUpdate = {
  name?: string;
  description?: string;
};

// ---------------------------------------------------------------------
// Request helper — throws a rich Error on non-2xx so callers can display
// the backend's actual message, not a generic "fetch failed."
// ---------------------------------------------------------------------

async function request<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body && typeof body === "object" && "error" in body) {
        detail = String(body.error);
      }
    } catch {
      // Non-JSON response body; ignore
    }
    throw new Error(`Request to ${path} failed: ${detail}`);
  }

  // 204 No Content etc.
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------
// API surface
// ---------------------------------------------------------------------

export const api = {
  healthDb: () => request<HealthDbResponse>("/health/db"),

  // Entities
  listEntities: (status?: EntityStatus) => {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return request<EntityList>(`/api/entities${qs}`);
  },

  approveEntity: (id: string) =>
    request<Entity>(`/api/entities/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  rejectEntity: (id: string, reason?: string) =>
    request<Entity>(`/api/entities/${id}/reject`, {
      method: "POST",
      body: JSON.stringify(reason ? { reason } : {}),
    }),

  reopenEntity: (id: string) =>
    request<Entity>(`/api/entities/${id}/reopen`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  // Ingest
  runIngest: (warehouseUrl: string) =>
    request<IngestResponse>(`/api/ingest`, {
      method: "POST",
      body: JSON.stringify({ warehouse_url: warehouseUrl }),
    }),

  // Admin: data sources
  listDataSources: () => request<DataSourceList>("/api/admin/data-sources"),

  getDataSource: (id: string) =>
    request<DataSource>(`/api/admin/data-sources/${id}`),

  createDataSource: (body: DataSourceCreate) =>
    request<DataSource>("/api/admin/data-sources", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  deleteDataSource: (id: string) =>
    request<void>(`/api/admin/data-sources/${id}`, { method: "DELETE" }),

  listDataSourceSchemas: (id: string) =>
    request<SchemaList>(`/api/admin/data-sources/${id}/schemas`, {
      method: "POST",
    }),

  // Admin: scopes
  listScopes: (dataSourceId?: string) => {
    const qs = dataSourceId ? `?data_source_id=${encodeURIComponent(dataSourceId)}` : "";
    return request<ScopeList>(`/api/admin/scopes${qs}`);
  },

  getScope: (id: string) =>
    request<Scope>(`/api/admin/scopes/${id}`),

  createScope: (body: ScopeCreate) =>
    request<Scope>("/api/admin/scopes", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  updateScope: (id: string, body: ScopeUpdate) =>
    request<Scope>(`/api/admin/scopes/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  deleteScope: (id: string) =>
    request<void>(`/api/admin/scopes/${id}`, { method: "DELETE" }),
};
