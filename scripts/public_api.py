"""Local public-demo preview with no database, upload storage or live credentials."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import uvicorn
from app.core.config import Settings
from app.main import create_app

if __name__ == "__main__":
    settings = Settings(
        _env_file=None,
        public_demo=True,
        cors_origins=["http://localhost:3002", "http://127.0.0.1:3002"],
    )
    uvicorn.run(create_app(settings), host="127.0.0.1", port=8002)
