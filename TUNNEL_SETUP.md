# Permanent Cloudflare Tunnel Setup

## Why You Need This

The free temporary tunnel (`start-tunnel.sh`) gives you a new random URL every time you restart. This is annoying because you have to update Netlify's environment variable every time.

A **permanent named tunnel** gives you a fixed URL that never changes, even after:
- Restarting your computer
- Changing IP addresses
- Stopping and starting the tunnel

## One-Time Setup (5 minutes)

### Step 1: Install Cloudflare Tunnel CLI

```bash
# macOS
brew install cloudflared

# Already installed? Update it:
brew upgrade cloudflared
```

### Step 2: Login to Cloudflare

```bash
cloudflared tunnel login
```

This will open a browser window. Login to your Cloudflare account (create a free one if needed).

### Step 3: Create Named Tunnel

```bash
cloudflared tunnel create neighborhood-ai
```

**Output will look like:**
```
Tunnel credentials written to /Users/yourname/.cloudflared/abc123-def456.json
Created tunnel neighborhood-ai with id abc123-def456-ghi789
```

**Save that tunnel ID!** You'll need it.

### Step 4: Create Configuration File

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: neighborhood-ai
credentials-file: /Users/yourname/.cloudflared/abc123-def456.json

ingress:
  - hostname: neighborhood.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```

**Replace:**
- `abc123-def456.json` with your actual credentials file name
- `neighborhood.yourdomain.com` with your desired subdomain (optional)

### Step 5: Route DNS (Optional - for custom domain)

If you have a domain in Cloudflare:

```bash
cloudflared tunnel route dns neighborhood-ai neighborhood.yourdomain.com
```

This creates a CNAME record automatically.

**Don't have a domain?** Skip this step. You'll get a `trycloudflare.com` URL.

### Step 6: Test Your Permanent Tunnel

```bash
./start-tunnel-permanent.sh
```

**Look for output like:**
```
✅ Tunnel URL: https://neighborhood-ai.trycloudflare.com

Your quick Tunnel has been created! Visit it at:
https://neighborhood-ai.trycloudflare.com
```

**This URL is now PERMANENT!** It will never change.

### Step 7: Update Netlify

1. Go to: https://app.netlify.com/sites/neighborhood-ai/settings/deploys
2. Navigate to: **Environment variables**
3. Update `REACT_APP_API_URL` to your permanent tunnel URL
4. Click **Save**
5. Trigger a new deploy

## Daily Usage

After setup, just run:

```bash
./start-tunnel-permanent.sh
```

Your URL stays the same forever. No more updating Netlify!

## Starting All Services Together

Create a convenience script to start everything:

```bash
#!/bin/bash
# start-all.sh

echo "Starting Neighborhood AI services..."

# Terminal 1: Ollama (in background)
ollama serve > /tmp/ollama.log 2>&1 &
OLLAMA_PID=$!
echo "✅ Ollama started (PID: $OLLAMA_PID)"

# Wait for Ollama
sleep 2

# Terminal 2: Backend (in background)
cd /Users/amateurmenace/ai-machine/neighborhood-ai
python3 app.py > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "✅ Backend started (PID: $BACKEND_PID)"

# Wait for backend
sleep 3

# Terminal 3: Tunnel
echo "✅ Starting permanent tunnel..."
./start-tunnel-permanent.sh
```

## Troubleshooting

### "Tunnel not found" error

Run the creation command again:
```bash
cloudflared tunnel create neighborhood-ai
```

### Wrong URL in logs

The old temporary tunnel is still running. Kill it:
```bash
pkill cloudflared
./start-tunnel-permanent.sh
```

### IP Address Changed

Permanent tunnels handle IP changes automatically. Just restart:
```bash
pkill cloudflared
./start-tunnel-permanent.sh
```

### Get Tunnel Info

```bash
cloudflared tunnel info neighborhood-ai
```

### List All Tunnels

```bash
cloudflared tunnel list
```

### Delete Old Tunnel (if needed)

```bash
cloudflared tunnel delete <tunnel-id>
```

## Security Note

The credentials file (`~/.cloudflared/*.json`) contains secrets. Keep it safe:
- Don't commit to git
- Don't share publicly
- Back it up securely

## Cost

Cloudflare Tunnels are **100% free** with no limits for personal use.
