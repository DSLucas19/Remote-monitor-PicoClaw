@echo off
setlocal enabledelayedexpansion

REM ──────────────────────────────────────────────
REM  Remote Monitor Dashboard — Quick Setup (Windows)
REM ──────────────────────────────────────────────

echo.
echo  ┌──────────────────────────────────────────┐
echo  │   Remote Monitor Dashboard — Setup        │
echo  └──────────────────────────────────────────┘
echo.

REM ── Generate secrets ──
set "JWT_SECRET="
set "ADMIN_KEY="

echo [1/4] Generating secrets...
for /f "delims=" %%i in ('python -c "import secrets; print(secrets.token_urlsafe(48))"') do set "JWT_SECRET=%%i"
for /f "delims=" %%i in ('python -c "import secrets; print('rmk_' + secrets.token_urlsafe(32))"') do set "ADMIN_KEY=%%i"

if "%JWT_SECRET%"=="" (
    echo ERROR: Python is required. Install from https://python.org
    exit /b 1
)

echo   JWT_SECRET generated.
echo   Initial admin key: %ADMIN_KEY%
echo   SAVE THIS KEY — you'll need it to log in!
echo.

REM ── Backend setup ──
echo [2/4] Setting up backend...
cd backend

if not exist .env (
    powershell -Command "(Get-Content .env.example) -replace '^JWT_SECRET=.*', 'JWT_SECRET=%JWT_SECRET%' -replace '^INITIAL_ADMIN_KEY=.*', 'INITIAL_ADMIN_KEY=%ADMIN_KEY%' | Set-Content .env"
    echo   Created backend\.env with auto-generated secrets
) else (
    echo   backend\.env already exists, skipping
)

echo   Installing Python dependencies...
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
cd ..

REM ── Frontend setup ──
echo.
echo [3/4] Setting up frontend...
cd frontend
npm install --silent
cd ..

REM ── Summary ──
echo.
echo [4/4] Setup complete!
echo.
echo To start the dashboard:
echo.
echo   Terminal 1 — Backend:
echo     cd backend ^&^& uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
echo.
echo   Terminal 2 — Frontend:
echo     cd frontend ^&^& npm run dev
echo.
echo Then open http://localhost:5173 and sign in with your admin key.
echo.
echo Happy monitoring!
