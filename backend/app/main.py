import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, get_settings
from .database import Base, create_engine_and_session
from .models import APIKey
from .routers import auth, keys, logs, services
from .security import hash_api_key, key_prefix
from .services.gateway_client import GatewayClient
from .services.log_broker import LogBroker
from .services.process_manager import ProcessManager


async def status_monitor_loop(app: FastAPI) -> None:
    settings = app.state.settings
    manager = app.state.process_manager
    gateway = app.state.gateway_client

    while True:
        try:
            statuses = manager.get_all_statuses()
            status_map = {item.name: item for item in statuses}
            pico = status_map["picoclaw"]
            if (
                settings.gateway_auto_connect_enabled
                and pico.managed
                and not pico.reachable
                and pico.status in {"starting", "error"}
            ):
                await asyncio.to_thread(gateway.connect, "auto:not_reachable", False)
        except Exception as exc:
            app.state.log_broker.publish("picoclaw", "stderr", f"Monitor loop error: {exc}", source="system")
        await asyncio.sleep(max(0.5, settings.health_poll_seconds))


def _seed_initial_key(app: FastAPI) -> None:
    session_local = app.state.session_local
    db = session_local()
    try:
        key_count = db.query(APIKey).count()
        if key_count > 0:
            return
        plain = app.state.settings.initial_admin_key
        salt, hashed = hash_api_key(plain)
        item = APIKey(
            name="Initial Admin Key",
            key_prefix=key_prefix(plain),
            key_hash=hashed,
            key_salt=salt,
            active=True,
        )
        db.add(item)
        db.commit()
        app.state.log_broker.publish(
            "metaclaw",
            "system",
            "Created initial admin key from INITIAL_ADMIN_KEY environment variable.",
            source="system",
        )
    finally:
        db.close()


def create_app(settings_override: Settings | None = None) -> FastAPI:
    settings = settings_override or get_settings()
    engine, session_local = create_engine_and_session(settings.database_url)
    log_broker = LogBroker(max_entries=settings.app_log_buffer_size)
    process_manager = ProcessManager(settings=settings, log_broker=log_broker)
    gateway_client = GatewayClient(settings=settings, log_broker=log_broker)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Base.metadata.create_all(bind=engine)
        _seed_initial_key(app)
        log_broker.bind_loop(asyncio.get_running_loop())
        monitor_task = asyncio.create_task(status_monitor_loop(app))
        app.state.monitor_task = monitor_task
        yield
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        process_manager.shutdown()
        engine.dispose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.settings = settings
    app.state.engine = engine
    app.state.session_local = session_local
    app.state.log_broker = log_broker
    app.state.process_manager = process_manager
    app.state.gateway_client = gateway_client

    app.include_router(auth.router)
    app.include_router(keys.router)
    app.include_router(services.router)
    app.include_router(logs.router)

    @app.get("/")
    def root():
        return {"name": settings.app_name, "ok": True}

    return app


# Uvicorn needs `app` at module level (referenced as `app.main:app`), but during
# test collection pytest also imports this module. Calling create_app() without
# env vars set raises a validation error. So we guard with a try/except: if
# required settings are missing, we skip eager creation — tests use create_app()
# directly with explicit settings overrides.
try:
    app = create_app()
except Exception:
    # Likely missing env vars during test collection; tests create their own app.
    app = None  # type: ignore[assignment]

