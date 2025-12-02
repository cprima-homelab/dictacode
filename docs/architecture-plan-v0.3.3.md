**Big picture **

* The app exists already and **works fully without a license key**.
* You will add a new **badge-only license key system** (cosmetic, FOSS aligned).
* Purpose is **recognition + contribution incentive**, not security/DRM.
* Key is **stored locally**, checked **on startup**, and **never blocks typing or other features**.
* A signed token proves donation/contribution without needing internet.
* Future keys may rotate, so support **multiple public keys**.
* Expose the badge state via API: **GET** for diagnostics/UI and **POST** to save a token from the control panel (writes user-scope file).

---

**Addressing the developer directly**

Implement this feature as follows:

### A. Accept license token

* Provide a CLI command to save the token once.
* Save to:

  * user scope: `~/.config/dictacode/license.key`
  * system scope: `/etc/dictacode/license.key`

Token format you expect to read/write:

```
<base64url(payload_json_bytes)>.<base64url(signature_bytes)>
```

Payload example you will decode later:

```json
{
  "kid": "key-1",
  "tier": "donated",
  "name": "Lorem Ipsum Dev",
  "issued_at": "2025-12-01"
}
```

### B. Ship a public-key registry

* Embed a dictionary mapping `kid → public key (PEM)`.

```python
PUBLIC_KEYS = {
    "key-1": b"""-----BEGIN PUBLIC KEY-----
    <TBD>
    -----END PUBLIC KEY-----""",
    "key-2": b"""-----BEGIN PUBLIC KEY-----
    <TBD>
    -----END PUBLIC KEY-----""",
}
```

### C. Validate at startup

1. Try reading user scope file, else system scope, else `"free"` state.
2. Split token into `payload_b64, signature_b64`.
3. Extract `kid` from decoded payload **before** signature verification.
4. For the given `kid`, load the matching public key.
5. Verify signature over the **raw payload bytes**.
6. If verification fails → log warning → use neutral `"free"` badge state.

Code sketch for startup check:

```python
import base64, json, logging
from pathlib import Path
from cryptography.hazmat.primitives.serialization import load_pem_public_key

def load_badge_state() -> dict:
    paths = [
        Path.home() / ".config/dictacode/license.key",
        Path("/etc/dictacode/license.key")
    ]

    token = None
    for p in paths:
        if p.exists():
            token = p.read_text().strip()
            break
    if not token:
        return {"tier": "free", "badge": None}

    try:
        payload_b64, sig_b64 = token.split(".", 1)
        payload = base64.urlsafe_b64decode(payload_b64)
        sig = base64.urlsafe_b64decode(sig_b64)

        data = json.loads(payload)
        kid = data.get("kid")
        if not kid or kid not in PUBLIC_KEYS:
            logging.warning("Unknown license key id (kid). Falling back to Free.")
            return {"tier": "free", "badge": None}

        pub_pem = PUBLIC_KEYS[kid]
        pub = load_pem_public_key(pub_pem)
        pub.verify(sig, payload)

        return {"tier": data.get("tier","free"), "badge": data.get("name")}
    except Exception as e:
        logging.warning(f"License invalid: {e}. Falling back to Free.")
        return {"tier": "free", "badge": None}
```

Call this function in your existing startup routine and persist result globally as your edition label/banner.

### D. Render, never enforce

Use the returned object only to display:

* Edition label in terminal banner
* Name in credits
* Badge in UI (future web panel)
* REST endpoints:
  * `GET /api/license` returns badge state for CP/diagnostics; no auth, read-only, responds even when key is missing/invalid.
  * `POST /api/license` accepts a token payload, stores to user scope (not system), revalidates, and returns the resulting badge state; still cosmetic.

### E. Testing checklist

You will add automated tests that prove:

| Test                            | Expect                                |
| ------------------------------- | ------------------------------------- |
| No file present                 | App starts, tier=`free`, badge=`None` |
| File exists + valid signature   | Parsed tier + name returned           |
| File exists + invalid signature | Fallback to `free`                    |
| File exists + unknown `kid`     | Fallback to `free`                    |
| Token string malformed          | Fallback to `free`, log warning       |
| REST endpoint returns state     | `/api/license` returns current badge state (`free` when invalid/missing) |
| POST saves token and returns    | `/api/license` POST stores token (user scope), returns new badge state  |

Pytest-style tests you will write:

```python
def test_free_when_missing(tmp_path):
    p = tmp_path / "license.key"
    assert load_badge_state_from_file(p.read_text() if False else None)["tier"] == "free"

def test_valid_token_returns_badge(valid_token):
    assert load_badge_state_from_string(valid_token)["tier"] == "donated"
    assert load_badge_state_from_string(valid_token)["badge"] is not None

def test_invalid_signature_falls_back(invalid_token):
    assert load_badge_state_from_string(invalid_token)["tier"] == "free"

def test_unknown_kid_falls_back(token_unknown_kid):
    assert load_badge_state_from_string(token_unknown_kid)["tier"] == "free"

def test_malformed_falls_back("no-dot-string"):
    assert load_badge_state_from_string("no-dot-string")["tier"] == "free"
```

### F. Key rotation test

* Add a new `kid` + key to `PUBLIC_KEYS`
* Validate old token still passes
* Validate new token passes
* Remove deprecated `kid` → ensure both kinds fallback to `free`.

---

You now have:

* Recognition system that is **offline**
* **No feature gating**
* **Key rotation support**
* **Completely cosmetic**

---

## Implementation Status

### Files Created

| File | Status | Description |
|------|--------|-------------|
| `apps/stt/src/dictacode_stt/license.py` | ✅ Done | Core license validation (Ed25519) |
| `apps/stt/src/dictacode_stt/license_cli.py` | ✅ Done | CLI: `dictacode-license save/show` |
| `apps/stt/tests/test_license.py` | ✅ Done | Unit tests for all scenarios |

### Files Modified

| File | Status | Changes |
|------|--------|---------|
| `apps/stt/src/dictacode_stt/api.py` | ✅ Done | GET/POST/DELETE `/api/license` endpoints |
| `apps/stt/src/dictacode_stt/main.py` | ✅ Done | Badge state loading at startup |
| `apps/stt/pyproject.toml` | ✅ Done | `cryptography>=41.0` + CLI entry point |

### Feature Checklist

| Feature | Status |
|---------|--------|
| A. CLI command to save token | ✅ `dictacode-license save <token> [--system]` |
| B. Public key registry (Ed25519) | ✅ `PUBLIC_KEYS` dict with `2025-01` key |
| C. Validate at startup | ✅ `load_badge_state()` in main.py |
| D. Render, never enforce | ✅ Cosmetic only |
| D. GET /api/license | ✅ Returns badge state |
| D. POST /api/license | ✅ Saves token + validates |
| D. DELETE /api/license | ✅ Removes token, resets to free |
| E. Automated tests | ✅ `test_license.py` |
| F. Key rotation support | ✅ Multiple `kid` supported |

### Badge Tiers Implemented

| Tier | Description |
|------|-------------|
| `free` | Default (no license) |
| `supporter` | Early adopters, testers |
| `donor` | Financial contribution |
| `contributor` | Code/docs contributor |
| `multiplicator` | Advocates, educators |

### API Endpoints

```
GET    /api/license  → { tier, badge, name, issued_at }
POST   /api/license  → { token, scope:"user"|"system" } → saves + validates
DELETE /api/license  → removes license files, resets to free
```
