#!/bin/bash

# Start FastAPI backend server
# Make sure you're in the backend directory and have activated your virtual environment

echo "Starting FastAPI backend..."
echo "Backend will be available at http://localhost:8000"
echo "API docs at http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

