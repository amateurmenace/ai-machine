#!/bin/bash
# Start Permanent Cloudflare Tunnel for Neighborhood AI
# This uses a named tunnel with a fixed custom domain

TUNNEL_NAME="neighborhood-ai"
TUNNEL_ID="661c38c1-d69e-433c-9910-bc3ec80d6117"
DOMAIN="create.neighborhoodai.org"

echo "Starting permanent Cloudflare tunnel: $TUNNEL_NAME"
echo "Tunnel ID: $TUNNEL_ID"
echo "Domain: https://$DOMAIN"
echo ""
echo "Backend will be accessible at: https://$DOMAIN"
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
    echo "3. Configure DNS:"
    echo "   cloudflared tunnel route dns $TUNNEL_NAME $DOMAIN"
    echo ""
    echo "4. Run this script again"
    exit 1
fi

echo "✅ Tunnel configured and ready"
echo ""

# Run the tunnel using config file
cloudflared tunnel run $TUNNEL_NAME
