# dictacode Architecture Plan v0.3.4 — API Versioning to /v1

## Status
- [x] Add versioned router `/v1` for all public STT endpoints (REST, WS, docs, CP) and remove unversioned endpoints.
- [x] Emit response header `X-Dictacode-API-Version: v1`.
- [x] Update OpenAPI/docs to live under `/v1`.
- [x] Align any HID HTTP/WS endpoints if present (confirm exposure). → HID has no HTTP endpoints (out of scope)
- [x] Add runtime and CI guards to prevent regression to unversioned routes.

**v0.3.4 goal:** ship `/v1`-only surface with strong safeguards; no backward compatibility required.

---

## Prerequisites
- FastAPI apps must create routes via `create_app()` (no module-level globals).
- `paths.py` helpers stable for static/templating assets.
- Clients able to switch to `/v1` paths; docs/examples updated.

---

## Scope
- STT HTTP/WS surface: audio endpoints, control panel HTML, metrics, OpenAPI/docs, websocket handshake.
- HID: only if it exposes HTTP/WS; otherwise out-of-scope.

---

## Design
- Introduce `APIRouter(prefix="/v1")`; register all public routes (REST, WS) and include routers within `create_app()`. Delete/disable unversioned mounts.
- Static/templating: keep existing mounts; add `/v1/cp` route to render CP template. Update template links and JS to honor a `base_path` helper (no hard-coded roots).
- WebSocket: move to `/v1/api/ws` only.
- OpenAPI/docs: set `docs_url="/v1/docs"`, `redoc_url=None`, `openapi_url="/v1/openapi.json"`; ensure OpenAPI lists only `/v1/*`.
- Middleware: add response header `X-Dictacode-API-Version: v1`; structured log/metric counters for `/v1` hits.
- Guards: startup self-check to assert no unversioned routes are registered; CI test to fail if any route path lacks `/v1/` prefix.
- Compatibility matrix: add API version entry; warn at startup if matrix or build lacks `/v1`.
- Tests/examples: update CP links, curl snippets, clients to `/v1`.

---

## Implementation Phases

### Phase 1: Router Refactor
1. Create `router_v1 = APIRouter(prefix="/v1")`; move REST/WS handlers into registration function used by `create_app()`.
2. Ensure static mounts and template setup occur before route registration; avoid module-level `app` usage.

### Phase 2: Hardened Mount
1. Include `router_v1` only; remove unversioned includes. Add startup assert that every route path starts with `/v1/` (except static mounts).
2. Add middleware for version header and metrics counters.
3. Add self-check endpoint/diagnostic that verifies versioned routes and OpenAPI correctness.

### Phase 3: Docs & Clients
1. Regenerate OpenAPI so paths show `/v1/*`.
2. Update docs/testing snippets, README/API examples, and control-panel JS (use `base_path` helper).

### Phase 4: CI & Compatibility Matrix
1. CI test to fail if any route lacks `/v1/`.
2. Add API version entry to compatibility matrix and surface startup warning if mismatch.

---

## Testing
- Unit: router inclusion under `/v1`, middleware injects header, startup assert rejects unversioned routes, OpenAPI base paths are `/v1/*`.
- Integration: hit `/v1/api/audio/ports`, `/v1/cp`, `/v1/metrics`, `/v1/api/ws`; verify responses match prior behavior.
- Docs: `/v1/docs` loads and lists only versioned paths; OpenAPI contains no unversioned entries.
- CI: route prefix check; optional smoke script hitting key endpoints; template-link test using `base_path` override.

---

## Open Questions
- Does HID expose HTTP/WS that must be versioned? If yes, mirror pattern with shared helper.
- Redirect vs 404 for legacy paths once flag off? (default plan: 404 after deprecation period.)
