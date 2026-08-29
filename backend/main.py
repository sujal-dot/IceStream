"""Entrypoint for running the IceStream FastAPI Telemetry Backend server."""

import uvicorn
from backend.app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
