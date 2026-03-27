from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ServiceName = Literal["metaclaw", "picoclaw"]
ServiceStatusValue = Literal[
    "offline",
    "starting",
    "online_managed",
    "online_external",
    "stopping",
    "error",
]


class AuthSessionCreate(BaseModel):
    api_key: str = Field(min_length=8, max_length=256)


class AuthSessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    key_id: int
    key_name: str


class KeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class KeyItem(BaseModel):
    id: int
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    active: bool


class KeyCreateResponse(BaseModel):
    id: int
    name: str
    prefix: str
    api_key: str
    created_at: datetime


class GenericMessage(BaseModel):
    message: str


class ServiceStatus(BaseModel):
    name: ServiceName
    status: ServiceStatusValue
    managed: bool
    pid: int | None
    port: int
    reachable: bool
    last_probe: str
    last_error: str | None
    updated_at: datetime


class StatusResponse(BaseModel):
    services: list[ServiceStatus]
    timestamp: datetime


class ServiceActionResponse(BaseModel):
    service: ServiceName
    status: ServiceStatusValue
    message: str


class LogEntry(BaseModel):
    timestamp: datetime
    service: ServiceName
    stream: Literal["stdout", "stderr", "system", "file"]
    source: Literal["managed", "external", "system"]
    message: str

