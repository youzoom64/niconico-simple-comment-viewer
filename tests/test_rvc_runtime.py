from __future__ import annotations

import pytest

from app.services.obs_websocket import ObsAudioInput, ObsDeviceOption, ObsOutputActivity
from app.services.rvc_main_service import MainServiceLease, RvcAudioDevice, RvcAudioDevices
from app.services.rvc_runtime import ObsAccess, RvcRuntimeController, RvcRuntimeError, RvcRuntimeState
from app.services.rvc_settings import RvcSettings
from app.services.rvc_worker_api import RvcModel, RvcWorkerOverview


OFF_ID = "physical-guid"
ON_ID = "cable-output-guid"


class FakeWorker:
    def __init__(self, events: list[str], *, ready: bool = True) -> None:
        self.events = events
        self.ready = ready
        self.active = RvcModel(1, "model-one", True)
        self.last_ensure_started = False

    def ensure_running(self):
        self.events.append("direct.ensure")
        return {"status": "OK"}

    def overview(self) -> RvcWorkerOverview:
        self.events.append("worker.overview")
        return RvcWorkerOverview(self.ready, (RvcModel(1, "model-one", True),), self.active, {"ok": True}, {})

    def select_model(self, slot_index: int) -> RvcModel:
        self.events.append(f"worker.select:{slot_index}")
        self.active = RvcModel(slot_index, f"model-{slot_index}", True)
        return self.active

    def start_audio(self, input_name: str):
        self.events.append(f"direct.start:{input_name}")
        return {"serverAudioStated": 1}

    def stop_audio(self):
        self.events.append("direct.stop")
        return {"serverAudioStated": 0}


class FakeMainClient:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.running = False

    def wait_connected(self):
        self.events.append("main.wait_connected")
        return self.status()

    def status(self):
        return {
            "connected": True,
            "authorized": True,
            "audio": {
                "running": self.running,
                "pipeline": {
                    "state": "flowing" if self.running else "waiting_input",
                    "boundaries": {},
                },
            },
            "logPath": "J:/tools/scripts/rvc_lan_transport/runtime/logs/main.jsonl",
        }

    def devices(self):
        self.events.append("main.devices")
        return RvcAudioDevices(
            inputs=(RvcAudioDevice("1", "Physical Mic", True),),
            outputs=(RvcAudioDevice("25", "CABLE Input", False),),
        )

    def start_audio(self, input_device: str, output_device: str):
        self.events.append(f"main.start:{input_device}:{output_device}")
        self.running = True
        return {"ok": True}

    def stop_audio(self):
        self.events.append("main.stop")
        self.running = False
        return {"ok": True}


class FakeManager:
    def __init__(self, events: list[str], *, owned: bool = True) -> None:
        self.events = events
        self.owned = owned
        self.client = FakeMainClient(events)
        self.owned_pid = 4321 if owned else None

    def ensure_running(self, _settings, _token):
        self.events.append("manager.ensure")
        return MainServiceLease(self.client, self.owned, self.owned_pid or 9876, self.client.status())

    def stop_owned(self):
        self.events.append("manager.stop_owned")
        if not self.owned:
            return False
        self.owned = False
        self.owned_pid = None
        return True


class FakeObs:
    def __init__(self, events: list[str], *, fail_on: bool = False) -> None:
        self.events = events
        self.fail_on = fail_on
        self.current = OFF_ID
        self.input = ObsAudioInput(
            "マイク",
            "wasapi_input_capture",
            self.current,
            (
                ObsDeviceOption(OFF_ID, "Physical Mic"),
                ObsDeviceOption(ON_ID, "CABLE Output"),
            ),
        )

    def _snapshot(self):
        return ObsAudioInput(self.input.name, self.input.kind, self.current, self.input.devices)

    def list_inputs(self):
        self.events.append("obs.list")
        return (self._snapshot(),)

    def get_input(self, _name):
        self.events.append("obs.get")
        return self._snapshot()

    def set_device(self, _name, device_id):
        self.events.append(f"obs.set:{device_id}")
        if self.fail_on and device_id == ON_ID:
            raise RuntimeError("fake OBS failure")
        self.current = device_id
        return self._snapshot()

    def activity(self):
        self.events.append("obs.activity")
        return ObsOutputActivity(False, False)


def settings() -> RvcSettings:
    return RvcSettings(
        worker_host="192.0.2.10",
        worker_port=8770,
        obs_input_name="マイク",
        obs_off_device_id=OFF_ID,
        obs_on_device_id=ON_ID,
        input_device_id="1",
        output_device_id="25",
        model_slot_index=1,
    )


def controller(events: list[str], *, fail_obs_on: bool = False, owned: bool = True):
    manager = FakeManager(events, owned=owned)
    obs = FakeObs(events, fail_on=fail_obs_on)
    worker = FakeWorker(events)
    value = RvcRuntimeController(
        main_manager=manager,
        worker_factory=lambda _settings, _token: worker,
        obs_factory=lambda _access: obs,
        token_loader=lambda: "secret",
    )
    return value, manager, obs


def test_on_and_off_follow_audio_then_obs_and_restore_then_stop_order() -> None:
    events: list[str] = []
    runtime, manager, _obs = controller(events)
    started = runtime.start(settings(), ObsAccess("ws://127.0.0.1:4455", ""))
    assert started.state == RvcRuntimeState.ON
    assert events.index("main.start:1:25") < events.index(f"obs.set:{ON_ID}")
    stopped = runtime.stop(settings(), ObsAccess("ws://127.0.0.1:4455", ""))
    assert stopped.state == RvcRuntimeState.OFF
    assert events.index(f"obs.set:{OFF_ID}") < events.index("main.stop") < events.index("manager.stop_owned")
    assert events.count("obs.get") == 1
    assert events.count("obs.list") == 1
    assert events.count("obs.activity") == 1
    assert events.count(f"obs.set:{ON_ID}") == 1
    assert events.count(f"obs.set:{OFF_ID}") == 1
    assert not manager.owned


def test_obs_switch_failure_rolls_back_audio_obs_and_owned_service() -> None:
    events: list[str] = []
    runtime, manager, obs = controller(events, fail_obs_on=True)
    with pytest.raises(RvcRuntimeError, match="fake OBS failure") as caught:
        runtime.start(settings(), ObsAccess("ws://127.0.0.1:4455", ""))
    assert caught.value.snapshot.state == RvcRuntimeState.ERROR
    assert "main.stop" in events
    assert f"obs.set:{OFF_ID}" in events
    assert events[-1] == "manager.stop_owned"
    assert obs.current == OFF_ID
    assert not manager.owned


def test_double_start_is_idempotent() -> None:
    events: list[str] = []
    runtime, _manager, _obs = controller(events)
    access = ObsAccess("ws://127.0.0.1:4455", "")
    runtime.start(settings(), access)
    runtime.start(settings(), access)
    assert events.count("main.start:1:25") == 1
    assert events.count(f"obs.set:{ON_ID}") == 1


def test_external_main_service_is_used_but_not_terminated() -> None:
    events: list[str] = []
    runtime, manager, _obs = controller(events, owned=False)
    access = ObsAccess("ws://127.0.0.1:4455", "")
    runtime.start(settings(), access)
    runtime.stop(settings(), access)
    assert "manager.stop_owned" in events
    assert manager.owned is False


def test_shutdown_restores_obs_and_stops_audio_when_on() -> None:
    events: list[str] = []
    runtime, _manager, obs = controller(events)
    access = ObsAccess("ws://127.0.0.1:4455", "")
    runtime.start(settings(), access)
    result = runtime.shutdown(settings(), access)
    assert result.state == RvcRuntimeState.OFF
    assert obs.current == OFF_ID
    assert "main.stop" in events


def test_background_probe_does_not_call_obs_or_enumerate_audio_devices() -> None:
    events: list[str] = []
    runtime, _manager, _obs = controller(events)
    access = ObsAccess("ws://127.0.0.1:4455", "")
    runtime.refresh(settings(), access, ensure_main=True, refresh_obs=True)
    events.clear()

    for _ in range(5):
        result = runtime.refresh(settings(), access, ensure_main=False, refresh_obs=False)

    assert result.main_connected is True
    assert not any(value.startswith("obs.") for value in events)
    assert "main.devices" not in events


def test_explicit_refresh_reads_obs_and_audio_devices() -> None:
    events: list[str] = []
    runtime, _manager, _obs = controller(events)
    runtime.refresh(
        settings(),
        ObsAccess("ws://127.0.0.1:4455", ""),
        ensure_main=True,
        refresh_obs=True,
    )
    assert "obs.list" in events
    assert "obs.activity" in events
    assert "main.devices" in events


def test_local_mmvc_direct_uses_mmvc_and_obs_without_worker_or_main_audio() -> None:
    events: list[str] = []
    manager = FakeManager(events)
    obs = FakeObs(events)
    direct = FakeWorker(events)
    runtime = RvcRuntimeController(
        main_manager=manager,
        worker_factory=lambda _settings, _token: (_ for _ in ()).throw(AssertionError("LAN worker must not be used")),
        direct_factory=lambda _settings: direct,
        main_client_factory=lambda _settings: manager.client,
        obs_factory=lambda _access: obs,
        token_loader=lambda: (_ for _ in ()).throw(AssertionError("token must not be loaded")),
    )
    local = RvcSettings(
        worker_host="127.0.0.1",
        worker_port=18888,
        obs_input_name="マイク",
        obs_off_device_id=OFF_ID,
        obs_on_device_id=ON_ID,
        model_slot_index=1,
    )
    access = ObsAccess("ws://127.0.0.1:4455", "")

    started = runtime.start(local, access)
    assert started.state == RvcRuntimeState.ON
    assert started.main_connected is True
    assert started.audio_running is True
    assert "direct.ensure" not in events
    assert "worker.overview" in events
    assert any(value.startswith("direct.start:") for value in events)
    assert f"obs.set:{ON_ID}" in events
    assert "manager.ensure" not in events
    assert not any(value.startswith("main.start:") for value in events)

    stopped = runtime.stop(local, access)
    assert stopped.state == RvcRuntimeState.OFF
    assert f"obs.set:{OFF_ID}" in events
    assert "direct.stop" in events
    assert "main.stop" not in events


def test_start_mmvc_is_the_only_action_that_ensures_local_mmvc() -> None:
    events: list[str] = []
    manager = FakeManager(events)
    direct = FakeWorker(events)
    runtime = RvcRuntimeController(
        main_manager=manager,
        direct_factory=lambda _settings: direct,
        main_client_factory=lambda _settings: manager.client,
        obs_factory=lambda _access: FakeObs(events),
    )
    local = RvcSettings(worker_host="127.0.0.1", worker_port=18888)

    runtime.start_mmvc(local, ObsAccess("ws://127.0.0.1:4455", ""))

    assert events.count("direct.ensure") == 1
    assert "worker.overview" in events


def test_local_mmvc_direct_refresh_resolves_saved_main_audio_devices() -> None:
    events: list[str] = []
    manager = FakeManager(events)
    runtime = RvcRuntimeController(
        main_manager=manager,
        direct_factory=lambda _settings: FakeWorker(events),
        main_client_factory=lambda _settings: manager.client,
        obs_factory=lambda _access: FakeObs(events),
        token_loader=lambda: (_ for _ in ()).throw(AssertionError("token must not be loaded")),
    )
    local = RvcSettings(
        worker_host="127.0.0.1",
        worker_port=18888,
        main_port=8771,
        obs_input_name="マイク",
        obs_off_device_id=OFF_ID,
        obs_on_device_id=ON_ID,
        input_device_id="1",
        output_device_id="25",
    )

    snapshot = runtime.refresh(
        local,
        ObsAccess("ws://127.0.0.1:4455", ""),
        ensure_main=True,
        refresh_obs=True,
    )

    assert snapshot.audio_inputs[0].name == "Physical Mic"
    assert snapshot.audio_outputs[0].name == "CABLE Input"
    assert "main.devices" in events
    assert "manager.ensure" not in events
