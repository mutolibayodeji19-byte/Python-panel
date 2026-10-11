import hmac
import os
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException

app = FastAPI(
    title="PRIME ZENITH Worker",
    version="1.0.0",
)

WORKER_SHARED_SECRET = os.environ.get(
    "WORKER_SHARED_SECRET", ""
).strip()


@app.get("/health")
def health():
    return {
        "service": "PRIME ZENITH Worker",
        "health": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/worker/status")
def worker_status(
    x_worker_secret: str | None = Header(default=None),
):
    if not WORKER_SHARED_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Worker secret is not configured",
        )

    if not x_worker_secret or not hmac.compare_digest(
        x_worker_secret, WORKER_SHARED_SECRET
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )

    return {
        "status": "online",
        "connected": True,
        "execution_enabled": False,
        "message": "Worker API ready; isolated runtime not configured",
        "time": datetime.now(timezone.utc).isoformat(),
    }
