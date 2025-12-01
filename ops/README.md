# dictacode Operations & Monitoring

This directory contains configurations and dashboards for monitoring dictacode STT with Prometheus and Grafana (v0.2.13).

## Directory Structure

```
ops/
├── grafana/
│   └── dashboards/
│       └── dictacode-stt.json      # Grafana dashboard
├── prometheus/
│   ├── prometheus.yml              # Prometheus scrape config
│   └── rules/
│       └── dictacode.yml           # Alerting rules
└── README.md                       # This file
```

## Quick Start

### 1. Enable Metrics in dictacode STT

Start the service with metrics enabled:

```bash
# Via CLI flag
dictacode-stt --metrics --metrics-port 9100

# Or via API server
dictacode-stt-api --metrics --metrics-port 9100
```

The metrics endpoint will be available at:
- Service: `http://localhost:9100/metrics` (dedicated metrics server)
- API: `http://localhost:8000/metrics` (integrated with API)

### 2. Install Prometheus

#### Option A: Docker

```bash
docker run -d \
  --name prometheus \
  -p 9090:9090 \
  -v $(pwd)/ops/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml \
  -v $(pwd)/ops/prometheus/rules:/etc/prometheus/rules \
  prom/prometheus
```

#### Option B: Native Installation

```bash
# Debian/Ubuntu
sudo apt-get install prometheus

# Copy configuration
sudo cp ops/prometheus/prometheus.yml /etc/prometheus/
sudo cp ops/prometheus/rules/dictacode.yml /etc/prometheus/rules/

# Restart Prometheus
sudo systemctl restart prometheus
```

### 3. Install Grafana

#### Option A: Docker

```bash
docker run -d \
  --name=grafana \
  -p 3000:3000 \
  grafana/grafana
```

#### Option B: Native Installation

```bash
# Debian/Ubuntu
sudo apt-get install grafana

# Start Grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

### 4. Import Dashboard

1. Open Grafana: `http://localhost:3000` (default credentials: admin/admin)
2. Add Prometheus data source:
   - Go to **Configuration > Data Sources**
   - Click **Add data source**
   - Select **Prometheus**
   - URL: `http://localhost:9090` (or your Prometheus URL)
   - Click **Save & Test**
3. Import dashboard:
   - Go to **Create > Import**
   - Upload `ops/grafana/dashboards/dictacode-stt.json`
   - Select your Prometheus data source
   - Click **Import**

## Metrics Overview

### Counters

| Metric | Description | Labels |
|--------|-------------|--------|
| `dictacode_transcriptions_total` | Total transcription attempts | `status`, `transcriber` |
| `dictacode_hid_commands_total` | Total HID commands sent | `type` |
| `dictacode_audio_chunks_total` | Total audio chunks processed | - |
| `dictacode_transport_reconnects_total` | Total transport reconnections | `transport` |

### Histograms

| Metric | Description | Labels |
|--------|-------------|--------|
| `dictacode_transcription_duration_seconds` | Transcription duration | `transcriber` |
| `dictacode_audio_buffer_duration_seconds` | Audio buffer duration | - |

### Gauges

| Metric | Description |
|--------|-------------|
| `dictacode_audio_buffer_bytes` | Current audio buffer size |
| `dictacode_link_healthy` | HID link health (1=healthy, 0=unhealthy) |
| `dictacode_active_connections` | Number of active transport connections |
| `dictacode_transcription_queue_size` | Number of items in transcription queue |

## Alerting Rules

The following alerts are configured in `ops/prometheus/rules/dictacode.yml`:

### Critical Alerts

- **DictacodeHIDLinkDown**: HID link has been unhealthy for > 1 minute
- **DictacodeServiceDown**: Prometheus cannot scrape metrics (service is down)

### Warning Alerts

- **DictacodeHighErrorRate**: Transcription error rate > 10% for 5 minutes
- **DictacodeHighLatency**: 95th percentile latency > 5 seconds for 5 minutes
- **DictacodeNoTranscriptions**: No transcriptions for 10 minutes (service idle)
- **DictacodeReconnectStorm**: Transport reconnecting > 1x per 5 minutes
- **DictacodeAudioBufferHigh**: Audio buffer > 5MB for 2 minutes
- **DictacodeNoConnections**: No active transport connections for 5 minutes

## Dashboard Panels

The Grafana dashboard includes:

1. **Transcriptions per Minute**: Rate of transcription attempts by status
2. **Transcription Latency (p95)**: 95th percentile latency gauge
3. **HID Link Health**: Binary indicator (healthy/unhealthy)
4. **Audio Buffer Size**: Current buffer size over time
5. **Error Rate**: Percentage of failed transcriptions
6. **Active Connections**: Number of active transport connections
7. **Audio Chunks Processed**: Rate of audio chunk processing
8. **Transport Reconnects**: Reconnection rate by transport type
9. **HID Commands by Type**: Pie chart of command distribution
10. **Transcription Duration Distribution**: Heatmap of duration distribution

## Advanced Configuration

### Custom Scrape Interval

Edit `ops/prometheus/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'dictacode'
    scrape_interval: 10s  # Change from 15s to 10s
```

### Adding More Targets

For multiple dictacode instances:

```yaml
scrape_configs:
  - job_name: 'dictacode'
    static_configs:
      - targets:
          - 'dictacode-pi5:9100'
          - 'dictacode-pi0:9100'
          - 'dictacode-dev:9100'
```

### Alertmanager Integration

Configure Alertmanager in `ops/prometheus/prometheus.yml`:

```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - 'alertmanager:9093'
```

## Troubleshooting

### Metrics Not Appearing

1. Check service is running with `--metrics` flag:
   ```bash
   systemctl status dictacode-stt
   journalctl -u dictacode-stt -n 50
   ```

2. Verify metrics endpoint is accessible:
   ```bash
   curl http://localhost:9100/metrics
   ```

3. Check Prometheus targets:
   - Open `http://localhost:9090/targets`
   - Verify target is **UP** and green

### Dashboard Shows No Data

1. Verify Prometheus data source is configured correctly in Grafana
2. Check time range in dashboard (top-right corner)
3. Verify queries in dashboard panels match your metric names

### Alerts Not Firing

1. Check Prometheus rules are loaded:
   ```bash
   curl http://localhost:9090/api/v1/rules
   ```

2. Verify alert conditions in `ops/prometheus/rules/dictacode.yml`
3. Check Prometheus logs for rule evaluation errors

## Integration with Homelab

### With Existing Prometheus

If you already have Prometheus running:

1. Add dictacode scrape config to your existing `prometheus.yml`
2. Copy alert rules to your rules directory
3. Reload Prometheus configuration:
   ```bash
   kill -HUP $(pidof prometheus)
   # Or
   curl -X POST http://localhost:9090/-/reload
   ```

### With Docker Compose

Example `docker-compose.yml`:

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./ops/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./ops/prometheus/rules:/etc/prometheus/rules
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false

volumes:
  prometheus-data:
  grafana-data:
```

## Optional Dependencies

To use Prometheus metrics, install the optional dependency:

```bash
# Install with metrics support
pip install -e ".[metrics]"

# Or directly
pip install prometheus_client>=0.19
```

## Further Reading

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
- [v0.2.13 Architecture Plan](../docs/architecture-plan-v0.2.13.md)
