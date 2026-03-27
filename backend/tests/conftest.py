from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def client(tmp_path: Path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        jwt_secret="test-secret",
        initial_admin_key="test-initial-key",
        gateway_auto_connect_enabled=False,
        metaclaw_workdir=str(tmp_path),
        picoclaw_workdir=str(tmp_path),
        metaclaw_command="cmd /c echo metaclaw",
        picoclaw_command="cmd /c echo picoclaw",
        startup_wait_seconds=1.0,
        stop_timeout_seconds=1.0,
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client

