from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.core.config import AppConfig
from app.services.rtfw_api import RtfwApiClient, normalize_base_url, normalize_devices, normalize_local_http_url, normalize_status


class MockRtfwHandler(BaseHTTPRequestHandler):
    requests: list[tuple[str, str, dict]] = []

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/v1/status":
            self._send({"state": "listening", "source": "mic", "latestTranscript": {"text": "テスト"}})
            return
        if self.path.startswith("/api/v1/devices"):
            self._send({"devices": [{"id": 4, "name": "既定マイク", "isDefault": True}]})
            return
        if self.path == "/api/v1/config":
            self._send({"ok": True, "settings": {"model": "large-v3", "threshold_dbfs": -38.0}})
            return
        if self.path == "/api/v1/models":
            self._send({"ok": True, "models": ["large-v3", "small"]})
            return
        self._send({"ok": True})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length) or b"{}")
        type(self).requests.append(("POST", self.path, payload))
        self._send({"ok": True})

    def do_PUT(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length) or b"{}")
        type(self).requests.append(("PUT", self.path, payload))
        self._send({"ok": True, "settings": payload})

    def _send(self, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class RtfwApiClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MockRtfwHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.client = RtfwApiClient(f"http://127.0.0.1:{cls.server.server_port}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self) -> None:
        MockRtfwHandler.requests.clear()

    def test_rejects_non_loopback_endpoint(self) -> None:
        with self.assertRaises(ValueError):
            normalize_base_url("http://192.168.1.2:8795")
        with self.assertRaises(ValueError):
            normalize_local_http_url("https://example.com/overlay", label="OBS字幕URL")

    def test_reads_status_and_devices(self) -> None:
        status = self.client.status()
        devices = self.client.devices("mic")
        self.assertEqual("listening", status.state)
        self.assertEqual("mic", status.source)
        self.assertEqual("テスト", status.latest_text)
        self.assertEqual("4", devices[0].id)
        self.assertTrue(devices[0].is_default)

    def test_activate_switches_only_when_other_source_is_active(self) -> None:
        current = normalize_status({"state": "recording", "source": "mic"})
        self.client.activate("pc", "7", current)
        self.assertEqual(("POST", "/api/v1/capture/switch", {"source": "pc", "deviceId": "7"}), MockRtfwHandler.requests[-1])
        stopped = normalize_status({"state": "stopped", "source": ""})
        self.client.activate("mic", "4", stopped)
        self.assertEqual(("POST", "/api/v1/capture/start", {"source": "mic", "deviceId": "4"}), MockRtfwHandler.requests[-1])

    def test_normalizers_accept_contract_variants(self) -> None:
        devices = normalize_devices(["A", {"deviceId": "b", "label": "B"}])
        self.assertEqual(["A", "b"], [device.id for device in devices])
        self.assertEqual("B", devices[1].name)

    def test_config_roundtrip(self) -> None:
        config = AppConfig.from_dict({"rtfw_base_url": "http://localhost:9000", "rtfw_overlay_url": "http://127.0.0.1:9001/"})
        self.assertEqual("http://localhost:9000", config.to_dict()["rtfw_base_url"])
        self.assertEqual("http://127.0.0.1:9001/", config.to_dict()["rtfw_overlay_url"])

    def test_remote_configuration_and_models_contract(self) -> None:
        self.assertEqual("large-v3", self.client.configuration()["settings"]["model"])
        self.assertEqual(["large-v3", "small"], self.client.models())
        result = self.client.update_configuration({"model": "small", "threshold_dbfs": -32.0})
        self.assertEqual("small", result["settings"]["model"])
        self.assertEqual(("PUT", "/api/v1/config", {"model": "small", "threshold_dbfs": -32.0}), MockRtfwHandler.requests[-1])


if __name__ == "__main__":
    unittest.main()
