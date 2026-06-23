from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse

from app.domain.received_events.comment_event import CommentEvent
from app.domain.received_events.event_kind import EventKind
from app.domain.speech.speech_job import SpeechSynthesisJob
from app.infra.voicevox_engine.client import VoicevoxEngineClient, VoicevoxEngineConfig
from app.infra.voicevox_engine.speakers_api import list_speaker_styles
from app.infra.voicevox_engine.synthesis_api import synthesize_job_to_file


class VoicevoxEngineApiTests(unittest.TestCase):
    def test_synthesize_job_to_file_uses_audio_query_then_synthesis(self) -> None:
        with FakeVoicevoxServer() as server, TemporaryDirectory() as temp_dir:
            client = VoicevoxEngineClient(VoicevoxEngineConfig(base_url=server.base_url, timeout_seconds=5))
            result = synthesize_job_to_file(client, make_job(), Path(temp_dir))
            self.assertTrue(result.ok)
            self.assertIsNotNone(result.audio_path)
            assert result.audio_path is not None
            self.assertEqual(b"RIFFfake-wave", result.audio_path.read_bytes())

        self.assertEqual(["/audio_query", "/synthesis"], server.paths)
        self.assertEqual("7", server.queries[0]["speaker"][0])
        self.assertEqual(1.3, server.synthesis_body["speedScale"])

    def test_list_speaker_styles_flattens_speakers(self) -> None:
        with FakeVoicevoxServer() as server:
            client = VoicevoxEngineClient(VoicevoxEngineConfig(base_url=server.base_url, timeout_seconds=5))
            styles = list_speaker_styles(client)

        self.assertEqual(1, len(styles))
        self.assertEqual(7, styles[0].style_id)
        self.assertEqual("テスト", styles[0].speaker_name)


class FakeVoicevoxServer:
    def __enter__(self) -> "FakeVoicevoxServer":
        self.paths: list[str] = []
        self.queries: list[dict[str, list[str]]] = []
        self.synthesis_body: dict[str, object] = {}
        handler = self._build_handler()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def _build_handler(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                owner.paths.append(parsed.path)
                owner.queries.append(parse_qs(parsed.query))
                if parsed.path == "/speakers":
                    self._json(
                        [
                            {
                                "speaker_uuid": "uuid",
                                "name": "テスト",
                                "styles": [{"id": 7, "name": "ノーマル"}],
                            }
                        ]
                    )
                    return
                self.send_error(404)

            def do_POST(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                owner.paths.append(parsed.path)
                owner.queries.append(parse_qs(parsed.query))
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                if parsed.path == "/audio_query":
                    self._json({"speedScale": 1.0, "pitchScale": 0.0, "intonationScale": 1.0, "volumeScale": 1.0})
                    return
                if parsed.path == "/synthesis":
                    owner.synthesis_body = json.loads(body.decode("utf-8"))
                    self.send_response(200)
                    self.send_header("Content-Type", "audio/wav")
                    self.end_headers()
                    self.wfile.write(b"RIFFfake-wave")
                    return
                self.send_error(404)

            def log_message(self, _format: str, *_args: object) -> None:
                return

            def _json(self, value: object) -> None:
                data = json.dumps(value, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        return Handler


def make_job() -> SpeechSynthesisJob:
    from datetime import datetime

    return SpeechSynthesisJob(
        comment=CommentEvent(
            event_id="abc",
            comment_no=1,
            event_kind=EventKind.REGISTERED_USER_CHAT,
            text="こんにちは",
            received_at=datetime.now(),
        ),
        style_id=7,
        text_for_voice="こんにちは",
        speed_scale=1.3,
    )


if __name__ == "__main__":
    unittest.main()
