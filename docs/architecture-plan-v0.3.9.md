# dictacode Architecture Plan v0.3.9 — Split API vs Web Control Panel

## Status / ToDo
- [x] Separate FastAPI surfaces for API and Web control panel.
- [x] Ensure OpenAPI includes only API endpoints (no CP pages).
- [x] Serve static/templates from a dedicated web app/router.
- [x] Keep both apps mountable in one process; allow future split to separate ports if needed.
- [x] Tests to validate route separation and versioning.

### Implementation Notes (Completed)
- **URL Change**: CP moved from `/v1/cp*` to `/cp*` (unversioned) - UI doesn't need versioning.
- **Architecture**: Starlette ASGI app combines `api_app` (with OpenAPI) and `web_app` (no OpenAPI) via Mount.
- **CLI Options**: Added `--api-only` and `--web-only` flags to `dictacode-stt-api` for separate deployment.
- **Tests**: `tests/test_api_split.py` validates OpenAPI exclusion, route separation, and deployment modes.

---

## Prerequisites
- Existing FastAPI app currently serves both API and CP under `/v1` prefix.
- IPC diagnostics/state available for API data.

---

## Scope
- STT project only.
- Split concerns: API (JSON/WS) vs Web CP (HTML/static).

---

## Design
- Two FastAPI app instances:
  - `api_app`: hosts `/v1` API routes (REST/WS), OpenAPI/docs.
  - `web_app`: hosts `/v1/cp*` HTML routes and static assets; no OpenAPI/docs.
- Routers:
  - `api_router` with `/v1/api/*`, health, diagnostics, state, license, WS.
  - `web_router` with `/v1/cp*` pages and static mounts.
- Mount strategy:
  - Default: mount `web_app` under the main ASGI app so a single uvicorn serves both (one port).
  - Future-ready: allow running `api_app` and `web_app` separately (e.g., two uvicorn commands) by exposing both objects in `api.py`.
- Versioning guard: OpenAPI only contains API routes; CP routes excluded; ensure route validation still enforces `/v1` on API.
- Static/templates: mounted/configured in `web_app` only.

---

## Implementation Phases

### Phase 1: App/Router Split
1. Introduce `api_app`, `web_app`, `api_router`, `web_router` in `api.py`.
2. Move CP routes (`/cp*`, static/templates) to `web_router`.
3. Keep API routes on `api_router`.

### Phase 2: App Assembly
1. In `create_app()`, configure middleware on `api_app`; mount `web_app` (with its router and static mounts) under the main ASGI app.
2. Expose both `api_app` and `web_app` for optional separate serving.

### Phase 3: OpenAPI/Docs
1. Ensure OpenAPI/docs only include API routes; disable docs on `web_app`.
2. Keep `/v1/docs` and `/v1/openapi.json` for API only.

### Phase 4: Testing
1. Assert no CP routes appear in OpenAPI.
2. Route validation still passes for API (`/v1/*`).
3. CP pages/static served via `web_app` mounts.

---

## Testing
- Unit/integration: request `/v1/api/...` vs `/v1/cp/...` and verify correct responses/sources.
- OpenAPI: check that `/v1/openapi.json` lacks CP routes.
- Static/templates: served only by `web_app` mounts.

---

## Open Questions (Resolved)
- **Separate ports/processes?** No - kept single-process mount with `--api-only`/`--web-only` flags for optional split.
- **CP URL prefix?** Moved to `/cp` (unversioned) - UI doesn't need versioning. Breaking change from `/v1/cp`.
