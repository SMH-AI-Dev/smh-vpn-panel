# SMH Panel — Development Guide

## Requirements

- Python 3.10–3.13 (this project was developed and tested with 3.13.12)
- No Node.js needed (the frontend is dependency-free vanilla JS)

## Setup (Windows PowerShell)

```powershell
cd smh-vpn-panel
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r app\requirements-dev.txt

# generate the Xray stats gRPC stubs (already committed; only needed if proto changes)
.\.venv\Scripts\python.exe -m grpc_tools.protoc -I proto --python_out=app\smhpanel\grpc_gen proto\xray_stats.proto
```

## Run the test suite

```powershell
.\.venv\Scripts\python.exe -m pytest app\tests -q
```

29 tests cover: share-link formats, Xray config builder, quota/delta accounting
(including counter resets), auth + CSRF + rate limiting, full API CRUD flow,
WireGuard config generation and `wg dump` parsing, Clash YAML output, and the
detailed server-specs snapshot.

## Run the panel in dev mode

Dev mode is automatic on non-Linux hosts (or when the root helper scripts are
absent): Xray/WireGuard system calls are simulated, configs are written under
`dev-data/`.

```powershell
$env:PYTHONPATH = "app"

# one-time: create DB + admin + dev configs
.\.venv\Scripts\python.exe -m smhpanel.cli init --admin-user admin --admin-pass devpass123 --public-host 127.0.0.1 --no-tls

# start the panel (http://127.0.0.1:2099)
.\.venv\Scripts\python.exe -m smhpanel --port 2099
```

## Layout

```
app/smhpanel/
  config.py            # config file + path resolution + dev/prod detection
  db.py, models.py     # SQLAlchemy (SQLite)
  security.py          # bcrypt, JWT sessions, CSRF, rate limiter
  api/                 # FastAPI routers (auth, inbounds, clients, settings, system, sub)
  services/
    xray_config.py     # pure DB->config builder (unit-tested)
    xray_manager.py    # apply (validates via helper) + version + firewall
    wireguard.py       # server/client confs, dump parsing, apply
    links.py, clash.py # share links + subscription formats
    traffic.py         # StatsService polling, delta tracker, quota enforcement
    helpers.py         # sudo helper runner (simulated in dev)
    stats_client.py    # generic gRPC call to Xray StatsService
  grpc_gen/            # generated protobuf (from ../../proto/xray_stats.proto)
  static/              # Persian RTL SPA (vanilla JS, no CDN)
  tests/               # pytest suite
deploy/                # systemd unit, sudo helpers, sudoers, sysctl, fail2ban
install.sh             # one-command production installer (Linux only)
```

## Design notes

- The panel never runs as root. It calls a fixed set of validated helper
  scripts through `sudo` (see `deploy/sudoers/smhpanel.sudoers`).
- Xray configs are written to a candidate file, validated with
  `xray run -test`, then atomically installed by the helper — a broken config
  never replaces a working one.
- Traffic counters from Xray reset on restart; `DeltaTracker` converts
  cumulative counters into deltas and handles resets.
