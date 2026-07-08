from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from db.models import SpyLookPublicModel, SpyLookPublicModelRoute, SpyLookUpstream


@dataclass(slots=True)
class ResolvedModelRoute:
    upstream_row: dict[str, Any]
    upstream_model: str


async def _scalar_one(session: AsyncSession, stmt) -> Any:
    result = await session.execute(stmt)
    return result.scalars().first()


async def _scalar_all(session: AsyncSession, stmt) -> list[Any]:
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _route_dict(route: SpyLookPublicModelRoute, upstream_name: str | None = None) -> dict[str, Any]:
    d = route.model_dump(mode="json")
    if upstream_name is not None:
        d["upstream_name"] = upstream_name
    return d


def _public_model_dict(
    model: SpyLookPublicModel,
    routes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    d = model.model_dump(mode="json")
    if routes is not None:
        d["routes"] = routes
    return d


async def _load_routes_for_models(
    session: AsyncSession,
    model_ids: list[int],
) -> dict[int, list[dict[str, Any]]]:
    if not model_ids:
        return {}
    stmt = (
        select(SpyLookPublicModelRoute, SpyLookUpstream.name)
        .join(SpyLookUpstream, SpyLookUpstream.id == SpyLookPublicModelRoute.upstream_id)
        .where(SpyLookPublicModelRoute.public_model_id.in_(model_ids))
        .order_by(
            SpyLookPublicModelRoute.public_model_id.asc(),
            SpyLookPublicModelRoute.sort_order.asc(),
            SpyLookPublicModelRoute.id.asc(),
        )
    )
    rows = await session.execute(stmt)
    grouped: dict[int, list[dict[str, Any]]] = {mid: [] for mid in model_ids}
    for route, upstream_name in rows.all():
        grouped.setdefault(route.public_model_id, []).append(
            _route_dict(route, upstream_name=str(upstream_name or ""))
        )
    return grouped


async def list_public_models(session: AsyncSession) -> list[dict[str, Any]]:
    models = await _scalar_all(
        session,
        select(SpyLookPublicModel).order_by(SpyLookPublicModel.id.asc()),
    )
    if not models:
        return []
    model_ids = [m.id for m in models if m.id is not None]
    routes_by_model = await _load_routes_for_models(session, model_ids)
    return [
        _public_model_dict(model, routes_by_model.get(model.id or 0, []))
        for model in models
    ]


async def get_public_model(session: AsyncSession, model_id: int) -> dict[str, Any] | None:
    model = await session.get(SpyLookPublicModel, model_id)
    if not model:
        return None
    routes_by_model = await _load_routes_for_models(session, [model.id or 0])
    return _public_model_dict(model, routes_by_model.get(model.id or 0, []))


async def get_public_model_by_name(session: AsyncSession, name: str) -> SpyLookPublicModel | None:
    stmt = select(SpyLookPublicModel).where(SpyLookPublicModel.name == name.strip())
    return await _scalar_one(session, stmt)


async def list_public_model_ids(session: AsyncSession) -> list[str]:
    stmt = (
        select(SpyLookPublicModel.name)
        .where(SpyLookPublicModel.enabled == True)
        .order_by(SpyLookPublicModel.name.asc())
    )
    rows = await session.execute(stmt)
    return [str(row[0]) for row in rows.all()]


async def list_enabled_routes_for_model(
    session: AsyncSession,
    public_model_name: str,
) -> tuple[str | None, list[ResolvedModelRoute]]:
    model = await get_public_model_by_name(session, public_model_name)
    if not model or not model.enabled or model.id is None:
        return None, []

    stmt = (
        select(SpyLookPublicModelRoute, SpyLookUpstream)
        .join(SpyLookUpstream, SpyLookUpstream.id == SpyLookPublicModelRoute.upstream_id)
        .where(
            SpyLookPublicModelRoute.public_model_id == model.id,
            SpyLookPublicModelRoute.enabled == True,
            SpyLookUpstream.enabled == True,
        )
        .order_by(
            SpyLookPublicModelRoute.sort_order.asc(),
            SpyLookPublicModelRoute.id.asc(),
        )
    )
    rows = await session.execute(stmt)
    routes: list[ResolvedModelRoute] = []
    for route, upstream in rows.all():
        upstream_row = upstream.model_dump(mode="json")
        routes.append(
            ResolvedModelRoute(
                upstream_row=upstream_row,
                upstream_model=str(route.upstream_model),
            )
        )
    return model.name, routes


def _validate_routes(routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not routes:
        raise ValueError("至少配置一条模型源绑定")
    seen: set[tuple[int, str]] = set()
    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(routes):
        upstream_id = int(item.get("upstream_id") or 0)
        upstream_model = str(item.get("upstream_model") or "").strip()
        if upstream_id <= 0:
            raise ValueError("upstream_id 无效")
        if not upstream_model:
            raise ValueError("upstream_model 不能为空")
        key = (upstream_id, upstream_model)
        if key in seen:
            raise ValueError("同一模型源下的实际模型不可重复绑定")
        seen.add(key)
        normalized.append({
            "upstream_id": upstream_id,
            "upstream_model": upstream_model,
            "enabled": bool(item.get("enabled", True)),
            "sort_order": idx,
        })
    return normalized


async def _replace_routes(
    session: AsyncSession,
    public_model_id: int,
    routes: list[dict[str, Any]],
) -> None:
    await session.execute(
        delete(SpyLookPublicModelRoute).where(
            SpyLookPublicModelRoute.public_model_id == public_model_id
        )
    )
    for item in routes:
        session.add(
            SpyLookPublicModelRoute(
                public_model_id=public_model_id,
                upstream_id=item["upstream_id"],
                upstream_model=item["upstream_model"],
                sort_order=item["sort_order"],
                enabled=item["enabled"],
            )
        )


async def create_public_model(
    session: AsyncSession,
    *,
    name: str,
    enabled: bool = True,
    routes: list[dict[str, Any]],
) -> int:
    model_name = name.strip()
    if not model_name:
        raise ValueError("对外模型名称不能为空")
    existing = await get_public_model_by_name(session, model_name)
    if existing:
        raise ValueError(f"对外模型 {model_name} 已存在")
    normalized_routes = _validate_routes(routes)

    model = SpyLookPublicModel(name=model_name, enabled=enabled)
    session.add(model)
    await session.flush()
    new_id = model.id
    if new_id is None:
        raise RuntimeError("failed to create public model")
    await _replace_routes(session, new_id, normalized_routes)
    await session.commit()
    return new_id


async def update_public_model(
    session: AsyncSession,
    model_id: int,
    *,
    name: str | None = None,
    enabled: bool | None = None,
    routes: list[dict[str, Any]] | None = None,
) -> bool:
    model = await session.get(SpyLookPublicModel, model_id)
    if not model:
        return False

    if name is not None:
        new_name = name.strip()
        if not new_name:
            raise ValueError("对外模型名称不能为空")
        if new_name != model.name:
            existing = await get_public_model_by_name(session, new_name)
            if existing and existing.id != model_id:
                raise ValueError(f"对外模型 {new_name} 已存在")
            model.name = new_name
    if enabled is not None:
        model.enabled = enabled
    model.updated_at = datetime.utcnow()

    if routes is not None:
        normalized_routes = _validate_routes(routes)
        await _replace_routes(session, model_id, normalized_routes)

    await session.commit()
    return True


async def delete_public_model(session: AsyncSession, model_id: int) -> bool:
    model = await session.get(SpyLookPublicModel, model_id)
    if not model:
        return False
    await session.execute(
        delete(SpyLookPublicModelRoute).where(
            SpyLookPublicModelRoute.public_model_id == model_id
        )
    )
    await session.delete(model)
    await session.commit()
    return True


async def list_upstream_bindings(session: AsyncSession, upstream_id: int) -> list[dict[str, Any]]:
    stmt = (
        select(SpyLookPublicModelRoute, SpyLookPublicModel.name)
        .join(SpyLookPublicModel, SpyLookPublicModel.id == SpyLookPublicModelRoute.public_model_id)
        .where(SpyLookPublicModelRoute.upstream_id == upstream_id)
        .order_by(SpyLookPublicModel.name.asc(), SpyLookPublicModelRoute.id.asc())
    )
    rows = await session.execute(stmt)
    return [
        {
            "public_model_id": route.public_model_id,
            "public_model_name": str(name or ""),
            "upstream_model": route.upstream_model,
        }
        for route, name in rows.all()
    ]


async def count_upstream_route_refs(session: AsyncSession, upstream_id: int) -> int:
    bindings = await list_upstream_bindings(session, upstream_id)
    return len(bindings)
