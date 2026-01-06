#!/bin/bash
# Start Permanent Cloudflare Tunnel for Neighborhood AI
# This uses a named tunnel with a fixed URL

TUNNEL_NAME="neighborhood-ai"

echo "Starting permanent Cloudflare tunnel: $TUNNEL_NAME"
echo "This tunnel will have a fixed URL that persists across restarts"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Check if tunnel exists
if ! cloudflared tunnel info $TUNNEL_NAME &>/dev/null; then
    echo "❌ Tunnel '$TUNNEL_NAME' not found!"
    echo ""
    echo "To create a permanent tunnel, run these commands:"
    echo ""
    echo "1. Login to Cloudflare:"
    echo "   cloudflared tunnel login"
    echo ""
    echo "2. Create the tunnel:"
    echo "   cloudflared tunnel create $TUNNEL_NAME"
    echo ""
    echo "3. Get your tunnel URL:"
    echo "   cloudflared tunnel info $TUNNEL_NAME"
    echo ""
    echo "4. Run this script again"
    exit 1
fi

# Get tunnel URL
TUNNEL_URL=$(cloudflared tunnel info $TUNNEL_NAME 2>/dev/null | grep -o 'https://[^"]*trycloudflare.com' || echo "")

if [ -n "$TUNNEL_URL" ]; then
    echo "✅ Tunnel URL: $TUNNEL_URL"
    echo ""
fi

# Run the tunnel
cloudflared tunnel --url http://localhost:8000 run $TUNNEL_NAME
