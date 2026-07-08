from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class SpyLookLog(SQLModel, table=True):
    __tablename__ = "spy_look_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    path: Optional[str] = Field(default=None)
    model: Optional[str] = Field(default=None)
    upstream_model: Optional[str] = Field(default=None)
    status_code: Optional[int] = Field(default=None)
    latency_ms: Optional[int] = Field(default=None)
    client_ip: Optional[str] = Field(default=None)
    input_tokens: Optional[int] = Field(default=None)
    output_tokens: Optional[int] = Field(default=None)
    total_tokens: Optional[int] = Field(default=None)
    request_body: Optional[str] = Field(default=None)
    response_body: Optional[str] = Field(default=None)
    session_id: str = Field(default="default")
    app_id: str = Field(default="unknown")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SpyLookUpstream(SQLModel, table=True):
    __tablename__ = "spy_look_upstreams"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    base_url: str
    api_key: str
    trust_env: bool = Field(default=False)
    timeout_seconds: float = Field(default=60.0)
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SpyLookClientKey(SQLModel, table=True):
    __tablename__ = "spy_look_client_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    api_key: str = Field(unique=True)
    app_id: str = Field(unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SpyLookPendingGatewayKey(SQLModel, table=True):
    __tablename__ = "spy_look_pending_gateway_keys"

    api_key: str = Field(primary_key=True)
    expires_at: float


class SpyLookPublicModel(SQLModel, table=True):
    __tablename__ = "spy_look_public_models"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SpyLookPublicModelRoute(SQLModel, table=True):
    __tablename__ = "spy_look_public_model_routes"

    id: Optional[int] = Field(default=None, primary_key=True)
    public_model_id: int = Field(foreign_key="spy_look_public_models.id", index=True)
    upstream_id: int = Field(foreign_key="spy_look_upstreams.id", index=True)
    upstream_model: str
    sort_order: int = Field(default=0)
    enabled: bool = Field(default=True)
