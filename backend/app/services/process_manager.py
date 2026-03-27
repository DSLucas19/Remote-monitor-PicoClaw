import asyncio
import os
import shlex
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from ..config import Settings
from ..schemas import ServiceName, ServiceStatus
from .heartbeat import probe_http_then_tcp
from .log_broker import LogBroker


class ServiceActionError(Exception):
    pass


class ExternalControlError(ServiceActionError):
    pass


@dataclass
class ServiceRuntime:
    name: ServiceName
    workdir: str
    command: str
    port: int
    log_file: str = ""
    process: subprocess.Popen[str] | None = None
    state: str = "offline"
    last_error: str | None = None
    last_probe: str = "n/a"
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    lock: threading.RLock = field(default_factory=threading.RLock)
    tail_stop: threading.Event = field(default_factory=threading.Event)


class ProcessManager:
    def __init__(self, settings: Settings, log_broker: LogBroker):
        self.settings = settings
        self.log_broker = log_broker
        self._shutdown = threading.Event()
        self._runtimes: dict[ServiceName, ServiceRuntime] = {
            "metaclaw": ServiceRuntime(
                name="metaclaw",
                workdir=settings.metaclaw_workdir,
                command=settings.metaclaw_command,
                port=settings.metaclaw_port,
                log_file=settings.metaclaw_log_file.strip(),
            ),
            "picoclaw": ServiceRuntime(
                name="picoclaw",
                workdir=settings.picoclaw_workdir,
                command=settings.picoclaw_command,
                port=settings.picoclaw_port,
                log_file=settings.picoclaw_log_file.strip(),
            ),
        }
        self._start_file_tailers()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _derive_status(runtime: ServiceRuntime, reachable: bool) -> str:
        managed_running = runtime.process is not None and runtime.process.poll() is None

        if runtime.state == "stopping" and managed_running:
            return "stopping"
        if managed_running:
            if reachable:
                return "online_managed"
            if runtime.state in {"error", "stopping"}:
                return runtime.state
            return "starting"
        if reachable:
            return "online_external"
        if runtime.state == "error":
            return "error"
        return "offline"

    def _runtime(self, service: ServiceName) -> ServiceRuntime:
        return self._runtimes[service]

    def _tokenize(self, command: str) -> list[str]:
        return shlex.split(command, posix=False)

    def _probe(self, runtime: ServiceRuntime) -> tuple[bool, str]:
        reachable, details = probe_http_then_tcp("127.0.0.1", runtime.port)
        with runtime.lock:
            runtime.last_probe = details
            runtime.updated_at = self._now()
        return reachable, details

    def _set_state(self, runtime: ServiceRuntime, state: str, error: str | None = None) -> None:
        with runtime.lock:
            runtime.state = state
            if error is not None:
                runtime.last_error = error
            elif state != "error":
                runtime.last_error = None
            runtime.updated_at = self._now()

    def _start_file_tailers(self) -> None:
        for runtime in self._runtimes.values():
            if not runtime.log_file:
                continue
            thread = threading.Thread(target=self._tail_file_loop, args=(runtime,), daemon=True)
            thread.start()

    def _tail_file_loop(self, runtime: ServiceRuntime) -> None:
        path = Path(runtime.log_file)
        warned_missing = False
        while not self._shutdown.is_set() and not runtime.tail_stop.is_set():
            if not path.exists():
                if not warned_missing:
                    self.log_broker.publish(
                        runtime.name,
                        "system",
                        f"Configured log file not found yet: {path}",
                        source="external",
                    )
                    warned_missing = True
                time.sleep(1.0)
                continue
            warned_missing = False
            try:
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    handle.seek(0, os.SEEK_END)
                    while not self._shutdown.is_set() and not runtime.tail_stop.is_set():
                        line = handle.readline()
                        if line:
                            self.log_broker.publish(runtime.name, "file", line, source="external")
                        else:
                            time.sleep(0.3)
            except Exception as exc:
                self.log_broker.publish(
                    runtime.name,
                    "stderr",
                    f"Log tailer error: {exc}",
                    source="external",
                )
                time.sleep(1.0)

    def _read_pipe(
        self,
        runtime: ServiceRuntime,
        stream_name: Literal["stdout", "stderr"],
        pipe,
    ) -> None:
        if pipe is None:
            return
        try:
            for line in iter(pipe.readline, ""):
                if not line:
                    break
                self.log_broker.publish(runtime.name, stream_name, line, source="managed")
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    def _wait_for_exit(self, runtime: ServiceRuntime, process: subprocess.Popen[str]) -> None:
        return_code = process.wait()
        with runtime.lock:
            if runtime.process is process:
                runtime.process = None
                if return_code == 0:
                    runtime.state = "offline"
                    runtime.last_error = None
                else:
                    runtime.state = "error"
                    runtime.last_error = f"Process exited with code {return_code}"
                runtime.updated_at = self._now()
        self.log_broker.publish(
            runtime.name,
            "system",
            f"Managed process exited with code {return_code}",
            source="managed",
        )

    def _wait_until_ready(
        self,
        runtime: ServiceRuntime,
        process: subprocess.Popen[str] | None,
        timeout_seconds: float,
    ) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline and not self._shutdown.is_set():
            reachable, _ = self._probe(runtime)
            if reachable:
                return True
            if process is not None and process.poll() is not None:
                return False
            time.sleep(0.5)
        return False

    def _start_service_blocking(self, service: ServiceName) -> tuple[ServiceStatus, str]:
        runtime = self._runtime(service)
        with runtime.lock:
            managed_running = runtime.process is not None and runtime.process.poll() is None
            if managed_running:
                return self.get_service_status(service), "Service is already running (managed)."

        reachable, _ = self._probe(runtime)
        if reachable:
            self._set_state(runtime, "offline")
            return self.get_service_status(service), "Service is already running outside dashboard (external)."

        workdir = Path(runtime.workdir)
        if not workdir.exists():
            self._set_state(runtime, "error", f"Working directory not found: {workdir}")
            raise ServiceActionError(f"Working directory not found: {workdir}")

        cmd = self._tokenize(runtime.command)
        if not cmd:
            self._set_state(runtime, "error", "Command is empty.")
            raise ServiceActionError("Command is empty.")

        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(workdir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except Exception as exc:
            self._set_state(runtime, "error", f"Failed to start process: {exc}")
            raise ServiceActionError(f"Failed to start process: {exc}") from exc

        with runtime.lock:
            runtime.process = process
            runtime.state = "starting"
            runtime.last_error = None
            runtime.updated_at = self._now()

        threading.Thread(
            target=self._read_pipe,
            args=(runtime, "stdout", process.stdout),
            daemon=True,
        ).start()
        threading.Thread(
            target=self._read_pipe,
            args=(runtime, "stderr", process.stderr),
            daemon=True,
        ).start()
        threading.Thread(target=self._wait_for_exit, args=(runtime, process), daemon=True).start()

        self.log_broker.publish(
            runtime.name,
            "system",
            f"Started managed process (pid={process.pid})",
            source="managed",
        )

        ready = self._wait_until_ready(runtime, process, timeout_seconds=self.settings.startup_wait_seconds)
        if ready:
            self._set_state(runtime, "offline")
            status = self.get_service_status(service)
            return status, "Service started successfully."

        with runtime.lock:
            current_process = runtime.process
        if current_process is process and process.poll() is None:
            self._set_state(runtime, "error", "Service did not become reachable before timeout.")
        status = self.get_service_status(service)
        raise ServiceActionError("Service started but heartbeat did not become reachable in time.")

    def _stop_service_blocking(
        self,
        service: ServiceName,
        allow_if_already_offline: bool = False,
    ) -> tuple[ServiceStatus, str]:
        runtime = self._runtime(service)
        with runtime.lock:
            process = runtime.process
            managed_running = process is not None and process.poll() is None

        if not managed_running:
            reachable, _ = self._probe(runtime)
            if reachable:
                raise ExternalControlError(
                    "Service is running externally. Stop/Restart is disabled for external processes."
                )
            if allow_if_already_offline:
                self._set_state(runtime, "offline")
                return self.get_service_status(service), "Service is already offline."
            raise ServiceActionError("Service is already offline.")

        self._set_state(runtime, "stopping")
        assert process is not None
        try:
            process.terminate()
            process.wait(timeout=self.settings.stop_timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=self.settings.stop_timeout_seconds)
        except Exception as exc:
            self._set_state(runtime, "error", f"Failed stopping process: {exc}")
            raise ServiceActionError(f"Failed stopping process: {exc}") from exc

        with runtime.lock:
            if runtime.process is process:
                runtime.process = None
                runtime.state = "offline"
                runtime.updated_at = self._now()
        status = self.get_service_status(service)
        self.log_broker.publish(runtime.name, "system", "Managed process stopped.", source="managed")
        return status, "Service stopped."

    async def ensure_metaclaw_ready(self) -> None:
        status = self.get_service_status("metaclaw")
        if status.status in {"online_managed", "online_external"}:
            return
        if status.status == "starting" and status.managed:
            ready = await asyncio.to_thread(
                self._wait_until_ready,
                self._runtime("metaclaw"),
                self._runtime("metaclaw").process,
                self.settings.startup_wait_seconds,
            )
            if not ready:
                raise ServiceActionError("MetaClaw is still not reachable.")
            return
        await self.start_service("metaclaw")
        post_start = self.get_service_status("metaclaw")
        if post_start.status not in {"online_managed", "online_external"}:
            raise ServiceActionError("MetaClaw did not become ready, refusing to start PicoClaw.")

    async def start_service(self, service: ServiceName) -> tuple[ServiceStatus, str]:
        if service == "picoclaw":
            await self.ensure_metaclaw_ready()
        return await asyncio.to_thread(self._start_service_blocking, service)

    async def stop_service(self, service: ServiceName) -> tuple[ServiceStatus, str]:
        return await asyncio.to_thread(self._stop_service_blocking, service)

    async def restart_service(self, service: ServiceName) -> tuple[ServiceStatus, str]:
        status = self.get_service_status(service)
        if status.status == "online_external":
            raise ExternalControlError(
                "Service is running externally. Restart is disabled for external processes."
            )
        try:
            await asyncio.to_thread(self._stop_service_blocking, service, True)
        except ServiceActionError:
            pass
        return await self.start_service(service)

    def get_service_status(self, service: ServiceName) -> ServiceStatus:
        runtime = self._runtime(service)
        reachable, probe_details = self._probe(runtime)
        with runtime.lock:
            status_value = self._derive_status(runtime, reachable)
            managed_running = runtime.process is not None and runtime.process.poll() is None
            pid = runtime.process.pid if managed_running and runtime.process is not None else None
            runtime.updated_at = self._now()
            updated_at = runtime.updated_at
            last_error = runtime.last_error
        return ServiceStatus(
            name=service,
            status=status_value,  # type: ignore[arg-type]
            managed=managed_running,
            pid=pid,
            port=runtime.port,
            reachable=reachable,
            last_probe=probe_details,
            last_error=last_error,
            updated_at=updated_at,
        )

    def get_all_statuses(self) -> list[ServiceStatus]:
        return [self.get_service_status("metaclaw"), self.get_service_status("picoclaw")]

    def shutdown(self) -> None:
        self._shutdown.set()
        for runtime in self._runtimes.values():
            runtime.tail_stop.set()
        for service in ("picoclaw", "metaclaw"):
            runtime = self._runtime(service)  # type: ignore[arg-type]
            with runtime.lock:
                process = runtime.process
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=3)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass

