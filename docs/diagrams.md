# dictacode Architecture Diagrams

Solarized Light palette:
- Background: `#fdf6e3` (base3), `#eee8d5` (base2)
- Text: `#657b83` (base00), `#073642` (base02)
- Accents: `#268bd2` (blue), `#2aa198` (cyan), `#859900` (green), `#b58900` (yellow), `#cb4b16` (orange), `#dc322f` (red), `#d33682` (magenta), `#6c71c4` (violet)

---

## 1. System Overview

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83', 'secondaryColor': '#eee8d5', 'tertiaryColor': '#fdf6e3'}}}%%
flowchart LR
    subgraph Pi5["Pi5 (STT Node)"]
        MIC[/"🎤 Mic"/]
        STT["STT Engine"]
    end
    subgraph Pi0["Pi Zero (HID Node)"]
        HID["HID Bridge"]
    end
    PC[/"💻 Target PC"/]

    MIC --> STT
    STT -->|UART| HID
    HID -->|USB HID| PC

    style Pi5 fill:#fdf6e3,stroke:#268bd2,color:#073642
    style Pi0 fill:#fdf6e3,stroke:#2aa198,color:#073642
    style MIC fill:#eee8d5,stroke:#b58900,color:#073642
    style STT fill:#eee8d5,stroke:#859900,color:#073642
    style HID fill:#eee8d5,stroke:#2aa198,color:#073642
    style PC fill:#eee8d5,stroke:#6c71c4,color:#073642
```

---

## 2. Audio Pipeline

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83'}}}%%
flowchart LR
    MIC["USB Mic<br/>hw:0,0"]
    ALSA["ALSA<br/>sounddevice"]
    BUF["Audio Buffer<br/>16kHz mono"]
    STT["STT Engine"]

    MIC -->|PCM| ALSA
    ALSA -->|chunks| BUF
    BUF -->|stream| STT

    style MIC fill:#fdf6e3,stroke:#b58900,color:#073642
    style ALSA fill:#fdf6e3,stroke:#268bd2,color:#073642
    style BUF fill:#fdf6e3,stroke:#2aa198,color:#073642
    style STT fill:#fdf6e3,stroke:#859900,color:#073642
```

---

## 3. STT Engine Adapters

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83', 'classText': '#073642'}}}%%
classDiagram
    class STTEngine {
        <<abstract>>
        +transcribe_stream(audio) Iterator~str~
        +transcribe_file(path) str
    }
    class WhisperCpp {
        -binary_path: str
        -model_path: str
        +transcribe_stream()
        +transcribe_file()
    }
    class Vosk {
        -model_path: str
        +transcribe_stream()
        +transcribe_file()
    }
    class CloudSTT {
        -provider: str
        -credentials: str
        +transcribe_stream()
        +transcribe_file()
    }

    STTEngine <|-- WhisperCpp : implements
    STTEngine <|-- Vosk : implements
    STTEngine <|-- CloudSTT : implements

    style STTEngine fill:#fdf6e3,stroke:#268bd2,color:#073642
    style WhisperCpp fill:#eee8d5,stroke:#859900,color:#073642
    style Vosk fill:#eee8d5,stroke:#2aa198,color:#073642
    style CloudSTT fill:#eee8d5,stroke:#6c71c4,color:#073642
```

---

## 4. Transport Adapters

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83'}}}%%
classDiagram
    class Transport {
        <<abstract>>
        +connect() void
        +send(text: str) void
        +close() void
    }
    class UARTTransport {
        -device: str
        -baud_rate: int
        +connect()
        +send()
        +close()
    }
    class WiFiTransport {
        -host: str
        -port: int
        +connect()
        +send()
        +close()
    }

    Transport <|-- UARTTransport : implements
    Transport <|-- WiFiTransport : implements

    style Transport fill:#fdf6e3,stroke:#268bd2,color:#073642
    style UARTTransport fill:#eee8d5,stroke:#b58900,color:#073642
    style WiFiTransport fill:#eee8d5,stroke:#2aa198,color:#073642
```

---

## 5. CLI Command Structure

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83'}}}%%
flowchart TB
    CLI["dictacode-stt"]
    RUN["run"]
    STATUS["status"]
    DISCOVER["discover"]
    TEST["test-*"]
    TESTMIC["test-mic"]
    TESTSTT["test-stt"]
    TESTUART["test-uart"]

    CLI --> RUN
    CLI --> STATUS
    CLI --> DISCOVER
    CLI --> TEST
    TEST --> TESTMIC
    TEST --> TESTSTT
    TEST --> TESTUART

    style CLI fill:#fdf6e3,stroke:#268bd2,color:#073642
    style RUN fill:#eee8d5,stroke:#859900,color:#073642
    style STATUS fill:#eee8d5,stroke:#2aa198,color:#073642
    style DISCOVER fill:#eee8d5,stroke:#b58900,color:#073642
    style TEST fill:#eee8d5,stroke:#cb4b16,color:#073642
    style TESTMIC fill:#eee8d5,stroke:#d33682,color:#073642
    style TESTSTT fill:#eee8d5,stroke:#d33682,color:#073642
    style TESTUART fill:#eee8d5,stroke:#d33682,color:#073642
```

---

## 6. Configuration Loading

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83'}}}%%
flowchart TB
    ENV["$DICTACODE_INVENTORY"]
    ETC["/etc/dictacode/inventory.yaml"]
    LOADER["Config Loader"]
    ROLE["Find by role<br/>(stt or hid)"]
    CONFIG["Device Config"]

    ENV -->|if set| LOADER
    ETC -->|default| LOADER
    LOADER --> ROLE
    ROLE --> CONFIG

    style ENV fill:#fdf6e3,stroke:#b58900,color:#073642
    style ETC fill:#fdf6e3,stroke:#268bd2,color:#073642
    style LOADER fill:#fdf6e3,stroke:#2aa198,color:#073642
    style ROLE fill:#fdf6e3,stroke:#859900,color:#073642
    style CONFIG fill:#fdf6e3,stroke:#6c71c4,color:#073642
```

---

## 7. Message Flow (Sequence)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83', 'actorLineColor': '#657b83', 'actorBkg': '#eee8d5', 'actorBorder': '#268bd2', 'actorTextColor': '#073642', 'noteBkgColor': '#eee8d5', 'noteTextColor': '#073642', 'noteBorderColor': '#b58900', 'signalColor': '#657b83', 'signalTextColor': '#073642'}}}%%
sequenceDiagram
    participant M as Mic
    participant S as STT Engine
    participant U as UART TX
    participant H as HID Bridge
    participant P as Target PC

    M->>S: audio chunks
    S->>S: transcribe
    S->>U: text
    U->>H: send over serial
    H->>H: text → keycodes
    H->>P: HID report

    Note over M,S: Pi5
    Note over H,P: Pi Zero
```

---

## 8. Boot Sequence

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83', 'actorLineColor': '#657b83', 'actorBkg': '#eee8d5', 'actorBorder': '#268bd2', 'actorTextColor': '#073642', 'noteBkgColor': '#eee8d5', 'noteTextColor': '#073642', 'noteBorderColor': '#859900', 'signalColor': '#657b83', 'signalTextColor': '#073642'}}}%%
sequenceDiagram
    participant SYS as systemd
    participant STT as dictacode-stt
    participant CFG as Config
    participant MIC as Mic
    participant UART as UART

    SYS->>STT: start service
    STT->>CFG: load inventory.yaml
    CFG-->>STT: device config (role=stt)
    STT->>MIC: open hw:0,0
    STT->>UART: open /dev/serial0
    STT->>STT: enter main loop
    Note over STT: ready for dictation
```

---

## 9. Error Handling

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83'}}}%%
flowchart TB
    ERR["Error Detected"]
    TYPE{"Error Type?"}
    MIC_ERR["Mic Error"]
    STT_ERR["STT Error"]
    UART_ERR["UART Error"]
    RETRY["Retry with backoff"]
    HALT["Halt & Log"]
    RESTART["systemd restart"]

    ERR --> TYPE
    TYPE -->|mic disconnected| MIC_ERR
    TYPE -->|model failed| STT_ERR
    TYPE -->|serial broken| UART_ERR
    MIC_ERR --> RETRY
    STT_ERR --> HALT
    UART_ERR --> RETRY
    RETRY -->|max attempts| HALT
    HALT --> RESTART

    style ERR fill:#fdf6e3,stroke:#dc322f,color:#073642
    style TYPE fill:#fdf6e3,stroke:#b58900,color:#073642
    style MIC_ERR fill:#eee8d5,stroke:#cb4b16,color:#073642
    style STT_ERR fill:#eee8d5,stroke:#cb4b16,color:#073642
    style UART_ERR fill:#eee8d5,stroke:#cb4b16,color:#073642
    style RETRY fill:#eee8d5,stroke:#2aa198,color:#073642
    style HALT fill:#eee8d5,stroke:#dc322f,color:#073642
    style RESTART fill:#eee8d5,stroke:#859900,color:#073642
```

---

## 10. Web Panel Architecture (Future)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83'}}}%%
flowchart LR
    subgraph Pi5
        STT["STT Daemon"]
        API["FastAPI"]
        WEB["Web UI"]
    end
    BROWSER[/"Browser"/]

    STT <-->|status/control| API
    API --> WEB
    BROWSER -->|HTTP| WEB

    style Pi5 fill:#fdf6e3,stroke:#268bd2,color:#073642
    style STT fill:#eee8d5,stroke:#859900,color:#073642
    style API fill:#eee8d5,stroke:#2aa198,color:#073642
    style WEB fill:#eee8d5,stroke:#6c71c4,color:#073642
    style BROWSER fill:#eee8d5,stroke:#b58900,color:#073642
```

---

## 11. Deployment Flow

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83'}}}%%
flowchart LR
    REPO["Git Repo"]
    BUILD["build-deb.sh"]
    DEB["dictacode-bootstrap.deb"]
    SCP["scp to device"]
    DPKG["dpkg -i"]
    INSTALLED["Installed"]

    REPO --> BUILD
    BUILD --> DEB
    DEB --> SCP
    SCP --> DPKG
    DPKG --> INSTALLED

    style REPO fill:#fdf6e3,stroke:#268bd2,color:#073642
    style BUILD fill:#fdf6e3,stroke:#859900,color:#073642
    style DEB fill:#fdf6e3,stroke:#2aa198,color:#073642
    style SCP fill:#fdf6e3,stroke:#b58900,color:#073642
    style DPKG fill:#fdf6e3,stroke:#cb4b16,color:#073642
    style INSTALLED fill:#fdf6e3,stroke:#859900,color:#073642
```

---

## 12. Directory Structure

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#fdf6e3', 'primaryTextColor': '#073642', 'primaryBorderColor': '#268bd2', 'lineColor': '#657b83'}}}%%
flowchart TB
    ROOT["dictacode/"]
    APPS["apps/"]
    STT["stt/"]
    HID["hid/"]
    CONFIG["config/"]
    OPS["ops/"]
    SANDBOX["sandbox/"]
    SRC["src/"]

    ROOT --> APPS
    ROOT --> CONFIG
    ROOT --> OPS
    APPS --> STT
    APPS --> HID
    STT --> SANDBOX
    STT --> SRC

    style ROOT fill:#fdf6e3,stroke:#268bd2,color:#073642
    style APPS fill:#eee8d5,stroke:#859900,color:#073642
    style STT fill:#eee8d5,stroke:#2aa198,color:#073642
    style HID fill:#eee8d5,stroke:#2aa198,color:#073642
    style CONFIG fill:#eee8d5,stroke:#b58900,color:#073642
    style OPS fill:#eee8d5,stroke:#6c71c4,color:#073642
    style SANDBOX fill:#eee8d5,stroke:#cb4b16,color:#073642
    style SRC fill:#eee8d5,stroke:#859900,color:#073642
```
