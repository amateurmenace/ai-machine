# DNS Configuration for Permanent Tunnel

## Current Status

✅ Tunnel Running: `neighborhood-ai` (ID: 661c38c1-d69e-433c-9910-bc3ec80d6117)
✅ Config File: `~/.cloudflared/config.yml` pointing to `api.neighborhoodai.org`
✅ Backend: Healthy on http://localhost:8000
⏳ DNS Record: **Needs to be added in Cloudflare Dashboard**

## Problem

The tunnel is running but `api.neighborhoodai.org` has no DNS record yet. The CLI command `cloudflared tunnel route dns` didn't create the CNAME automatically.

## Solution: Add DNS Record Manually

### Step 1: Login to Cloudflare Dashboard

1. Go to: https://dash.cloudflare.com
2. Select your account
3. Click on `neighborhoodai.org` domain

### Step 2: Add CNAME Record

1. Click **DNS** in the left sidebar
2. Click **Add record** button
3. Fill in:
   - **Type:** CNAME
   - **Name:** `api` (creates `api.neighborhoodai.org`)
   - **Target:** `661c38c1-d69e-433c-9910-bc3ec80d6117.cfargotunnel.com`
   - **Proxy status:** ✅ Proxied (orange cloud)
   - **TTL:** Auto
4. Click **Save**

### Step 3: Verify DNS

Wait 1-2 minutes, then test:

```bash
# Check DNS resolution
dig api.neighborhoodai.org +short

# Test tunnel endpoint
curl https://api.neighborhoodai.org/api/health
```

Expected result:
```json
{
  "status": "healthy",
  "service": "Neighborhood AI API",
  "ollama_status": "running",
  "projects_count": 10
}
```

## Alternative: Use CLI (If Authenticated)

If you have Cloudflare credentials configured:

```bash
# This might work if authenticated
cloudflared tunnel route dns neighborhood-ai api.neighborhoodai.org
```

But manual DNS record creation is more reliable.

## Update Netlify After DNS Works

Once the tunnel is accessible at `https://api.neighborhoodai.org`:

1. Go to: https://app.netlify.com/sites/neighborhood-ai/settings/env
2. Update environment variable:
   - **Key:** `REACT_APP_API_URL`
   - **Value:** `https://api.neighborhoodai.org`
3. Click **Save**
4. Go to **Deploys** → Click **Trigger deploy** → **Deploy site**
5. Wait for deployment (1-2 minutes)
6. Test frontend: https://neighborhood-ai.netlify.app

## Tunnel Architecture

```
Internet
   ↓
https://api.neighborhoodai.org (DNS → Cloudflare)
   ↓
Cloudflare Edge (Proxy)
   ↓
Cloudflare Tunnel (661c38c1-d69e-433c-9910-bc3ec80d6117)
   ↓
Your Mac (192.168.1.4)
   ↓
http://localhost:8000 (Backend)
```

## Permanent Tunnel Benefits

- ✅ Fixed URL that never changes
- ✅ Survives IP address changes
- ✅ Survives restarts
- ✅ No need to update Netlify env vars constantly
- ✅ SSL/TLS handled by Cloudflare

## Starting/Stopping Tunnel

```bash
# Start tunnel
./start-tunnel-permanent.sh

# Stop tunnel
pkill cloudflared

# Check if running
pgrep -fl cloudflared

# View logs
tail -f /tmp/tunnel.log
```

## Troubleshooting

### "Connection refused" or curl errors

**Cause:** DNS record not created yet

**Fix:** Follow Step 2 above to add CNAME record in Cloudflare dashboard

### Tunnel not running

```bash
pgrep -fl cloudflared
# If no output:
./start-tunnel-permanent.sh
```

### Backend not responding

```bash
curl http://localhost:8000/api/health
# If fails:
cd /Users/amateurmenace/ai-machine/neighborhood-ai
python3 app.py > /tmp/backend.log 2>&1 &
```

### DNS still not resolving

```bash
# Clear DNS cache (macOS)
sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder

# Try different DNS server
dig @8.8.8.8 api.neighborhoodai.org +short
```

## Summary

**Current Setup:**
- Frontend: `create.neighborhoodai.org` → Netlify (static site)
- Backend: `api.neighborhoodai.org` → Your Mac via tunnel (local AI)

**Next Steps:**
1. Add CNAME record in Cloudflare dashboard (see Step 2)
2. Wait 1-2 minutes for DNS propagation
3. Test: `curl https://api.neighborhoodai.org/api/health`
4. Update Netlify env var to `https://api.neighborhoodai.org`
5. Redeploy Netlify site

**Status:** Tunnel configured and ready, just needs DNS record created.
