#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────
#  Remote Monitor Dashboard — Quick Setup
# ──────────────────────────────────────────────

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}${BOLD}"
echo "  ┌──────────────────────────────────────────┐"
echo "  │   Remote Monitor Dashboard — Setup        │"
echo "  └──────────────────────────────────────────┘"
echo -e "${NC}"

# ── Generate secrets ──
generate_secret() {
  python3 -c "import secrets; print(secrets.token_urlsafe(48))" 2>/dev/null || \
  python -c "import secrets; print(secrets.token_urlsafe(48))" 2>/dev/null || \
  openssl rand -base64 48 2>/dev/null | tr -d '=/+' | head -c 64
}

generate_key() {
  python3 -c "import secrets; print('rmk_' + secrets.token_urlsafe(32))" 2>/dev/null || \
  python -c "import secrets; print('rmk_' + secrets.token_urlsafe(32))" 2>/dev/null || \
  echo "rmk_$(openssl rand -base64 32 | tr -d '=/+' | head -c 43)"
}

# ── Backend setup ──
echo -e "${GREEN}[1/4] Setting up backend...${NC}"
cd backend

if [ ! -f .env ]; then
  JWT_SECRET=$(generate_secret)
  ADMIN_KEY=$(generate_key)

  sed -e "s|^JWT_SECRET=.*|JWT_SECRET=${JWT_SECRET}|" \
      -e "s|^INITIAL_ADMIN_KEY=.*|INITIAL_ADMIN_KEY=${ADMIN_KEY}|" \
      .env.example > .env

  echo -e "  ${YELLOW}Created backend/.env with auto-generated secrets${NC}"
  echo -e "  ${YELLOW}Your initial admin key: ${BOLD}${ADMIN_KEY}${NC}"
  echo -e "  ${YELLOW}Save this key — you'll need it to log in!${NC}"
else
  echo -e "  ${YELLOW}backend/.env already exists, skipping${NC}"
fi

echo -e "  Installing Python dependencies..."
python3 -m venv .venv 2>/dev/null || python -m venv .venv
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
else
  source .venv/Scripts/activate
fi
pip install -q -r requirements.txt

cd ..

# ── Frontend setup ──
echo -e "${GREEN}[2/4] Setting up frontend...${NC}"
cd frontend
npm install --silent
cd ..

# ── Summary ──
echo ""
echo -e "${GREEN}${BOLD}[3/4] Setup complete!${NC}"
echo ""
echo -e "${CYAN}To start the dashboard:${NC}"
echo ""
echo -e "  ${BOLD}Terminal 1 — Backend:${NC}"
echo "    cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload"
echo ""
echo -e "  ${BOLD}Terminal 2 — Frontend:${NC}"
echo "    cd frontend && npm run dev"
echo ""
echo -e "${CYAN}Then open ${BOLD}http://localhost:5173${NC}${CYAN} and sign in with your admin key.${NC}"
echo ""
echo -e "${GREEN}${BOLD}[4/4] Happy monitoring!${NC}"
