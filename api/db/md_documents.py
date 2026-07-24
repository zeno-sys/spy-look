from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from db.models import SpyLookMdDocument, SpyLookMdDocumentImage, SpyLookMdRecentOpen

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
RECENT_TOP_N = 5
DEFAULT_TITLE = "未命名.md"

ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def _utf8_bytes(text: str) -> int:
    return len(text.encode("utf-8"))


def _ensure_title(title: str | None) -> str:
    name = (title or "").strip() or DEFAULT_TITLE
    if not name.lower().endswith((".md", ".markdown", ".txt")):
        name = f"{name}.md"
    return name[:255]


def _doc_list_item(row: SpyLookMdDocument) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "content_bytes": row.content_bytes,
        "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None,
        "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
    }


def _doc_detail(row: SpyLookMdDocument) -> dict[str, Any]:
    item = _doc_list_item(row)
    item["content"] = row.content
    return item


async def list_documents(session: AsyncSession) -> list[dict[str, Any]]:
    stmt = select(SpyLookMdDocument).order_by(SpyLookMdDocument.updated_at.desc())
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    return [_doc_list_item(row) for row in rows]


async def create_document(
    session: AsyncSession,
    *,
    title: str | None = None,
    content: str = "",
) -> dict[str, Any]:
    text = content or ""
    size = _utf8_bytes(text)
    if size > MAX_DOCUMENT_BYTES:
        raise ValueError(f"文档超过大小上限 ({MAX_DOCUMENT_BYTES // (1024 * 1024)} MB)")
    now = datetime.utcnow()
    row = SpyLookMdDocument(
        title=_ensure_title(title),
        content=text,
        content_bytes=size,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _doc_detail(row)


async def get_document(session: AsyncSession, document_id: int) -> dict[str, Any] | None:
    row = await session.get(SpyLookMdDocument, document_id)
    if row is None:
        return None
    return _doc_detail(row)


async def touch_recent_open(session: AsyncSession, document_id: int) -> None:
    row = await session.get(SpyLookMdDocument, document_id)
    if row is None:
        return
    recent = await session.get(SpyLookMdRecentOpen, document_id)
    now = datetime.utcnow()
    if recent is None:
        session.add(SpyLookMdRecentOpen(document_id=document_id, opened_at=now))
    else:
        recent.opened_at = now
        session.add(recent)
    await session.commit()


async def list_recent_opens(session: AsyncSession) -> list[dict[str, Any]]:
    stmt = (
        select(SpyLookMdRecentOpen, SpyLookMdDocument)
        .join(SpyLookMdDocument, SpyLookMdDocument.id == SpyLookMdRecentOpen.document_id)
        .order_by(SpyLookMdRecentOpen.opened_at.desc())
        .limit(RECENT_TOP_N)
    )
    result = await session.execute(stmt)
    items: list[dict[str, Any]] = []
    for recent, doc in result.all():
        items.append(
            {
                "id": doc.id,
                "title": doc.title,
                "opened_at": recent.opened_at.isoformat() + "Z" if recent.opened_at else None,
                "updated_at": doc.updated_at.isoformat() + "Z" if doc.updated_at else None,
            }
        )
    return items


async def update_document(
    session: AsyncSession,
    document_id: int,
    *,
    title: str | None = None,
    content: str | None = None,
) -> dict[str, Any] | None:
    row = await session.get(SpyLookMdDocument, document_id)
    if row is None:
        return None
    if title is not None:
        row.title = _ensure_title(title)
    if content is not None:
        size = _utf8_bytes(content)
        if size > MAX_DOCUMENT_BYTES:
            raise ValueError(f"文档超过大小上限 ({MAX_DOCUMENT_BYTES // (1024 * 1024)} MB)")
        row.content = content
        row.content_bytes = size
    row.updated_at = datetime.utcnow()
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _doc_detail(row)


async def delete_document(session: AsyncSession, document_id: int) -> bool:
    row = await session.get(SpyLookMdDocument, document_id)
    if row is None:
        return False
    await session.execute(
        delete(SpyLookMdDocumentImage).where(SpyLookMdDocumentImage.document_id == document_id)
    )
    await session.execute(
        delete(SpyLookMdRecentOpen).where(SpyLookMdRecentOpen.document_id == document_id)
    )
    await session.delete(row)
    await session.commit()
    return True


async def create_document_image(
    session: AsyncSession,
    document_id: int,
    *,
    data: bytes,
    content_type: str,
    filename: str | None = None,
) -> dict[str, Any]:
    doc = await session.get(SpyLookMdDocument, document_id)
    if doc is None:
        raise LookupError("document not found")
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype not in ALLOWED_IMAGE_TYPES:
        raise ValueError("仅支持 png / jpeg / gif / webp 图片")
    if not data:
        raise ValueError("图片内容为空")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(f"单张图片超过大小上限 ({MAX_IMAGE_BYTES // (1024 * 1024)} MB)")

    ext = ALLOWED_IMAGE_TYPES[ctype]
    name = (filename or f"image{ext}").strip() or f"image{ext}"
    row = SpyLookMdDocumentImage(
        document_id=document_id,
        filename=name[:255],
        content_type=ctype if ctype != "image/jpg" else "image/jpeg",
        data=data,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    image_id = row.id or 0
    return {
        "id": image_id,
        "document_id": document_id,
        "filename": row.filename,
        "content_type": row.content_type,
        "url": f"/doc-tools/admin/documents/{document_id}/images/{image_id}",
        "size": len(data),
    }


async def get_document_image(
    session: AsyncSession,
    document_id: int,
    image_id: int,
) -> SpyLookMdDocumentImage | None:
    row = await session.get(SpyLookMdDocumentImage, image_id)
    if row is None or row.document_id != document_id:
        return None
    return row
