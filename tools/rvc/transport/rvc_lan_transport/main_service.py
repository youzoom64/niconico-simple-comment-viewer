from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException

from .audio_io import AudioBridge, list_audio_devices
from .client import RvcLanClient
from .config import MainConfig
from .logging_utils import log_event


def create_main_app(config: MainConfig, client: RvcLanClient | None = None) -> FastAPI:
    config.validate()
    lan_client = client or RvcLanClient(config)
    bridge = AudioBridge(config, lan_client)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await lan_client.start()
        if config.auto_start_audio:
            try:
                await lan_client.wait_connected(10)
                await bridge.start(config.input_device, config.output_device)
                log_event(lan_client.logger, "audio.autostarted")
            except Exception as exc:
                lan_client.metrics.set_error(f"audio autostart failed: {exc}")
                log_event(lan_client.logger, "audio.autostart_failed", error=f"{type(exc).__name__}: {exc}")
        try:
            yield
        finally:
            await bridge.stop()
            await lan_client.stop()

    app = FastAPI(title="RVC LAN Main Service", version="1", lifespan=lifespan)
    app.state.client = lan_client
    app.state.bridge = bridge

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "rvc-lan-main",
            "connected": lan_client.connected,
            "audioRunning": bridge.running,
        }

    @app.get("/api/v1/status")
    async def status() -> dict[str, Any]:
        return {**lan_client.status(), "audio": bridge.status(), "config": config.public_dict()}

    @app.get("/api/v1/devices")
    async def devices() -> dict[str, Any]:
        try:
            return list_audio_devices()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"audio device enumeration failed: {exc}") from exc

    @app.post("/api/v1/audio/start")
    async def audio_start(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            await bridge.start(
                str(payload.get("inputDevice") or ""),
                str(payload.get("outputDevice") or ""),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"audio start failed: {exc}") from exc
        log_event(
            lan_client.logger,
            "audio.started",
            inputDevice=bridge.input_device,
            outputDevice=bridge.output_device,
        )
        return {"ok": True, "audio": bridge.status()}

    @app.post("/api/v1/audio/stop")
    async def audio_stop() -> dict[str, Any]:
        await bridge.stop()
        log_event(lan_client.logger, "audio.stopped")
        return {"ok": True, "audio": bridge.status()}

    return app
