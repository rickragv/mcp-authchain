@echo off
REM Start all services locally (without Docker)
REM Requires: Python 3.12+ (conda env "mcp-auth"), Node.js 18+, Ollama running

cd /d "%~dp0\.."

IF NOT EXIST .env (
    echo ERROR: .env file not found. Copy .env.example and configure it:
    echo   copy .env.example .env
    exit /b 1
)

IF NOT EXIST .secrets\firebase-service-account.json (
    echo ERROR: .secrets\firebase-service-account.json not found.
    echo   Place your Firebase service account JSON there.
    exit /b 1
)

REM Use conda env python if available, else system python
WHERE conda >nul 2>&1 && (
    FOR /F "tokens=*" %%i IN ('conda run -n mcp-auth where python 2^>nul') DO SET PYTHON=%%i
)
IF NOT DEFINED PYTHON SET PYTHON=python
SET PYTHONPATH=.

echo Starting MCP Auth Demo...
echo.

echo [1/3] Starting MCP server on :8001...
start "MCP Server" cmd /c "%PYTHON% -m uvicorn run_mcp_server:app --host 0.0.0.0 --port 8001"
timeout /t 3 /nobreak >nul

echo [2/3] Starting Agent API on :8000...
start "Agent API" cmd /c "%PYTHON% -m uvicorn run_agent_api:app --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul

echo [3/3] Starting Frontend on :5173...
start "Frontend" cmd /c "cd frontend && npx vite --host"

echo.
echo All services started:
echo   Frontend:   http://localhost:5173
echo   Agent API:  http://localhost:8000
echo   MCP Server: http://localhost:8001
echo.
echo Close the opened terminal windows to stop services.
pause
