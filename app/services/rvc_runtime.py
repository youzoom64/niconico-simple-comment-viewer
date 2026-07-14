from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from app.services.obs_websocket import (
    ObsAudioInput,
    ObsOutputActivity,
    get_obs_audio_input,
    get_obs_output_activity,
    list_obs_audio_inputs,
    set_obs_input_device,
)
from app.services.rvc_main_service import (
    MainServiceLease,
    RvcAudioDevice,
    RvcMainApiClient,
    RvcMainServiceError,
    RvcMainServiceManager,
)
from app.services.rvc_mmvc_direct import RvcMmvcDirectClient
from app.services.rvc_settings import RvcSettings, load_rvc_token
from app.services.rvc_worker_api import RvcModel, RvcWorkerApiClient, RvcWorkerOverview


class RvcRuntimeState(str, Enum):
    OFF = "off"
    STARTING = "starting"
    ON = "on"
    STOPPING = "stopping"
    ERROR = "error"


STATE_LABELS = {
    RvcRuntimeState.OFF: "OFF",
    RvcRuntimeState.STARTING: "起動中",
    RvcRuntimeState.ON: "ON",
    RvcRuntimeState.STOPPING: "停止中",
    RvcRuntimeState.ERROR: "エラー",
}


@dataclass(frozen=True, slots=True)
class ObsAccess:
    url: str
    password: str


@dataclass(frozen=True, slots=True)
class RvcRuntimeSnapshot:
    state: RvcRuntimeState
    worker_ok: bool
    processor_ready: bool
    main_connected: bool
    audio_running: bool
    main_owned: bool
    main_pid: int | None
    models: tuple[RvcModel, ...]
    active_model: RvcModel | None
    audio_inputs: tuple[RvcAudioDevice, ...]
    audio_outputs: tuple[RvcAudioDevice, ...]
    obs_connected: bool
    obs_inputs: tuple[ObsAudioInput, ...]
    obs_current_device_id: str
    obs_streaming: bool
    obs_recording: bool
    last_error: str
    log_path: str
    audio_pipeline: dict[str, Any] = field(default_factory=dict)


class RvcRuntimeError(RuntimeError):
    def __init__(self, message: str, snapshot: RvcRuntimeSnapshot) -> None:
        super().__init__(message)
        self.snapshot = snapshot


class RvcObsApi:
    def __init__(self, access: ObsAccess) -> None:
        self.access = access

    def list_inputs(self) -> tuple[ObsAudioInput, ...]:
        return tuple(asyncio.run(list_obs_audio_inputs(self.access.url, self.access.password)))

    def get_input(self, name: str) -> ObsAudioInput:
        return asyncio.run(get_obs_audio_input(self.access.url, self.access.password, name))

    def set_device(self, name: str, device_id: str) -> ObsAudioInput:
        return asyncio.run(set_obs_input_device(self.access.url, self.access.password, name, device_id))

    def activity(self) -> ObsOutputActivity:
        return asyncio.run(get_obs_output_activity(self.access.url, self.access.password))


class RvcRuntimeController:
    def __init__(
        self,
        *,
        main_manager: RvcMainServiceManager | None = None,
        worker_factory: Callable[[RvcSettings, str], Any] | None = None,
        direct_factory: Callable[[RvcSettings], Any] | None = None,
        main_client_factory: Callable[[RvcSettings], Any] | None = None,
        obs_factory: Callable[[ObsAccess], Any] = RvcObsApi,
        token_loader: Callable[[], str] = load_rvc_token,
        log: Callable[[str, str], None] | None = None,
    ) -> None:
        self.main_manager = main_manager or RvcMainServiceManager()
        self.worker_factory = worker_factory or (lambda settings, token: RvcWorkerApiClient(settings.worker_base_url, token))
        self.direct_factory = direct_factory or (lambda settings: RvcMmvcDirectClient(settings.worker_base_url))
        self.main_client_factory = main_client_factory or (lambda settings: RvcMainApiClient(settings.main_base_url))
        self.obs_factory = obs_factory
        self.token_loader = token_loader
        self.log = log or (lambda _level, _message: None)
        self.state = RvcRuntimeState.OFF
        self.last_error = ""
        self._lease: MainServiceLease | None = None
        self._obs_switched = False
        self._audio_started = False
        self._worker_ok = False
        self._processor_ready = False
        self._main_connected = False
        self._audio_running = False
        self._models: tuple[RvcModel, ...] = ()
        self._active_model: RvcModel | None = None
        self._audio_inputs: tuple[RvcAudioDevice, ...] = ()
        self._audio_outputs: tuple[RvcAudioDevice, ...] = ()
        self._obs_connected = False
        self._obs_inputs: tuple[ObsAudioInput, ...] = ()
        self._obs_current_device_id = ""
        self._obs_activity = ObsOutputActivity(False, False)
        self._log_path = ""
        self._audio_pipeline: dict[str, Any] = {}

    @staticmethod
    def _is_mmvc_direct(settings: RvcSettings) -> bool:
        return settings.worker_host in {"127.0.0.1", "localhost", "::1"} and settings.worker_port == 18888

    def snapshot(self) -> RvcRuntimeSnapshot:
        return RvcRuntimeSnapshot(
            state=self.state,
            worker_ok=self._worker_ok,
            processor_ready=self._processor_ready,
            main_connected=self._main_connected,
            audio_running=self._audio_running,
            main_owned=bool(self.main_manager.owned),
            main_pid=self.main_manager.owned_pid or (self._lease.pid if self._lease else None),
            models=self._models,
            active_model=self._active_model,
            audio_inputs=self._audio_inputs,
            audio_outputs=self._audio_outputs,
            obs_connected=self._obs_connected,
            obs_inputs=self._obs_inputs,
            obs_current_device_id=self._obs_current_device_id,
            obs_streaming=self._obs_activity.streaming,
            obs_recording=self._obs_activity.recording,
            last_error=self.last_error,
            log_path=self._log_path,
            audio_pipeline=dict(self._audio_pipeline),
        )

    def _direct_worker(self, settings: RvcSettings) -> Any:
        return self.direct_factory(settings)

    def start_mmvc(
        self,
        settings: RvcSettings,
        obs_access: ObsAccess,
    ) -> RvcRuntimeSnapshot:
        if not self._is_mmvc_direct(settings):
            raise RuntimeError("MMVC起動ボタンはメインPC（このPC）でのみ使用できます")
        settings.validate_connection()
        worker = self.direct_factory(settings)
        self.log("INFO", "ローカルMMVCプロセスと18888応答を確認")
        worker.ensure_running()
        action = "起動完了" if bool(getattr(worker, "last_ensure_started", False)) else "起動済み"
        self.log("INFO", f"ローカルMMVC: {action}")
        return self.refresh(settings, obs_access, ensure_main=True, refresh_obs=True)

    def refresh(
        self,
        settings: RvcSettings,
        obs_access: ObsAccess,
        *,
        ensure_main: bool,
        refresh_obs: bool = True,
    ) -> RvcRuntimeSnapshot:
        settings.validate_connection()
        direct = self._is_mmvc_direct(settings)
        token = "" if direct else self.token_loader()
        errors: list[str] = []
        try:
            worker = self._direct_worker(settings) if direct else self.worker_factory(settings, token)
            overview = worker.probe() if hasattr(worker, "probe") else worker.overview()
            self._apply_worker(overview)
            if overview.model_error:
                errors.append(overview.model_error)
        except Exception as exc:
            self._worker_ok = False
            self._processor_ready = False
            errors.append(self._short_error(exc))

        if refresh_obs:
            self._obs_connected = False
            try:
                obs = self.obs_factory(obs_access)
                self._obs_inputs = tuple(obs.list_inputs())
                self._obs_connected = True
                self._obs_activity = obs.activity()
                selected = next((item for item in self._obs_inputs if item.name == settings.obs_input_name), None)
                self._obs_current_device_id = selected.current_device_id if selected else ""
            except Exception as exc:
                if not self._obs_connected:
                    self._obs_inputs = ()
                    self._obs_current_device_id = ""
                errors.append(f"OBS: {self._short_error(exc)}")

        if direct:
            self._main_connected = True
            self._audio_running = self.state == RvcRuntimeState.ON
            self._audio_pipeline = {"state": "mmvc_direct"}
            self._log_path = str(RvcMmvcDirectClient.MMVC_LOG)
            if ensure_main:
                try:
                    devices = self.main_client_factory(settings).devices()
                    self._audio_inputs = devices.inputs
                    self._audio_outputs = devices.outputs
                except Exception as exc:
                    errors.append(f"main devices: {self._short_error(exc)}")
        else:
          try:
            if ensure_main:
                self._lease = self.main_manager.ensure_running(settings, token)
                client = self._lease.client
                client.wait_connected()
            else:
                client = self._lease.client if self._lease else RvcMainApiClient(settings.main_base_url)
            self._apply_main(client.status(), client, refresh_devices=ensure_main)
          except Exception as exc:
            self._main_connected = False
            self._audio_running = False
            if ensure_main or self._lease is not None:
                errors.append(f"main: {self._short_error(exc)}")

        self.last_error = " / ".join(dict.fromkeys(value for value in errors if value))
        if self.state == RvcRuntimeState.ERROR and not self.last_error and not self._audio_running:
            self.state = RvcRuntimeState.OFF
        if refresh_obs or ensure_main:
            self.log(
                "INFO",
                f"RVC再読込: worker={self._worker_ok} main={self._main_connected} obs={self._obs_connected}",
            )
        return self.snapshot()

    def select_model(self, settings: RvcSettings, slot_index: int) -> RvcRuntimeSnapshot:
        if self.state in {RvcRuntimeState.STARTING, RvcRuntimeState.STOPPING}:
            return self.snapshot()
        direct = self._is_mmvc_direct(settings)
        token = "" if direct else self.token_loader()
        worker = self._direct_worker(settings) if direct else self.worker_factory(settings, token)
        self.log("INFO", f"RVCモデル切替開始: slot={int(slot_index)}")
        worker.select_model(int(slot_index))
        self._apply_worker(worker.overview())
        self.last_error = ""
        self.log("INFO", f"RVCモデル切替完了: {self._active_model.name if self._active_model else '不明'}")
        return self.snapshot()

    def start(self, settings: RvcSettings, obs_access: ObsAccess) -> RvcRuntimeSnapshot:
        if self.state == RvcRuntimeState.ON:
            return self.snapshot()
        if self.state in {RvcRuntimeState.STARTING, RvcRuntimeState.STOPPING}:
            return self.snapshot()
        self.state = RvcRuntimeState.STARTING
        self.last_error = ""
        self.log("INFO", "RVC起動開始")
        try:
            direct = self._is_mmvc_direct(settings)
            if direct:
                settings.validate_connection()
            else:
                settings.validate_for_start()
            token = "" if direct else self.token_loader()
            worker = self._direct_worker(settings) if direct else self.worker_factory(settings, token)
            overview = worker.overview()
            self._apply_worker(overview)
            if not overview.processor_ready:
                raise RuntimeError("workerのRVC processorが準備できていません")
            if settings.model_slot_index is not None and (
                overview.active_model is None or overview.active_model.slot_index != settings.model_slot_index
            ):
                worker.select_model(settings.model_slot_index)
                self._apply_worker(worker.overview())

            obs = self.obs_factory(obs_access)
            selected_obs = obs.get_input(settings.obs_input_name)
            self._validate_obs_devices(selected_obs, settings)
            self._obs_inputs = tuple(obs.list_inputs())
            self._obs_activity = obs.activity()
            self._obs_current_device_id = selected_obs.current_device_id

            if direct:
                physical_name = next(
                    (
                        item.label
                        for item in selected_obs.devices
                        if item.id == settings.obs_off_device_id
                    ),
                    "",
                )
                if not physical_name:
                    raise RuntimeError("OBSの物理マイク名を取得できません")
                worker.start_audio(physical_name)
                switched = obs.set_device(settings.obs_input_name, settings.obs_on_device_id)
                self._obs_switched = True
                self._obs_current_device_id = switched.current_device_id
                self._main_connected = True
                self._audio_running = True
                self._audio_pipeline = {"state": "mmvc_direct"}
                self._log_path = str(RvcMmvcDirectClient.MMVC_LOG)
                self.state = RvcRuntimeState.ON
                self.last_error = ""
                self.log("INFO", "RVC起動完了: ローカルMMVC直接接続でOBSをRVCへ切替")
                return self.snapshot()

            self._lease = self.main_manager.ensure_running(settings, token)
            client = self._lease.client
            status = client.wait_connected()
            self._apply_main(status, client, refresh_devices=True)
            self._validate_audio_devices(settings)
            client.start_audio(settings.input_device_id, settings.output_device_id)
            self._audio_started = True
            status = client.status()
            self._apply_main(status, client, refresh_devices=False)
            if not self._audio_running:
                raise RuntimeError("音声経路の開始を確認できません")

            switched = obs.set_device(settings.obs_input_name, settings.obs_on_device_id)
            self._obs_switched = True
            self._obs_current_device_id = switched.current_device_id
            self.state = RvcRuntimeState.ON
            self.last_error = ""
            self.log("INFO", "RVC起動完了: 音声経路開始後にOBSをRVCへ切替")
            return self.snapshot()
        except Exception as exc:
            message = self._short_error(exc)
            self._rollback_start(settings, obs_access)
            self.state = RvcRuntimeState.ERROR
            self.last_error = message
            self.log("ERROR", f"RVC起動失敗: {message}")
            raise RvcRuntimeError(message, self.snapshot()) from None

    def stop(self, settings: RvcSettings, obs_access: ObsAccess) -> RvcRuntimeSnapshot:
        if self.state in {RvcRuntimeState.STARTING, RvcRuntimeState.STOPPING}:
            return self.snapshot()
        self.state = RvcRuntimeState.STOPPING
        self.log("INFO", "RVC停止開始")
        errors: list[str] = []
        if self._obs_switched:
            try:
                restored = self.obs_factory(obs_access).set_device(settings.obs_input_name, settings.obs_off_device_id)
                self._obs_current_device_id = restored.current_device_id
                self._obs_switched = False
            except Exception as exc:
                errors.append(f"OBS復元: {self._short_error(exc)}")
        if self._is_mmvc_direct(settings):
            try:
                self.direct_factory(settings).stop_audio()
            except Exception as exc:
                errors.append(f"MMVC音声停止: {self._short_error(exc)}")
            self._audio_started = False
            self._audio_running = False
            self._main_connected = True
            self.state = RvcRuntimeState.ERROR if errors else RvcRuntimeState.OFF
            self.last_error = " / ".join(errors)
            if errors:
                raise RvcRuntimeError(self.last_error, self.snapshot())
            self.log("INFO", "RVC停止完了: ローカルMMVC直接接続からOBSを復元")
            return self.snapshot()
        try:
            client = self._lease.client if self._lease else RvcMainApiClient(settings.main_base_url)
            client.stop_audio()
            self._audio_started = False
            self._audio_running = False
        except Exception as exc:
            errors.append(f"音声停止: {self._short_error(exc)}")
        try:
            self.main_manager.stop_owned()
        except Exception as exc:
            errors.append(f"所有サービス停止: {self._short_error(exc)}")
        self._lease = None
        self._main_connected = False
        self.state = RvcRuntimeState.ERROR if errors else RvcRuntimeState.OFF
        self.last_error = " / ".join(errors)
        level = "ERROR" if errors else "INFO"
        self.log(level, f"RVC停止結果: {self.last_error or 'OBS復元・音声停止・所有サービス停止完了'}")
        if errors:
            raise RvcRuntimeError(self.last_error, self.snapshot())
        return self.snapshot()

    def shutdown(self, settings: RvcSettings, obs_access: ObsAccess) -> RvcRuntimeSnapshot:
        if self.state == RvcRuntimeState.ON or self._obs_switched or self._audio_started:
            return self.stop(settings, obs_access)
        self.main_manager.stop_owned()
        self._lease = None
        self._main_connected = False
        self._audio_running = False
        self.state = RvcRuntimeState.OFF
        return self.snapshot()

    def _apply_worker(self, overview: RvcWorkerOverview) -> None:
        self._worker_ok = True
        self._processor_ready = overview.processor_ready
        self._models = overview.models
        self._active_model = overview.active_model

    def _apply_main(
        self,
        status: dict[str, Any],
        client: RvcMainApiClient,
        *,
        refresh_devices: bool,
    ) -> None:
        self._main_connected = bool(status.get("connected")) and bool(status.get("authorized"))
        audio = status.get("audio") if isinstance(status.get("audio"), dict) else {}
        self._audio_running = bool(audio.get("running"))
        pipeline = audio.get("pipeline") if isinstance(audio.get("pipeline"), dict) else status.get("pipeline")
        self._audio_pipeline = dict(pipeline) if isinstance(pipeline, dict) else {}
        self._log_path = str(status.get("logPath") or self._log_path)
        if refresh_devices:
            devices = client.devices()
            self._audio_inputs = devices.inputs
            self._audio_outputs = devices.outputs

    def _validate_audio_devices(self, settings: RvcSettings) -> None:
        input_ids = {item.id for item in self._audio_inputs}
        output_ids = {item.id for item in self._audio_outputs}
        if settings.input_device_id not in input_ids:
            raise RuntimeError("選択した入力マイクがメインPCにありません")
        if settings.output_device_id not in output_ids:
            raise RuntimeError("選択した変換音声の書込先がメインPCにありません")

    @staticmethod
    def _validate_obs_devices(obs_input: ObsAudioInput, settings: RvcSettings) -> None:
        ids = {item.id for item in obs_input.devices if item.enabled}
        if settings.obs_off_device_id not in ids:
            raise RuntimeError("RVC OFF時のOBSマイクデバイスが見つかりません")
        if settings.obs_on_device_id not in ids:
            raise RuntimeError("RVC ON時のOBSマイクデバイスが見つかりません")

    def _rollback_start(self, settings: RvcSettings, obs_access: ObsAccess) -> None:
        if settings.obs_input_name and settings.obs_off_device_id:
            try:
                restored = self.obs_factory(obs_access).set_device(settings.obs_input_name, settings.obs_off_device_id)
                self._obs_current_device_id = restored.current_device_id
                self._obs_switched = False
            except Exception as exc:
                self.log("ERROR", f"RVCロールバックOBS復元失敗: {self._short_error(exc)}")
        if self._audio_started or self._lease is not None:
            try:
                client = self._lease.client if self._lease else RvcMainApiClient(settings.main_base_url)
                client.stop_audio()
            except Exception as exc:
                self.log("ERROR", f"RVCロールバック音声停止失敗: {self._short_error(exc)}")
        self._audio_started = False
        self._audio_running = False
        try:
            self.main_manager.stop_owned()
        except Exception as exc:
            self.log("ERROR", f"RVCロールバック所有サービス停止失敗: {self._short_error(exc)}")
        self._lease = None
        self._main_connected = False

    def _short_error(self, exc: BaseException) -> str:
        message = str(exc).strip() or type(exc).__name__
        try:
            token = self.token_loader()
        except Exception:
            token = ""
        if token:
            message = message.replace(token, "[secret]")
        return message[:240]
