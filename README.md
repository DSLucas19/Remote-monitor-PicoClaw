<div align="center">

# Remote Monitor Dashboard

**A self-hosted control plane for managing MetaClaw and PicoClaw services on Windows.**

Real-time monitoring, service orchestration, live log streaming, and secure API key management — all from a single web interface.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React 18](https://img.shields.io/badge/React-18-61dafb.svg?logo=react&logoColor=black)](https://react.dev)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

## What It Does

Remote Monitor Dashboard turns your Windows machine into a managed service host:

| Feature | Description |
|---------|-------------|
| **Service Control** | Start, stop, and restart MetaClaw / PicoClaw processes with one click |
| **Live Console** | WebSocket-powered real-time log streaming with service filtering |
| **API Key Auth** | PBKDF2-HMAC-SHA256 hashed keys, session-based JWT access |
| **Gateway Auto-Connect** | Automatically connects PicoClaw to your gateway when it comes online |
| **Status Monitoring** | Health probes every 2 seconds with external process detection |
| **Multi-User Keys** | Create named, revocable API keys for each machine or team member |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Browser (Machine B)                     │
│                    http://localhost:5173                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               FastAPI Backend (Machine A)                    │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌───────────┐  │
│  │   Auth    │  │ Services │  │  Logs     │  │  Gateway   │  │
│  │  (JWT)   │  │ (Manage) │  │ (WebSocket)│  │  Client    │  │
│  └──────────┘  └──────────┘  └───────────┘  └───────────┘  │
│       │              │              │              │         │
│       ▼              ▼              ▼              ▼         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  SQLite Database                      │   │
│  └──────────────────────────────────────────────────────┘   │
│       │              │                                       │
│       ▼              ▼                                       │
│  ┌──────────┐  ┌──────────┐                                │
│  │ MetaClaw │  │ PicoClaw │   ← Process Manager            │
│  │  :30000  │  │  :18800  │                                │
│  └──────────┘  └──────────┘                                │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### One-Command Setup

```bash
# Unix / macOS
chmod +x setup.sh && ./setup.sh

# Windows
setup.bat
```

The setup script will:
1. Generate secure `JWT_SECRET` and `INITIAL_ADMIN_KEY`
2. Create `backend/.env` from template
3. Install Python and Node.js dependencies
4. Print your admin key — **save it!**

### Manual Setup

<details>
<summary><strong>Backend</strong></summary>

```bash
cd backend
python -m venv .venv
# Activate:
#   Unix:    source .venv/bin/activate
#   Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env    # or: copy .env.example .env
# Edit .env — set JWT_SECRET and INITIAL_ADMIN_KEY

# Run
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

</details>

<details>
<summary><strong>Frontend</strong></summary>

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** and sign in with your admin key.

For production: `npm run build` and serve the `dist/` folder.

</details>

## First Login

1. Open the dashboard in your browser
2. Paste your `INITIAL_ADMIN_KEY` to create a session
3. Go to **API Keys** and create named keys for each machine/user
4. Revoke keys anytime from the dashboard

## Configuration

All configuration lives in `backend/.env`. See [`.env.example`](backend/.env.example) for the full reference.

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET` | **Yes** | Session signing secret (generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`) |
| `INITIAL_ADMIN_KEY` | **Yes** | First login key (generate with `python -c "import secrets; print('rmk_' + secrets.token_urlsafe(32))"`) |
| `DATABASE_URL` | No | SQLite path (default: `sqlite:///./dashboard.db`) |
| `METACLAW_WORKDIR` | No | MetaClaw working directory |
| `METACLAW_COMMAND` | No | Command to start MetaClaw (default: `py -m metaclaw start`) |
| `PICOCLAW_WORKDIR` | No | PicoClaw working directory |
| `PICOCLAW_COMMAND` | No | Command to start PicoClaw (default: `picoclaw-launcher.exe`) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins (default: `*`) |
| `GATEWAY_AUTO_CONNECT_ENABLED` | No | Auto-connect PicoClaw to gateway (default: `true`) |

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/session` | Create a JWT session from API key |
| `DELETE` | `/api/auth/session` | Revoke current session |
| `GET` | `/api/keys` | List all API keys |
| `POST` | `/api/keys` | Create a new named API key |
| `POST` | `/api/keys/{id}/revoke` | Revoke a specific key |
| `GET` | `/api/status` | Get service statuses |
| `POST` | `/api/services/{name}/start` | Start a service |
| `POST` | `/api/services/{name}/stop` | Stop a service |
| `POST` | `/api/services/{name}/restart` | Restart a service |
| `POST` | `/api/services/picoclaw/gateway/connect` | Manual gateway connect |
| `GET` | `/api/logs` | Fetch buffered logs |
| `WS` | `/ws/logs?token=...` | Real-time log stream |

## Service States

| State | Badge | Description |
|-------|-------|-------------|
| `offline` | 🔴 | Process not running |
| `starting` | 🟡 | Process launching, health probe pending |
| `online_managed` | 🟢 | Running and managed by dashboard |
| `online_external` | 🟢 | Running but started externally (monitor-only) |
| `stopping` | 🟡 | Graceful shutdown in progress |
| `error` | 🔴 | Process crashed or failed to start |

## Remote Access

For accessing the dashboard from other machines:

### Cloudflare Tunnel (Recommended)

```bash
# Install cloudflared
# https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/

# Create tunnel
cloudflared tunnel --url http://localhost:5173
```

### SSH Tunnel

```bash
# From Machine B:
ssh -L 5173:localhost:5173 -L 8080:localhost:8080 user@machine-a
```

## Project Structure

```
Remote-monitor-PicoClaw/
├── backend/
│   ├── app/
│   │   ├── config.py          # Pydantic Settings with validation
│   │   ├── main.py            # FastAPI app factory
│   │   ├── database.py        # SQLAlchemy engine/session
│   │   ├── models.py          # ORM models (APIKey, AuditLog)
│   │   ├── security.py        # API key hashing (PBKDF2-HMAC-SHA256)
│   │   ├── deps.py            # Dependency injection
│   │   ├── routers/           # API route handlers
│   │   └── services/          # Process manager, log broker, gateway client
│   ├── tests/                 # Pytest test suite
│   ├── .env.example           # Configuration template
│   └── requirements.txt       # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.jsx            # Main React application
│   │   ├── styles.css         # Design system & styles
│   │   └── components/
│   │       └── ServiceCard.jsx # Service status card component
│   ├── index.html
│   └── package.json
├── setup.sh                   # Unix quick-setup script
├── setup.bat                  # Windows quick-setup script
└── README.md
```

## Security

- **API keys are hashed** with PBKDF2-HMAC-SHA256 (600,000 iterations) before storage
- **JWT sessions** expire after configurable duration (default: 120 minutes)
- **No plaintext secrets** — the app refuses to start without explicit `JWT_SECRET` and `INITIAL_ADMIN_KEY`
- **External process policy** — dashboard cannot stop/restart processes it didn't start
- **Audit logging** — key creation and revocation events are recorded

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, FastAPI, SQLAlchemy, Pydantic v2 |
| Frontend | React 18, Vite 7 |
| Database | SQLite (zero-config) |
| Auth | JWT (PyJWT), PBKDF2-HMAC-SHA256 |
| Real-time | WebSocket (FastAPI native) |

## License

MIT
