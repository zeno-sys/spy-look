from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, LargeBinary, Text, UniqueConstraint
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


class SpyLookMdDocument(SQLModel, table=True):
    __tablename__ = "spy_look_md_documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(default="未命名.md", index=True)
    content: str = Field(default="", sa_column=Column(Text, nullable=False))
    content_bytes: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SpyLookMdDocumentImage(SQLModel, table=True):
    __tablename__ = "spy_look_md_document_images"

    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="spy_look_md_documents.id", index=True)
    filename: str = Field(default="image.png")
    content_type: str = Field(default="image/png")
    data: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SpyLookMdRecentOpen(SQLModel, table=True):
    __tablename__ = "spy_look_md_recent_opens"

    document_id: int = Field(primary_key=True, foreign_key="spy_look_md_documents.id")
    opened_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class SpyLookAgentSkill(SQLModel, table=True):
    __tablename__ = "spy_look_agent_skills"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: str = Field(default="", sa_column=Column(Text, nullable=False))
    current_version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SpyLookAgentSkillVersion(SQLModel, table=True):
    __tablename__ = "spy_look_agent_skill_versions"
    __table_args__ = (UniqueConstraint("skill_id", "version", name="uq_agent_skill_version"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    skill_id: int = Field(foreign_key="spy_look_agent_skills.id", index=True)
    version: int
    changelog: str = Field(default="", sa_column=Column(Text, nullable=False))
    package_zip: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    size_bytes: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SpyLookAgentSkillTag(SQLModel, table=True):
    __tablename__ = "spy_look_agent_skill_tags"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    color: str = Field(default="#64748b")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SpyLookAgentSkillTagLink(SQLModel, table=True):
    __tablename__ = "spy_look_agent_skill_tag_links"

    skill_id: int = Field(primary_key=True, foreign_key="spy_look_agent_skills.id")
    tag_id: int = Field(primary_key=True, foreign_key="spy_look_agent_skill_tags.id", index=True)


class SpyLookUser(SQLModel, table=True):
    __tablename__ = "spy_look_users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    role: str = Field(default="admin", index=True)  # owner | admin
    disabled: bool = Field(default=False)
    failed_login_count: int = Field(default=0)
    locked_until: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SpyLookSession(SQLModel, table=True):
    __tablename__ = "spy_look_sessions"

    id: str = Field(primary_key=True)  # session token
    user_id: int = Field(foreign_key="spy_look_users.id", index=True)
    expires_at: datetime = Field(index=True)
    remember: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)
