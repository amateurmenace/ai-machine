#!/bin/bash

echo "🏘️  Installing Neighborhood AI..."
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version

# Check Node version
echo "Checking Node.js version..."
node --version
npm --version

echo ""
echo "Installing Python dependencies..."
pip3 install -r requirements.txt --break-system-packages

echo ""
echo "Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo ""
echo "Creating data directory..."
mkdir -p data

echo ""
echo "✅ Installation complete!"
echo ""
echo "To start the application:"
echo "  1. Backend:  python3 app.py"
echo "  2. Frontend: cd frontend && npm start"
echo ""
echo "Or use the start.sh script to run both:"
echo "  ./start.sh"
