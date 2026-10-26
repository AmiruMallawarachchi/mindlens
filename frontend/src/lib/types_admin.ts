// ---- Admin — backend/app/routers/system.py, backend/app/middleware/auth.py ----
// Separate token, separate client (lib/admin-api.ts) — see that file for why.

/** POST /api/v1/auth/admin/login. */
export interface AdminTokenResponse {
  admin_token: string;
  token_type: string;
  expires_in: number;
}

/** One entry in AdminSystemStatus.models / the GET /admin/models response —
 * ModelManager.health_status() in app/models/loader.py. Always exactly the
 * five keys AdminSystemStatus["models"] names; "not_loaded" has no
 * loaded_at/error/last_inference_ms. */
export interface AdminServiceHealth {
  provider: string;
  status: string;
}

/** GET /api/v1/admin/system. */
export interface AdminSystemStatus {
  status: string;
  environment: string;
  release: string;
  database: string;
  inference: AdminServiceHealth;
  rag: AdminServiceHealth;
  observability: AdminServiceHealth & { enabled: boolean };
  timestamp: string;
}
