# Server Management Guide

Complete guide for managing Neighborhood AI servers, handling shutdowns, restarts, and common scenarios.

## Table of Contents
- [Quick Reference](#quick-reference)
- [Starting All Services](#starting-all-services)
- [Stopping All Services](#stopping-all-services)
- [Checking Service Status](#checking-service-status)
- [Common Scenarios](#common-scenarios)
- [Troubleshooting](#troubleshooting)

---

## Quick Reference

### Start Everything
```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Start Backend
python3 app.py

# Terminal 3: Start Frontend
cd frontend
npm start

# Terminal 4: Start Cloudflare Tunnel
./start-tunnel.sh
```

### Stop Everything
```bash
# Stop individual processes with Ctrl+C in each terminal
# OR kill all at once:
pkill ollama
pkill -f "python3 app.py"
pkill -f "react-scripts start"
pkill cloudflared
```

### Check Status
```bash
# Check what's running
pgrep -fl ollama        # Ollama status
pgrep -fl "python3"     # Backend status
pgrep -fl "node"        # Frontend status
pgrep -fl cloudflared   # Tunnel status

# Check ports
lsof -i :11434          # Ollama port
lsof -i :8000           # Backend port
lsof -i :3000           # Frontend port

# Test backend health
curl http://localhost:8000/api/health
```

---

## Starting All Services

### Method 1: Three-Terminal Workflow (Recommended)

This keeps each service in its own terminal so you can see logs.

**Terminal 1 - Ollama:**
```bash
ollama serve
```
Leave this running. You'll see logs like:
```
time=2026-01-05T11:30:00.000-05:00 level=INFO source=server.go:123 msg="Starting Ollama"
```

**Terminal 2 - Backend:**
```bash
cd /path/to/neighborhood-ai
python3 app.py
```
Leave this running. You'll see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

**Terminal 3 - Frontend:**
```bash
cd /path/to/neighborhood-ai/frontend
npm start
```
Leave this running. You'll see:
```
Compiled successfully!
You can now view neighborhood-ai-frontend in the browser.
  Local:            http://localhost:3000
```

**Terminal 4 - Cloudflare Tunnel (Optional, for remote access):**
```bash
cd /path/to/neighborhood-ai
./start-tunnel.sh
```
The tunnel URL will be displayed:
```
+--------------------------------------------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at:                                         |
|  https://random-words-here.trycloudflare.com                                              |
+--------------------------------------------------------------------------------------------+
```

### Method 2: Background Processes

Start everything in the background with logging:

```bash
# Start Ollama in background
ollama serve > /tmp/ollama.log 2>&1 &

# Start Backend in background
python3 app.py > /tmp/backend.log 2>&1 &

# Start Frontend in background
cd frontend && npm start > /tmp/frontend.log 2>&1 &

# Start Tunnel in background
./start-tunnel.sh &

# Monitor logs
tail -f /tmp/ollama.log     # Watch Ollama
tail -f /tmp/backend.log    # Watch Backend
tail -f /tmp/tunnel.log     # Watch Tunnel (created by script)
```

### Method 3: Using screen or tmux

If you want persistent sessions that survive disconnection:

**Using screen:**
```bash
# Create new session for each service
screen -S ollama -dm ollama serve
screen -S backend -dm python3 app.py
screen -S frontend -dm bash -c "cd frontend && npm start"
screen -S tunnel -dm ./start-tunnel.sh

# Attach to any session to see logs
screen -r ollama
# Press Ctrl+A, then D to detach

# List all sessions
screen -ls

# Kill a session
screen -X -S ollama quit
```

**Using tmux:**
```bash
# Create new session with 4 panes
tmux new-session -s neighborhood-ai \; \
  send-keys 'ollama serve' C-m \; \
  split-window -h \; \
  send-keys 'python3 app.py' C-m \; \
  split-window -v \; \
  send-keys 'cd frontend && npm start' C-m \; \
  select-pane -t 0 \; \
  split-window -v \; \
  send-keys './start-tunnel.sh' C-m

# Attach to session
tmux attach -t neighborhood-ai

# Detach: Press Ctrl+B, then D

# Kill session
tmux kill-session -t neighborhood-ai
```

---

## Stopping All Services

### Graceful Shutdown

Press `Ctrl+C` in each terminal window where services are running.

### Force Kill All Services

```bash
# Kill Ollama
pkill ollama

# Kill Backend
pkill -f "python3 app.py"
pkill -f uvicorn

# Kill Frontend
pkill -f "react-scripts start"
pkill -f "node.*react-scripts"

# Kill Tunnel
pkill cloudflared

# Verify all stopped
ps aux | grep -E "ollama|uvicorn|react-scripts|cloudflared"
```

### Kill by Port (if process won't die)

```bash
# Find and kill process on specific port
lsof -ti:11434 | xargs kill -9  # Ollama
lsof -ti:8000 | xargs kill -9   # Backend
lsof -ti:3000 | xargs kill -9   # Frontend
```

### Stop Individual Services

```bash
# Stop just Ollama
pkill ollama

# Stop just Backend
pkill -f "python3 app.py"

# Stop just Frontend
pkill -f "react-scripts start"

# Stop just Tunnel
pkill cloudflared
```

---

## Checking Service Status

### Quick Health Check

```bash
# Check if services are running
pgrep ollama && echo "✅ Ollama running" || echo "❌ Ollama stopped"
pgrep -f "python3 app.py" && echo "✅ Backend running" || echo "❌ Backend stopped"
pgrep -f "react-scripts" && echo "✅ Frontend running" || echo "❌ Frontend stopped"
pgrep cloudflared && echo "✅ Tunnel running" || echo "❌ Tunnel stopped"
```

### Detailed Process Information

```bash
# See full process details
pgrep -fl ollama
pgrep -fl "python3"
pgrep -fl "node"
pgrep -fl cloudflared

# Check ports in use
lsof -i :11434  # Ollama
lsof -i :8000   # Backend
lsof -i :3000   # Frontend
```

### API Health Endpoints

```bash
# Backend health check
curl http://localhost:8000/api/health

# Should return:
# {
#   "status": "healthy",
#   "service": "Neighborhood AI API",
#   "checks": {
#     "ollama": {"status": "running", "models_available": 5},
#     "projects": {"status": "ok", "count": 6}
#   }
# }

# Check specific project health
curl http://localhost:8000/api/projects/{project_id}/health

# List all projects
curl http://localhost:8000/api/projects
```

### Get Current Tunnel URL

```bash
# From log file
cat /tmp/tunnel.log | grep "Your quick Tunnel" -A 1

# Live monitoring
tail -f /tmp/tunnel.log
```

---

## Common Scenarios

### Scenario 1: Computer Shut Down / Restart

**What happens:**
- All services stop
- Frontend and tunnel URLs become inaccessible
- No data is lost (stored in `data/` directory)

**How to recover:**
```bash
# 1. Start Ollama
ollama serve &

# 2. Wait 5 seconds, then start Backend
sleep 5
python3 app.py &

# 3. Start Frontend
cd frontend
npm start &

# 4. Start Tunnel (if needed for remote access)
./start-tunnel.sh &
```

**Expected time:** 1-2 minutes for all services to be ready

### Scenario 2: IP Address Changed

**What happens:**
- Local network IP changes (e.g., from `192.168.1.100` to `192.168.20.53`)
- `localhost` addresses still work
- Tunnel URL remains the same (it proxies to localhost)

**What to do:**
```bash
# Nothing required! Services bind to localhost (127.0.0.1)
# Frontend dev server automatically shows new network IP:
# "On Your Network: http://192.168.20.53:3000"

# If you need the new IP:
ifconfig | grep "inet " | grep -v 127.0.0.1
# OR
hostname -I
```

**For remote access:**
- Tunnel URL doesn't change
- Update Netlify env var if tunnel was restarted (new URL)

### Scenario 3: Tunnel URL Changed

**What happens:**
- Cloudflare free tunnels get new URLs each time they restart
- Old tunnel URL stops working
- Production frontend (Netlify) can't reach backend

**How to fix:**
```bash
# 1. Get new tunnel URL
cat /tmp/tunnel.log | grep "trycloudflare.com"

# 2. Update Netlify environment variable
# Go to: https://app.netlify.com → Your Site → Site settings → Environment variables
# Update: REACT_APP_API_URL = https://new-tunnel-url.trycloudflare.com

# 3. Trigger Netlify redeploy
# Go to: Deploys tab → Trigger deploy → Deploy site
```

**Prevention:**
- Use a named Cloudflare tunnel (requires Cloudflare account)
- Or run backend on a dedicated server with static IP

### Scenario 4: Port Already in Use

**What happens:**
```
Error: listen tcp 127.0.0.1:8000: bind: address already in use
```

**How to fix:**
```bash
# 1. Find process using the port
lsof -ti:8000

# 2. Kill it
lsof -ti:8000 | xargs kill -9

# 3. Or kill by name
pkill -f "python3 app.py"

# 4. Restart service
python3 app.py
```

### Scenario 5: Ollama Not Responding

**What happens:**
- Backend shows "Ollama not running" in health check
- Chat interface returns errors
- Can't list models

**How to fix:**
```bash
# 1. Check if Ollama is running
pgrep ollama

# 2. If not, start it
ollama serve

# 3. If running but not responding, restart it
pkill ollama
sleep 2
ollama serve

# 4. Verify it works
ollama list

# 5. Test with curl
curl http://localhost:11434/api/tags
```

### Scenario 6: Frontend Won't Start

**What happens:**
```
sh: react-scripts: command not found
```

**How to fix:**
```bash
# 1. Reinstall dependencies
cd frontend
rm -rf node_modules package-lock.json
npm install

# 2. Start again
npm start

# 3. If still fails, check Node version
node --version  # Should be 16+
npm --version   # Should be 8+

# 4. Update Node if needed (macOS)
brew upgrade node
```

### Scenario 7: Need to Access from Another Device

**What happens:**
- You want to use the app from your phone or another computer

**Local Network Access:**
```bash
# 1. Get your local IP
ifconfig | grep "inet " | grep -v 127.0.0.1
# Example: inet 192.168.20.53

# 2. Frontend is accessible at:
# http://192.168.20.53:3000

# 3. Backend is accessible at:
# http://192.168.20.53:8000
```

**Internet Access (via Tunnel):**
```bash
# 1. Make sure tunnel is running
./start-tunnel.sh

# 2. Get tunnel URL
cat /tmp/tunnel.log | grep "trycloudflare.com"

# 3. Share the tunnel URL
# Anyone can access: https://your-tunnel.trycloudflare.com
```

### Scenario 8: Moving to a New Location

**What happens:**
- Different WiFi network
- Different IP address
- Services still running

**What to do:**
```bash
# Nothing required!
# Services bind to localhost, which never changes
# Frontend dev server shows new IP automatically

# Just check tunnel is still running:
pgrep cloudflared && echo "Tunnel OK" || ./start-tunnel.sh
```

### Scenario 9: Running Out of Disk Space

**What happens:**
- Vector database can't write new data
- PDF uploads fail
- System becomes slow

**How to fix:**
```bash
# 1. Check disk usage
df -h

# 2. Find large projects
du -sh data/*/ | sort -h

# 3. Delete unused projects
rm -rf data/old-project-id/

# 4. Clean up uploads
rm -f data/*/uploads/*.pdf

# 5. Clear Qdrant cache (if using)
rm -rf data/*/qdrant/storage/*

# 6. Clean Ollama models you don't use
ollama list
ollama rm model-name
```

### Scenario 10: Need to Run Only Backend (Headless)

**What happens:**
- Running on a server with no display
- Want API access only, no browser interface

**How to do it:**
```bash
# 1. Start Ollama
ollama serve &

# 2. Start Backend
python3 app.py &

# 3. Start Tunnel for remote access
./start-tunnel.sh &

# 4. Access via API
curl https://your-tunnel.trycloudflare.com/api/health

# 5. Chat via API
curl -X POST https://your-tunnel.trycloudflare.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is this about?",
    "project_id": "brookline-ma"
  }'
```

---

## Troubleshooting

### All Services Running but Chat Doesn't Work

```bash
# 1. Check backend logs for errors
tail -f /tmp/backend.log

# 2. Check if Qdrant is accessible
ls -la data/your-project-id/qdrant/

# 3. Test chat API directly
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "test",
    "project_id": "your-project-id"
  }'

# 4. Check project config
cat data/your-project-id/config.json

# 5. Verify data sources have been ingested
curl http://localhost:8000/api/projects/your-project-id/documents
```

### Tunnel Keeps Disconnecting

```bash
# Free Cloudflare tunnels are unstable
# Solutions:

# 1. Use a named tunnel (requires account)
# Follow: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps

# 2. Use ngrok instead
brew install ngrok
ngrok http 8000

# 3. Deploy backend to cloud server
# See DEPLOYMENT.md for options
```

### Backend Says "No Models Available"

```bash
# 1. Check Ollama is running
curl http://localhost:11434/api/tags

# 2. Pull a model
ollama pull llama3.1:8b

# 3. Restart backend
pkill -f "python3 app.py"
python3 app.py

# 4. Verify in UI
# Go to Settings → AI Provider → Select model
```

### Frontend Shows Blank Page

```bash
# 1. Check browser console for errors (F12)

# 2. Clear browser cache
# Chrome: Ctrl+Shift+Delete
# Safari: Cmd+Option+E

# 3. Check if backend is accessible
curl http://localhost:8000/api/health

# 4. Check frontend .env file
cat frontend/.env
# Should have: REACT_APP_API_URL=http://localhost:8000

# 5. Restart frontend
pkill -f "react-scripts"
cd frontend && npm start
```

### Can't Upload PDFs

```bash
# 1. Check file size (max 100MB default)

# 2. Check disk space
df -h

# 3. Check uploads directory exists
mkdir -p data/your-project-id/uploads/

# 4. Check permissions
chmod -R 755 data/

# 5. Check backend logs
tail -f /tmp/backend.log
```

---

## Quick Restart Script

Save this as `restart-all.sh`:

```bash
#!/bin/bash

echo "Stopping all services..."
pkill ollama
pkill -f "python3 app.py"
pkill -f "react-scripts start"
pkill cloudflared

echo "Waiting 3 seconds..."
sleep 3

echo "Starting Ollama..."
ollama serve > /tmp/ollama.log 2>&1 &
sleep 5

echo "Starting Backend..."
python3 app.py > /tmp/backend.log 2>&1 &
sleep 3

echo "Starting Frontend..."
cd frontend && npm start > /tmp/frontend.log 2>&1 &
sleep 5

echo "Starting Tunnel..."
./start-tunnel.sh &

echo ""
echo "✅ All services started!"
echo ""
echo "Access points:"
echo "  Local Frontend:  http://localhost:3000"
echo "  Local Backend:   http://localhost:8000"
echo ""
echo "Getting tunnel URL..."
sleep 5
cat /tmp/tunnel.log | grep "trycloudflare.com" | tail -1
echo ""
echo "Monitor logs:"
echo "  tail -f /tmp/backend.log"
echo "  tail -f /tmp/tunnel.log"
```

Make it executable:
```bash
chmod +x restart-all.sh
./restart-all.sh
```

---

## Production Deployment

For production use, consider:

1. **Systemd Services** (Linux)
   - Create service files for auto-restart
   - Enable on boot
   - See DEPLOYMENT.md

2. **Docker Compose**
   - Containerize all services
   - Easy multi-server deployment
   - Coming soon in roadmap

3. **Named Cloudflare Tunnel**
   - Persistent URL
   - Better reliability
   - Requires Cloudflare account

4. **Dedicated Server**
   - No need for tunnel
   - Static IP with domain
   - More reliable for production

See DEPLOYMENT.md for detailed production setup instructions.

---

**Last Updated:** January 5, 2026
