# dictacode Architecture Diagrams (Solarized Light)

Palette (Solarized Light):
- Background: `#fdf6e3` (base3), `#eee8d5` (base2)
- Text: `#073642` (base02), `#657b83` (base00)
- Accents: `#268bd2` (blue), `#2aa198` (cyan), `#859900` (green), `#b58900` (yellow), `#cb4b16` (orange), `#dc322f` (red), `#d33682` (magenta), `#6c71c4` (violet)

---

## 1. System Overview (STT ↔ HID with IPC/API/CP)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83', 'secondaryColor': '#eee8d5', 'tertiaryColor': '#fdf6e3'}}}%%
flowchart LR
    subgraph STT["Pi5 / STT Service"]
      MIC[/"🎤 Mic"/]
      SVC["SttService\n(audio+ASR+LLM+transport)"]
      IPC["IPC Server\n(diag+state)"]
      API["FastAPI (API)"]
      CP["FastAPI (CP)"]
    end
    subgraph HID["Pi0 / HID Service"]
      HIDB["HID Bridge\n(UART/WiFi → USB HID)"]
    end
    PC[/"💻 Target PC"/]

    MIC --> SVC
    SVC -->|UART/WiFi| HIDB
    HIDB -->|USB HID| PC
    API <-->|UDS IPC| IPC
    CP --> API
    CLI[CLI tools] -->|UDS IPC| IPC

    style STT fill:#fdf6e3,stroke:#268bd2,color:#073642
    style HID fill:#fdf6e3,stroke:#2aa198,color:#073642
    style MIC fill:#eee8d5,stroke:#b58900,color:#073642
    style SVC fill:#eee8d5,stroke:#859900,color:#073642
    style IPC fill:#eee8d5,stroke:#268bd2,color:#073642
    style API fill:#eee8d5,stroke:#268bd2,color:#073642
    style CP fill:#eee8d5,stroke:#6c71c4,color:#073642
    style HIDB fill:#eee8d5,stroke:#2aa198,color:#073642
    style PC fill:#eee8d5,stroke:#6c71c4,color:#073642
    style CLI fill:#eee8d5,stroke:#cb4b16,color:#073642
```

---

## 2. Audio/ASR/LLM Pipeline

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83'}}}%%
flowchart LR
    MIC["Mic (ALSA)"]
    PORTS["AudioPortManager\n+ profiles"]
    BUF["RingBuffer\n16kHz mono"]
    RESAMPLE["Resampler"]
    ASR["ASR Adapter\nWhisper/Vosk"]
    LLM["LLM Postproc\n(optional)"]
    PROTO["Protocol\n(cmd/text messages)"]
    TX["Transport\nUART/WiFi/USB-serial"]

    MIC --> PORTS --> BUF --> RESAMPLE --> ASR --> LLM --> PROTO --> TX

    style MIC fill:#fdf6e3,stroke:#b58900,color:#073642
    style PORTS fill:#eee8d5,stroke:#268bd2,color:#073642
    style BUF fill:#eee8d5,stroke:#2aa198,color:#073642
    style RESAMPLE fill:#eee8d5,stroke:#2aa198,color:#073642
    style ASR fill:#eee8d5,stroke:#859900,color:#073642
    style LLM fill:#eee8d5,stroke:#6c71c4,color:#073642
    style PROTO fill:#eee8d5,stroke:#cb4b16,color:#073642
    style TX fill:#eee8d5,stroke:#2aa198,color:#073642
```

---

## 3. Components (Service + IPC + API/CP)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83', 'classText': '#073642'}}}%%
classDiagram
    class SttService {
        +state: SttState
        +diagnostics: DiagnosticsService
        +audio_manager: AudioPortManager
        +transcriber
        +llm_postprocessor
        +transport
        +run_continuous()
        +apply_profile(cfg)
    }
    class IPCServer {
        +diag.list/run/status/history
        +state.get/history
    }
    class APIApp {
        +/v1/api/* routes
        +/v1/docs OpenAPI
    }
    class CPApp {
        +/v1/cp* HTML
        +Static/templates
    }
    class DiagnosticsService
    class SttState
    class AudioPortManager
    class Transport
    class Transcriber
    class LlmPostProcessor

    SttService --> IPCServer
    APIApp --> IPCServer : IPC client
    CPApp --> APIApp : HTTP
    SttService --> DiagnosticsService
    SttService --> SttState
    SttService --> AudioPortManager
    SttService --> Transport
    SttService --> Transcriber
    SttService --> LlmPostProcessor

    style SttService fill:#eee8d5,stroke:#268bd2,color:#073642
    style IPCServer fill:#eee8d5,stroke:#268bd2,color:#073642
    style APIApp fill:#eee8d5,stroke:#268bd2,color:#073642
    style CPApp fill:#eee8d5,stroke:#6c71c4,color:#073642
    style DiagnosticsService fill:#eee8d5,stroke:#2aa198,color:#073642
    style SttState fill:#eee8d5,stroke:#859900,color:#073642
    style AudioPortManager fill:#eee8d5,stroke:#b58900,color:#073642
    style Transport fill:#eee8d5,stroke:#2aa198,color:#073642
    style Transcriber fill:#eee8d5,stroke:#859900,color:#073642
    style LlmPostProcessor fill:#eee8d5,stroke:#6c71c4,color:#073642
```

---

## 4. Observability Surfaces (Diagnostics + State)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83'}}}%%
flowchart LR
    subgraph Service["SttService"]
      DIAG["DiagnosticsService"]
      STATE["SttState\n+history\n+metrics"]
      IPC["IPC Server\n(diag.*, state.*)"]
    end

    API["API /v1/api/diagnostics/*\n/v1/api/service/state*"] -->|IPC client| IPC
    CLI["CLI (diag/state)"] -->|IPC client| IPC
    CP["Control Panel"] --> API
    MET["Prometheus\n/metrics"] --> STATE

    style Service fill:#fdf6e3,stroke:#268bd2,color:#073642
    style DIAG fill:#eee8d5,stroke:#2aa198,color:#073642
    style STATE fill:#eee8d5,stroke:#859900,color:#073642
    style IPC fill:#eee8d5,stroke:#268bd2,color:#073642
    style API fill:#eee8d5,stroke:#268bd2,color:#073642
    style CLI fill:#eee8d5,stroke:#cb4b16,color:#073642
    style CP fill:#eee8d5,stroke:#6c71c4,color:#073642
    style MET fill:#eee8d5,stroke:#b58900,color:#073642
```

---

## 5. API vs Control Panel (Split Apps)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83'}}}%%
flowchart TB
    API["API App\n/v1/api/*\n/v1/docs\nOpenAPI only"]
    WEB["CP App\n/v1/cp*\nHTML + Static\nno OpenAPI"]
    COMB["Combined ASGI\n(mount WEB into API)"]
    BROWSER[/"Browser"/]
    IPC["IPC client\n(state/diag)"]

    COMB --> API
    COMB --> WEB
    WEB -->|HTTP| API
    API -->|IPC calls| IPC
    BROWSER --> WEB

    style API fill:#eee8d5,stroke:#268bd2,color:#073642
    style WEB fill:#eee8d5,stroke:#6c71c4,color:#073642
    style COMB fill:#fdf6e3,stroke:#b58900,color:#073642
    style BROWSER fill:#eee8d5,stroke:#b58900,color:#073642
    style IPC fill:#eee8d5,stroke:#2aa198,color:#073642
```

---

## 6. Config & Profiles

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83'}}}%%
flowchart TB
    DEF["Packaged profiles\n/opt/dictacode/profiles"]
    DROP["Drop-ins\n/etc/dictacode/stt.d/profiles/"]
    LOADER["Profile Loader\n+ validation"]
    CFG["PipelineConfig\n(ASR, LLM, transport)"]
    SVC["SttService\napply_profile()"]

    DEF --> LOADER
    DROP --> LOADER
    LOADER --> CFG --> SVC

    style DEF fill:#eee8d5,stroke:#268bd2,color:#073642
    style DROP fill:#eee8d5,stroke:#b58900,color:#073642
    style LOADER fill:#eee8d5,stroke:#2aa198,color:#073642
    style CFG fill:#eee8d5,stroke:#859900,color:#073642
    style SVC fill:#eee8d5,stroke:#268bd2,color:#073642
```

---

## 7. Diagnostics Flow (IPC)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83', 'actorLineColor': '#657b83', 'actorBkg': '#eee8d5', 'actorBorder': '#268bd2', 'actorTextColor': '#073642'}}}%%
sequenceDiagram
    participant CLI as CLI/API
    participant IPC as IPC Server
    participant DIAG as DiagnosticsService

    CLI->>IPC: diag.run (JSON-RPC over UDS)
    IPC->>DIAG: run_all()
    DIAG-->>IPC: result (checks, status, history++)
    IPC-->>CLI: response {status, checks, history}
```

---

## 8. State Flow (Transitions + IPC)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83', 'actorLineColor': '#657b83', 'actorBkg': '#eee8d5', 'actorBorder': '#268bd2', 'actorTextColor': '#073642'}}}%%
sequenceDiagram
    participant SVC as SttService
    participant STATE as SttState
    participant MET as Metrics
    participant IPC as IPC Server
    participant API as API/CLI

    SVC->>STATE: transition_to(new_state, reason, source)
    STATE-->>STATE: record history (ring buffer)
    STATE-->>MET: record_state_transition
    API->>IPC: state.get / state.history
    IPC-->>API: {state...} / {history: [...]}
```

---

## 9. Deployment (Packages)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83'}}}%%
flowchart LR
    REPO["Repo"]
    BUILD["build-deb.sh"]
    DEB["dictacode-*.deb"]
    SCP["Copy to device"]
    DPKG["dpkg -i"]
    SERVICES["systemd services\n(dictacode-stt, dictacode-stt-api)"]

    REPO --> BUILD --> DEB --> SCP --> DPKG --> SERVICES

    style REPO fill:#eee8d5,stroke:#268bd2,color:#073642
    style BUILD fill:#eee8d5,stroke:#859900,color:#073642
    style DEB fill:#eee8d5,stroke:#2aa198,color:#073642
    style SCP fill:#eee8d5,stroke:#b58900,color:#073642
    style DPKG fill:#eee8d5,stroke:#cb4b16,color:#073642
    style SERVICES fill:#eee8d5,stroke:#268bd2,color:#073642
```

---

## 10. Directory Structure (Key Paths)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83'}}}%%
flowchart TB
    ROOT["repo/"]
    APPS["apps/"]
    STT["stt/"]
    HID["hid/"]
    OPS["ops/packaging/"]
    TEMPL["profiles/ (default)"]
    ETC["/etc/dictacode/stt.d/profiles/"]
    RUN["/run/dictacode/diag.sock"]

    ROOT --> APPS --> STT
    APPS --> HID
    ROOT --> OPS
    ROOT --> TEMPL
    ROOT --> RUN
    ETC --> STT

    style ROOT fill:#eee8d5,stroke:#268bd2,color:#073642
    style APPS fill:#eee8d5,stroke:#2aa198,color:#073642
    style STT fill:#eee8d5,stroke:#859900,color:#073642
    style HID fill:#eee8d5,stroke:#2aa198,color:#073642
    style OPS fill:#eee8d5,stroke:#6c71c4,color:#073642
    style TEMPL fill:#eee8d5,stroke:#b58900,color:#073642
    style ETC fill:#eee8d5,stroke:#b58900,color:#073642
    style RUN fill:#eee8d5,stroke:#cb4b16,color:#073642
```

---

## 11. Boot Sequence (Systemd)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83', 'actorLineColor': '#657b83', 'actorBkg': '#eee8d5', 'actorBorder': '#268bd2', 'actorTextColor': '#073642'}}}%%
sequenceDiagram
    participant SYS as systemd
    participant STT as dictacode-stt
    participant CFG as Profiles/Config
    participant IPC as IPC Server
    participant API as dictacode-stt-api

    SYS->>STT: start service
    STT->>CFG: load config + profile
    STT->>STT: init audio/ASR/LLM/transport
    STT->>IPC: start IPC (diag+state)
    SYS->>API: start API (optional unit)
    API->>IPC: connect for diag/state
    STT-->>SYS: READY (sd_notify)
```

---

## 12. Error Handling (High-Level)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83'}}}%%
flowchart TB
    ERR["Error Detected"]
    TYPE{"Type?"}
    MIC["Audio/Device"]
    ASR["ASR/Model"]
    LINK["Transport/Link"]
    RETRY["Retry/Backoff"]
    PAUSE["Pause/Degrade"]
    FAIL["Fail & Log"]
    RESTART["systemd restart"]

    ERR --> TYPE
    TYPE -->|mic missing| MIC
    TYPE -->|model fail| ASR
    TYPE -->|link broken| LINK
    MIC --> RETRY
    ASR --> PAUSE
    LINK --> RETRY
    RETRY -->|max| FAIL
    PAUSE --> FAIL
    FAIL --> RESTART

    style ERR fill:#fdf6e3,stroke:#dc322f,color:#073642
    style TYPE fill:#eee8d5,stroke:#b58900,color:#073642
    style MIC fill:#eee8d5,stroke:#cb4b16,color:#073642
    style ASR fill:#eee8d5,stroke:#cb4b16,color:#073642
    style LINK fill:#eee8d5,stroke:#cb4b16,color:#073642
    style RETRY fill:#eee8d5,stroke:#2aa198,color:#073642
    style PAUSE fill:#eee8d5,stroke:#6c71c4,color:#073642
    style FAIL fill:#eee8d5,stroke:#dc322f,color:#073642
    style RESTART fill:#eee8d5,stroke:#859900,color:#073642
```

---

## 13. Diagnostics via API (IPC-backed)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83', 'actorBkg': '#eee8d5', 'actorTextColor': '#073642', 'noteBkgColor': '#eee8d5', 'noteBorderColor': '#268bd2'}}}%%
sequenceDiagram
    participant Browser as CP/API Caller
    participant API as FastAPI (/v1)
    participant IPC as IPC Client
    participant SVC as IPC Server
    participant DIAG as DiagnosticsService

    Browser->>API: GET /v1/api/diagnostics/status
    API->>IPC: diag.status (UDS)
    IPC->>SVC: diag.status
    SVC->>DIAG: quick_status()
    DIAG-->>SVC: overall/passed/failed/warnings
    SVC-->>IPC: result
    IPC-->>API: result
    API-->>Browser: JSON {healthy,...}
```

---

## 14. State via CLI (IPC-backed)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83', 'actorBkg': '#eee8d5', 'actorTextColor': '#073642'}}}%%
sequenceDiagram
    participant CLI as dictacode-stt-state
    participant IPC as IPC Client
    participant SVC as IPC Server
    participant STATE as SttState

    CLI->>IPC: state.get
    IPC->>SVC: state.get
    SVC->>STATE: to_dict()
    STATE-->>SVC: {state, failure_reason,...}
    SVC-->>IPC: result
    IPC-->>CLI: result
    CLI-->>CLI: render table/JSON
```

---

## 15. Profile Apply Flow

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83', 'actorBkg': '#eee8d5', 'actorTextColor': '#073642'}}}%%
sequenceDiagram
    participant CP as Control Panel
    participant API as FastAPI (/v1)
    participant SVC as SttService
    participant ASR as Transcriber Factory
    participant LLM as LLM Factory

    CP->>API: POST /v1/api/profile/apply {profile: "whisper_local"}
    API->>SVC: apply_profile(profile)
    SVC->>SVC: pause/maintenance
    SVC->>ASR: build transcriber (per profile)
    SVC->>LLM: build postproc (per profile)
    SVC-->>SVC: swap components, update state.profile
    SVC-->>API: ok
    API-->>CP: 200 {profile:"whisper_local"}
```

---

## 16. Metrics Scrape (State)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83', 'actorBkg': '#eee8d5', 'actorTextColor': '#073642'}}}%%
sequenceDiagram
    participant PROM as Prometheus
    participant API as FastAPI /metrics
    participant MET as Metrics
    participant STATE as SttState

    STATE-->>MET: record_state_transition(old,new)
    loop scrape interval
      PROM->>API: GET /metrics
      API->>MET: export metrics text
      MET-->>API: state gauges/counters
      API-->>PROM: text/plain (Prometheus format)
    end
```

---

## 17. IPC Error Handling

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83', 'actorBkg': '#eee8d5', 'actorTextColor': '#073642'}}}%%
sequenceDiagram
    participant Client as API/CLI IPC client
    participant IPC as IPC Server

    Client->>IPC: diag.run
    IPC-->>Client: error {code:-32601,msg:"Method not found"} (if unsupported)
    Note over Client: Fallback? surface 503/clear error
```

---

## 18. CP Page Load

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83', 'actorBkg': '#eee8d5', 'actorTextColor': '#073642'}}}%%
sequenceDiagram
    participant Browser
    participant WEB as CP App
    participant API as API App
    participant IPC as IPC Client
    participant SVC as IPC Server

    Browser->>WEB: GET /v1/cp
    WEB-->>Browser: HTML + JS
    Browser->>API: GET /v1/api/service/state
    API->>IPC: state.get
    IPC->>SVC: state.get
    SVC-->>IPC: state dict
    IPC-->>API: state
    API-->>Browser: JSON state
    Browser-->>Browser: render state in CP
```
