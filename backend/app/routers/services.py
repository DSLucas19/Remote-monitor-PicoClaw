import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..dependencies import get_current_key
from ..models import APIKey
from ..schemas import ServiceActionResponse, ServiceName, StatusResponse
from ..services.process_manager import ExternalControlError, ServiceActionError


router = APIRouter(prefix="/api", tags=["services"])


def _resolve_service(service: str) -> ServiceName:
    if service not in {"metaclaw", "picoclaw"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown service")
    return service  # type: ignore[return-value]


@router.get("/status", response_model=StatusResponse)
def get_status(
    request: Request,
    _current_key: APIKey = Depends(get_current_key),
):
    manager = request.app.state.process_manager
    services = manager.get_all_statuses()
    return StatusResponse(services=services, timestamp=datetime.now(timezone.utc))


@router.post("/services/{service}/start", response_model=ServiceActionResponse)
async def start_service(
    service: str,
    request: Request,
    _current_key: APIKey = Depends(get_current_key),
):
    manager = request.app.state.process_manager
    service_name = _resolve_service(service)
    try:
        status_data, message = await manager.start_service(service_name)
        return ServiceActionResponse(service=service_name, status=status_data.status, message=message)
    except ServiceActionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/services/{service}/stop", response_model=ServiceActionResponse)
async def stop_service(
    service: str,
    request: Request,
    _current_key: APIKey = Depends(get_current_key),
):
    manager = request.app.state.process_manager
    service_name = _resolve_service(service)
    try:
        status_data, message = await manager.stop_service(service_name)
        return ServiceActionResponse(service=service_name, status=status_data.status, message=message)
    except ExternalControlError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ServiceActionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/services/{service}/restart", response_model=ServiceActionResponse)
async def restart_service(
    service: str,
    request: Request,
    _current_key: APIKey = Depends(get_current_key),
):
    manager = request.app.state.process_manager
    service_name = _resolve_service(service)
    try:
        status_data, message = await manager.restart_service(service_name)
        return ServiceActionResponse(service=service_name, status=status_data.status, message=message)
    except ExternalControlError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ServiceActionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/services/picoclaw/gateway/connect", response_model=ServiceActionResponse)
async def gateway_connect(
    request: Request,
    _current_key: APIKey = Depends(get_current_key),
):
    gateway_client = request.app.state.gateway_client
    ok, message = await asyncio.to_thread(gateway_client.connect, "manual", True)
    manager = request.app.state.process_manager
    status_data = manager.get_service_status("picoclaw")
    status_value = status_data.status
    if not ok and status_value != "error":
        status_value = "error"
    return ServiceActionResponse(service="picoclaw", status=status_value, message=message)
