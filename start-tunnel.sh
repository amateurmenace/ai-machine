#!/bin/bash
# Start Cloudflare tunnel for Civic AI Engine
# The URL will be printed - update Netlify env var if it changes

echo "Starting Cloudflare tunnel..."
echo "Press Ctrl+C to stop"
echo ""

cloudflared tunnel --url http://localhost:8000
