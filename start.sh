#!/bin/bash

echo "🏘️  Starting Neighborhood AI..."
echo ""

# Create data directory if it doesn't exist
mkdir -p data

# Function to kill all background processes on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $(jobs -p) 2>/dev/null
    exit
}

trap cleanup INT TERM

# Start backend
echo "Starting backend server on http://localhost:8000..."
python3 app.py &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start frontend
echo "Starting frontend on http://localhost:3000..."
cd frontend
npm start &
FRONTEND_PID=$!

echo ""
echo "✅ Neighborhood AI is running!"
echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for both processes
wait
