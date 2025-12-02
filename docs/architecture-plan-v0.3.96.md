# dictacode Architecture Plan v0.3.96 — Hardware/Software Inventory (CycloneDX SBOM)

## Status
- [ ] Define CycloneDX profile (fields/types/naming) for dictacode deployments.
- [ ] Inventory all hardware (STT Pi, HID Pi, USB mic/audio interface, HID gadget) as `device` components.
- [ ] Inventory OS images and apps (dictacode-stt, dictacode-hid) as software components with versions/purls.
- [ ] Model dependencies: product → devices; device → OS/apps; device → attached peripherals.
- [ ] Produce/validate a single CycloneDX JSON BOM per release/environment.

---

## Prerequisites
- Decide canonical bom-ref naming (e.g., `product:dictacode`, `hw:stt-pi`, `hw:hid-pi`, `sw:os-stt`, `sw:app-stt`, `sw:app-hid`).
- Collect authoritative versions (use VERSIONS file, pyproject versions) and hardware IDs (serial/MAC/location).
- Choose validation target: CycloneDX JSON specVersion 1.7.

---

## Scope
- Hardware: STT host, HID host, attached audio/HID peripherals, other sensors if present.
- Software: OS images, dictacode-stt app, dictacode-hid app, optional key libraries if desired.
- Relationships: “runs on” / “attached to” captured via `dependencies.dependsOn`.

---

## Design
- Format: CycloneDX JSON, `bomFormat="CycloneDX"`, `specVersion="1.7"`, single file per product snapshot.
- Components:
  - Product component representing the full deployment.
  - Hardware as `type="device"` with properties: role (stt/hid), serial/MAC, location, connection hints.
  - Software as `type="operating-system"` (OS) and `type="application"` (dictacode-stt/hid) with `version`, `supplier`, optional `purl`.
  - Optional: key libraries as `type="library"` if deeper SBOM needed.
- Dependencies:
  - Product dependsOn all hardware.
  - Each hardware device dependsOn its OS and installed apps.
  - Hardware can dependOn peripherals (e.g., `hw:stt-pi` → `hw:usb-mic-1`).
- Metadata: `serialNumber` (UUID), `timestamp`, `metadata.component` set to product component.

---

### minimal profile schema:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/envmonitor-bom-profile.json",
  "title": "EnvMonitor CycloneDX Profile",
  "type": "object",
  "required": ["bomFormat", "specVersion", "metadata", "components", "dependencies"],
  "properties": {
    "bomFormat": { "const": "CycloneDX" },
    "specVersion": { "type": "string" },

    "metadata": {
      "type": "object",
      "required": ["component"],
      "properties": {
        "component": {
          "type": "object",
          "required": ["bom-ref", "type", "name", "version"],
          "properties": {
            "bom-ref": { "type": "string" },
            "type": { "const": "device" },
            "name": { "type": "string" },
            "version": { "type": "string" },
            "description": { "type": "string" }
          },
          "additionalProperties": true
        }
      },
      "additionalProperties": true
    },

    "components": {
      "type": "array",
      "minItems": 1,
      "items": { "$ref": "#/$defs/component" }
    },

    "dependencies": {
      "type": "array",
      "minItems": 1,
      "items": { "$ref": "#/$defs/dependency" }
    }
  },
  "additionalProperties": true,

  "$defs": {
    "component": {
      "type": "object",
      "required": ["bom-ref", "type", "name"],
      "properties": {
        "bom-ref": { "type": "string" },
        "type": {
          "type": "string",
          "enum": ["device", "operating-system", "application", "library"]
        },
        "name": { "type": "string" },
        "version": { "type": "string" },
        "supplier": {
          "type": "object",
          "properties": {
            "name": { "type": "string" }
          },
          "additionalProperties": true
        },
        "properties": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["name", "value"],
            "properties": {
              "name": { "type": "string" },
              "value": { "type": "string" }
            },
            "additionalProperties": true
          }
        }
      },
      "additionalProperties": true
    },

    "dependency": {
      "type": "object",
      "required": ["ref"],
      "properties": {
        "ref": { "type": "string" },
        "dependsOn": {
          "type": "array",
          "items": { "type": "string" }
        }
      },
      "additionalProperties": true
    }
  }
}
```


---

## Implementation Phases

### Phase 1: Profile & Naming
1. Publish a one-page profile: required fields (type/name/version/supplier), allowed types, bom-ref naming scheme, required properties (role, serial/MAC, location).
2. Add schema link and validation instructions.

### Phase 2: Data Collection
1. Gather hardware identifiers (serials/MACs/roles/locations) for STT/HID hosts and peripherals.
2. Gather software versions (OS image, dictacode-stt/hid from VERSIONS/pyproject).

### Phase 3: BOM Assembly
1. Generate `bom/dictacode-<env>-<date>.json` with components and dependencies per the profile.
2. Ensure product → devices → OS/apps graph is complete; add peripheral links where applicable.

### Phase 4: Validation & CI
1. Validate against CycloneDX JSON schema (v1.7).
2. Add CI check to reject missing required fields or unlinked components.

---

## Testing
- Schema validation passes for the generated BOM.
- All components reachable from product via dependencies (no orphans).
- Versions match VERSIONS/pyproject; hardware properties populated (role/serial/MAC/location).
- Spot-check: device dependsOn OS + app; product dependsOn both STT and HID devices.

---

## Open Questions
- Do we include detailed library-level components now or keep to apps/OS only?
- How to capture environment-specific data (hostnames, IPs) without polluting release BOMs? (Consider separate env overlay or properties flag.)*** End Patch

## 4. Minimal rules for your internal “schema”

You can either:

* Use the **official CycloneDX JSON schema** directly, plus:
* Add these **project rules** (the “profile”) that devs must follow:

**Required:**

* `bomFormat = "CycloneDX"`
* `specVersion` present
* `metadata.component` representing the product
* Every component:

  * `bom-ref`, `type`, `name`
* `dependencies` connecting:

  * product → all device components
  * each device → its OS + app components

**Conventions:**

* Hardware:

  * `type = "device"`
  * Serial, MAC, role, location in `properties` with `envmonitor:*` names.
* OS:

  * `type = "operating-system"`
* Your app:

  * `type = "application"`
* Other important packages:

  * `type = "library"` or `application` as appropriate.

---
