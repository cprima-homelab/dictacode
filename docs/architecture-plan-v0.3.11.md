# dictacode Architecture Plan v0.3.11 — Multi-Badge License Tokens

## Status / ToDo
- [x] Support license tokens containing multiple badges/tiers.
- [x] Update validation to parse multiple entries from one token.
- [x] Expose all badges via API/CLI (read-only) and POST save endpoint.
- [x] Preserve existing single-badge behavior for compatibility.
- [ ] Tests for multi-badge parsing, validation, and API/CLI responses.

### Implementation Notes (Completed)
- **Badge dataclass**: Added `Badge` dataclass for individual badges with `kid, tier, name, issued_at`.
- **BadgeState**: Updated to hold `List[Badge]` with backward-compat properties (`tier`, `badge`, `name`, `issued_at`).
- **API response**: `to_dict()` returns both v0.3.11 fields (`badges`, `tiers`, `primary`, `token_present`) and v0.3.3 compat fields.
- **CLI**: `show` command displays all badges; `save` validates and shows badge count.

---

## Prerequisites
- Existing badge-only license system (v0.3.3): single badge per token; public key registry; GET/POST `/api/license`; CLI token save/show.
- Ed25519 key derivation/keygen exists in tools.

---

## Scope
- STT app license badge system only (cosmetic).
- Tokens may contain multiple badge entries; no feature gating.

---

## Design
- Token format (compatible with v0.3.3):
  - `<base64url(payload_json_bytes)>.<base64url(signature_bytes)>`
  - Payload now supports `badges: [ {kid, tier, name, issued_at}, ... ]`
  - Backward compatibility: if `tier` is present at top-level, treat as a single badge.
- Validation:
  - Decode payload, select badges array if present; otherwise wrap the single badge.
  - Verify signature over raw payload bytes using `kid` per badge (or single `kid`).
  - If any badge fails verification, treat that badge as invalid and exclude it; token remains cosmetic only.
  - Unknown `kid` → exclude that badge; fall back to “free” if all badges invalid.
- Storage:
  - Keep token string as-is (same file locations); store parsed badges list in memory.
- API:
  - `GET /api/license` returns `{badges: [...], tiers: [...], primary: <first badge or highest tier>, token_present: bool}`
  - `POST /api/license` saves token (user scope) and returns parsed badges.
  - Optional `DELETE /api/license` clears token.
- CLI:
  - `dictacode-license show` prints all badges; `save <token>` unchanged; output includes count.
- UI:
  - Control panel can display multiple badges; pick a primary display (e.g., first or highest-tier).

---

## Implementation Phases

### Phase 1: Data Model & Validation
1. Update license payload parsing to support `badges` array; wrap single badge for legacy.
2. Validate each badge signature (shared token signature or per-badge `kid`); exclude invalid badges.
3. Return list of valid badges; if empty → free state.

### Phase 2: API/CLI Surfaces
1. API `GET /api/license` returns badges list + primary/tiers; `POST` persists token and returns parsed badges.
2. CLI `show` lists all badges; keep `save` behavior unchanged.

### Phase 3: UI/State Integration
1. Badge state in memory holds list of badges; expose primary for banners.
2. CP updates to render multiple badges.

### Phase 4: Tests
1. Unit: multi-badge token parsing; mixed valid/invalid badges; unknown `kid`; legacy single-badge token.
2. API: GET/POST returns badge list; invalid token → free state.
3. CLI: show outputs multiple badges; save persists token.

---

## Testing
- Multi-badge token with all valid signatures → all badges returned.
- Mixed badges (one invalid/unknown kid) → valid ones returned; invalid excluded.
- Legacy single-badge token → still works, wrapped as one badge.
- POST saves token, GET returns same badges; DELETE clears.
- CLI show outputs multiple badges.

---

## Open Questions
- Primary badge selection rule: first badge vs highest tier? (Default: first in list.)
- Do we need per-badge `kid` or one `kid` for all? (Default: single `kid` for token; per-badge `kid` optional.) 
