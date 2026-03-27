import asyncio
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.schemas import ServiceStatus
from app.services.log_broker import LogBroker
from app.services.process_manager import ExternalControlError, ProcessManager, ServiceRuntime


class DummyProcess:
    def __init__(self, running: bool, pid: int = 1111):
        self.running = running
        self.pid = pid

    def poll(self):
        return None if self.running else 0


def make_runtime() -> ServiceRuntime:
    return ServiceRuntime(
        name="metaclaw",
        workdir="C:\\tmp",
        command="cmd /c echo hi",
        port=30000,
    )


def test_status_classification():
    runtime = make_runtime()
    assert ProcessManager._derive_status(runtime, reachable=False) == "offline"

    runtime.process = DummyProcess(running=True)
    runtime.state = "starting"
    assert ProcessManager._derive_status(runtime, reachable=False) == "starting"
    assert ProcessManager._derive_status(runtime, reachable=True) == "online_managed"

    runtime.process = None
    runtime.state = "offline"
    assert ProcessManager._derive_status(runtime, reachable=True) == "online_external"

    runtime.state = "error"
    assert ProcessManager._derive_status(runtime, reachable=False) == "error"


def test_external_stop_policy_raises(tmp_path: Path):
    settings = Settings(
        gateway_auto_connect_enabled=False,
        metaclaw_workdir=str(tmp_path),
        picoclaw_workdir=str(tmp_path),
    )
    manager = ProcessManager(settings=settings, log_broker=LogBroker())

    def fake_probe(_runtime):
        return True, "tcp:open"

    manager._probe = fake_probe  # type: ignore[method-assign]

    try:
        try:
            manager._stop_service_blocking("metaclaw")
            assert False, "Expected ExternalControlError"
        except ExternalControlError:
            assert True
    finally:
        manager.shutdown()


def test_ensure_metaclaw_ready_starts_if_needed(tmp_path: Path):
    settings = Settings(
        gateway_auto_connect_enabled=False,
        metaclaw_workdir=str(tmp_path),
        picoclaw_workdir=str(tmp_path),
    )
    manager = ProcessManager(settings=settings, log_broker=LogBroker())
    called = []

    offline = ServiceStatus(
        name="metaclaw",
        status="offline",
        managed=False,
        pid=None,
        port=30000,
        reachable=False,
        last_probe="n/a",
        last_error=None,
        updated_at=datetime.now(timezone.utc),
    )
    online = ServiceStatus(
        name="metaclaw",
        status="online_managed",
        managed=True,
        pid=1234,
        port=30000,
        reachable=True,
        last_probe="tcp:open",
        last_error=None,
        updated_at=datetime.now(timezone.utc),
    )
    statuses = [offline, online]

    def fake_get_status(_name):
        return statuses.pop(0) if statuses else online

    async def fake_start(_name):
        called.append("metaclaw")
        return online, "ok"

    manager.get_service_status = fake_get_status  # type: ignore[method-assign]
    manager.start_service = fake_start  # type: ignore[method-assign]

    try:
        asyncio.run(manager.ensure_metaclaw_ready())
        assert called == ["metaclaw"]
    finally:
        manager.shutdown()

