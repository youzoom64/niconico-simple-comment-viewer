from __future__ import annotations

import os

import uvicorn

from rvc_pcm_lan_worker.app import app


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.environ.get("RVC_PCM_HOST", "0.0.0.0"),
        port=int(os.environ.get("RVC_PCM_PORT", "8770")),
        log_level="info",
    )
