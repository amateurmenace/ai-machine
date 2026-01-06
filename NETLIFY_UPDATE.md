# Netlify Environment Variable Update

## Issue
The domain `create.neighborhoodai.org` is currently pointing to Netlify's frontend.
The Cloudflare tunnel is configured and running, but needs to be accessed via a different subdomain or through Netlify's API proxy.

## Solution Options

### Option 1: Use Different Subdomain for Backend (Recommended)
Use `api.neighborhoodai.org` for the backend tunnel instead:

```bash
# Remove old DNS route
cloudflared tunnel route dns delete create.neighborhoodai.org

# Add new DNS route for API
cloudflared tunnel route dns neighborhood-ai api.neighborhoodai.org
```

Then update Netlify env var:
```
REACT_APP_API_URL=https://api.neighborhoodai.org
```

### Option 2: Keep Frontend on Netlify, Backend on Tunnel
Update `~/.cloudflared/config.yml`:

```yaml
tunnel: 661c38c1-d69e-433c-9910-bc3ec80d6117
credentials-file: /Users/amateurmenace/.cloudflared/661c38c1-d69e-433c-9910-bc3ec80d6117.json

ingress:
  - hostname: api.neighborhoodai.org  # Use api subdomain
    service: http://localhost:8000
  - service: http_status:404
```

### Option 3: Netlify Redirect (Not Recommended)
Configure Netlify to proxy `/api/*` to tunnel, but this adds latency.

## Recommended Action

**Use api.neighborhoodai.org for the backend:**

1. Update DNS routing:
```bash
cloudflared tunnel route dns neighborhood-ai api.neighborhoodai.org
```

2. Update config file `~/.cloudflared/config.yml`:
```yaml
tunnel: 661c38c1-d69e-433c-9910-bc3ec80d6117
credentials-file: /Users/amateurmenace/.cloudflared/661c38c1-d69e-433c-9910-bc3ec80d6117.json

ingress:
  - hostname: api.neighborhoodai.org
    service: http://localhost:8000
  - service: http_status:404
```

3. Restart tunnel:
```bash
pkill cloudflared
./start-tunnel-permanent.sh
```

4. Update Netlify environment variable:
   - Go to: https://app.netlify.com/sites/neighborhood-ai/settings/env
   - Variable: `REACT_APP_API_URL`
   - Value: `https://api.neighborhoodai.org`
   - Save and redeploy

5. Test:
```bash
curl https://api.neighborhoodai.org/api/health
```

This keeps your frontend at `create.neighborhoodai.org` and backend at `api.neighborhoodai.org`.
