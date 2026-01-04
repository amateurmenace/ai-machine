# Deployment Guide: Hybrid Architecture

This guide explains how to deploy Neighborhood AI with:
- **Frontend**: Netlify (free static hosting, global CDN)
- **Backend**: Your local Mac Mini with Cloudflare Tunnel

## Architecture

```
┌─────────────────────┐     ┌─────────────────────────────┐
│  Netlify            │     │ Your Home Server (Mac Mini) │
│  Static React app   │────▶│ - FastAPI backend           │
│  Global CDN         │     │ - Qdrant vector DB          │
│  Free HTTPS         │     │ - Ollama (local LLM)        │
└─────────────────────┘     └─────────────────────────────┘
                                    ▲
                            Cloudflare Tunnel
                            (secure, no port forwarding)
```

## Prerequisites

- Mac Mini M4 (or similar) running the backend
- GitHub repository for the code
- Cloudflare account (free)
- Netlify account (free)

---

## Step 1: Set Up Cloudflare Tunnel

Cloudflare Tunnel creates a secure connection between your home server and the internet without opening ports on your router.

### Install cloudflared

```bash
# macOS
brew install cloudflare/cloudflare/cloudflared

# Or download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
```

### Login and Create Tunnel

```bash
# Login to Cloudflare
cloudflared tunnel login

# Create a tunnel
cloudflared tunnel create neighborhood-ai

# This creates a tunnel ID and credentials file at:
# ~/.cloudflared/<tunnel-id>.json
```

### Configure the Tunnel

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: neighborhood-ai
credentials-file: /Users/yourusername/.cloudflared/<tunnel-id>.json

ingress:
  # Route to your FastAPI backend
  - hostname: api.neighborhood-ai.yourdomain.com
    service: http://localhost:8000
  # Catch-all (required)
  - service: http_status:404
```

If you don't have a custom domain, use the free `trycloudflare.com` subdomain:

```yaml
tunnel: neighborhood-ai
credentials-file: /Users/yourusername/.cloudflared/<tunnel-id>.json

ingress:
  - service: http://localhost:8000
```

### Run the Tunnel

```bash
# Quick test (temporary URL)
cloudflared tunnel --url http://localhost:8000

# Or run your configured tunnel
cloudflared tunnel run neighborhood-ai

# Note the URL: https://your-tunnel-id.trycloudflare.com
```

### Run as a Service (Recommended)

```bash
# Install as launchd service (macOS)
sudo cloudflared service install

# Start the service
sudo launchctl start com.cloudflare.cloudflared

# Check status
sudo launchctl list | grep cloudflared
```

---

## Step 2: Deploy Frontend to Netlify

### Option A: Netlify CLI (Recommended)

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Navigate to frontend directory
cd frontend

# Login to Netlify
netlify login

# Create new site
netlify init

# Deploy
netlify deploy --prod
```

### Option B: Netlify Web UI

1. Go to [netlify.com](https://netlify.com) and sign in
2. Click "Add new site" → "Import an existing project"
3. Connect your GitHub repository
4. Configure build settings:
   - **Base directory**: `frontend`
   - **Build command**: `npm run build`
   - **Publish directory**: `frontend/build`
5. Click "Deploy site"

### Configure Environment Variable

In Netlify dashboard → Site settings → Build & deploy → Environment variables:

```
REACT_APP_API_URL = https://your-tunnel-id.trycloudflare.com
```

Or with custom domain:
```
REACT_APP_API_URL = https://api.neighborhood-ai.yourdomain.com
```

Then redeploy:
```bash
netlify deploy --prod
```

---

## Step 3: Configure CORS on Backend

Update your FastAPI backend to allow requests from Netlify:

Edit `app.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

# Add after creating the FastAPI app
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "https://your-site-name.netlify.app",  # Your Netlify URL
        "https://neighborhood-ai.yourdomain.com",  # Custom domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Step 4: Start Your Backend

On your Mac Mini:

```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Start the backend
cd neighborhood-ai
python3 app.py

# Terminal 3: Start Cloudflare Tunnel (if not running as service)
cloudflared tunnel run neighborhood-ai
```

---

## Step 5: Verify Deployment

1. **Test the tunnel**: Visit your tunnel URL in a browser
   - You should see the FastAPI docs at `/docs`

2. **Test the frontend**: Visit your Netlify URL
   - The landing page should load
   - Projects should show "online" status if backend is running

3. **Test chat**: Create a project and try chatting
   - Messages should be processed by your local Ollama

---

## Keeping It Running

### Auto-start on Boot (macOS)

Create a launchd plist for the backend at `~/Library/LaunchAgents/com.neighborhood-ai.backend.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.neighborhood-ai.backend</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/neighborhood-ai/app.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/neighborhood-ai</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/neighborhood-ai.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/neighborhood-ai.error.log</string>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.neighborhood-ai.backend.plist
```

---

## Troubleshooting

### Frontend can't connect to backend

1. Check tunnel is running: `cloudflared tunnel info neighborhood-ai`
2. Check CORS settings in `app.py`
3. Verify `REACT_APP_API_URL` is set correctly in Netlify

### Tunnel disconnects frequently

- Ensure your Mac doesn't go to sleep: System Settings → Energy → Prevent sleep
- Use the cloudflared service instead of manual running

### Chat times out

- Check Ollama is running: `ollama list`
- Check backend logs: `tail -f /tmp/neighborhood-ai.log`

---

## Cost Breakdown

| Service | Cost |
|---------|------|
| Netlify | Free (100GB bandwidth) |
| Cloudflare Tunnel | Free |
| Ollama | Free (runs locally) |
| Electricity | ~$2/month (Mac Mini M4) |
| **Total** | **~$2/month** |

---

## Security Notes

- Cloudflare Tunnel is encrypted (no need for your own TLS certs)
- No ports opened on your router
- Consider adding authentication for production use
- Keep your tunnel credentials file secure

---

## Custom Domain (Optional)

If you want a custom domain:

1. Add domain to Cloudflare (free plan works)
2. In Cloudflare dashboard: Zero Trust → Access → Tunnels
3. Add a public hostname pointing to your tunnel
4. Update Netlify env var and CORS settings

---

**Last Updated:** January 2026
