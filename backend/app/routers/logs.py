from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket
from sqlalchemy.orm import Session

from ..dependencies import get_current_key, get_db
from ..models import APIKey
from ..schemas import LogEntry, ServiceName
from ..security import decode_session_token


router = APIRouter(tags=["logs"])


def _parse_service_filter(service: str | None) -> ServiceName | None:
    if service is None:
        return None
    if service not in {"metaclaw", "picoclaw"}:
        raise HTTPException(status_code=400, detail="Invalid service filter")
    return service  # type: ignore[return-value]


@router.get("/api/logs", response_model=list[LogEntry])
def list_logs(
    request: Request,
    service: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
    _current_key: APIKey = Depends(get_current_key),
):
    broker = request.app.state.log_broker
    service_filter = _parse_service_filter(service)
    return broker.history(service=service_filter, limit=limit)


@router.websocket("/ws/logs")
async def logs_websocket(
    websocket: WebSocket,
    token: str = Query(default=""),
    service: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
):
    if not token:
        await websocket.close(code=4401)
        return

    app = websocket.app
    settings = app.state.settings
    session_local = app.state.session_local

    try:
        payload = decode_session_token(settings, token)
        key_id = int(payload["sub"])
        db: Session = session_local()
        try:
            key = db.query(APIKey).filter(APIKey.id == key_id, APIKey.active.is_(True)).first()
        finally:
            db.close()
    except Exception:
        await websocket.close(code=4401)
        return

    if key is None:
        await websocket.close(code=4401)
        return

    broker = app.state.log_broker
    try:
        service_filter = _parse_service_filter(service)
    except HTTPException:
        await websocket.close(code=4400)
        return

    backlog = broker.history(service=service_filter, limit=limit)
    await broker.register(websocket, backlog)

    try:
        while True:
            await websocket.receive_text()
    except Exception:
        await broker.unregister(websocket)

