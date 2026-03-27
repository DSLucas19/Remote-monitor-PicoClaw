# Remote Monitor Dashboard

Dashboard Control Plane for **MetaClaw** and **PicoClaw** on Windows.

## Architecture
- **Machine A**: runs `FastAPI` backend + React frontend + MetaClaw/PicoClaw.
- **Machine B/C/...**: access dashboard via HTTPS domain (recommended: Cloudflare Tunnel).
- Access control: API Key -> short-lived JWT session.

## Project Structure
- `backend/`: FastAPI APIs, auth, process manager, heartbeat, gateway auto-connect, WebSocket logs.
- `frontend/`: React/Vite UI for status, control actions, key management, and live console.

## Backend Setup
1. Create virtual environment and install dependencies:
   - `cd backend`
   - `py -m venv .venv`
   - `.venv\Scripts\activate`
   - `pip install -r requirements.txt`
2. Copy config:
   - `copy .env.example .env`
3. Edit `.env`:
   - Set `JWT_SECRET`
   - Set strong `INITIAL_ADMIN_KEY`
   - Confirm service paths/commands.
4. Start API:
   - `uvicorn app.main:app --host 0.0.0.0 --port 8080`

## Frontend Setup
1. `cd frontend`
2. `npm install`
3. Copy config:
   - `copy .env.example .env`
4. Start UI:
   - `npm run dev`

For production, run `npm run build` and serve static assets via your preferred web server.

## First Login
1. Open UI.
2. Paste `INITIAL_ADMIN_KEY`.
3. Create named keys for each machine/user in **API Keys** panel.
4. Revoke keys anytime from dashboard.

## Service Control Rules
- `online_managed`: process started by dashboard, supports full Start/Stop/Restart flow.
- `online_external`: process detected running outside dashboard, dashboard is monitor-only.
- For `picoclaw start`, backend ensures `metaclaw` is reachable first.

## Remote Access (Cloudflare Tunnel Recommended)
1. Install `cloudflared` on Machine A.
2. Create tunnel route to dashboard frontend/backend host.
3. Use tunnel domain from any machine and sign in with valid key.

## API Overview
- `POST /api/auth/session`
- `DELETE /api/auth/session`
- `GET /api/keys`
- `POST /api/keys`
- `POST /api/keys/{id}/revoke`
- `GET /api/status`
- `POST /api/services/{metaclaw|picoclaw}/start`
- `POST /api/services/{metaclaw|picoclaw}/stop`
- `POST /api/services/{metaclaw|picoclaw}/restart`
- `POST /api/services/picoclaw/gateway/connect`
- `GET /api/logs`
- `WS /ws/logs?token=...`

