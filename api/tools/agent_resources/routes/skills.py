from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from sqlmodel.ext.asyncio.session import AsyncSession

from db import agent_skills as skills_db
from db.engine import get_session
from tools.agent_resources.schemas import (
    CreateSkillRequest,
    CreateTagRequest,
    GithubImportRequest,
    RestoreVersionRequest,
    SetSkillTagsRequest,
    UpdateSkillMdRequest,
    UpdateTagRequest,
)
from tools.agent_resources.services.skill_package import (
    MAX_SKILL_BYTES,
    create_empty_skill,
    fetch_github_skill,
    parse_file_map,
    parse_zip_bytes,
    replace_skill_md,
)

router = APIRouter(prefix="/agent-resources/admin", tags=["agent-resources-admin"])


def _http_value_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _http_lookup(exc: LookupError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/skills")
async def list_skills(
    q: str | None = None,
    tag_ids: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    ids: list[int] | None = None
    if tag_ids:
        try:
            ids = [int(x) for x in tag_ids.split(",") if x.strip()]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="tag_ids 格式无效") from exc
    items = await skills_db.list_skills(session, q=q, tag_ids=ids)
    return JSONResponse(content={"items": items})


@router.get("/skills/{skill_id}")
async def get_skill(
    skill_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    detail = await skills_db.get_skill_detail(session, skill_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    return JSONResponse(content=detail)


@router.post("/skills")
async def create_skill(
    body: CreateSkillRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        package = create_empty_skill(name=body.name, description=body.description)
        detail = await skills_db.create_or_version_skill(session, package, body.changelog)
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=detail)


@router.post("/skills/from-zip")
async def import_from_zip(
    file: UploadFile = File(...),
    changelog: str = Form("上传 zip"),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    raw = await file.read()
    try:
        package = parse_zip_bytes(raw)
        detail = await skills_db.create_or_version_skill(session, package, changelog)
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=detail)


@router.post("/skills/from-files")
async def import_from_files(
    files: list[UploadFile] = File(...),
    changelog: str = Form("上传文件夹"),
    root_name: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    file_map: dict[str, bytes] = {}
    total = 0
    for f in files:
        # webkitdirectory sends filename as relative path with /
        rel = (f.filename or "").replace("\\", "/").lstrip("./")
        if not rel:
            continue
        data = await f.read()
        total += len(data)
        if total > MAX_SKILL_BYTES * 2:
            raise HTTPException(status_code=400, detail="文件夹总大小过大")
        file_map[rel] = data
    # If browser sent paths like "my-skill/SKILL.md", root_name optional
    # If paths like "folder/my-skill/...", strip outer folder once when single top dir
    try:
        package = parse_file_map(file_map, root_name=root_name)
        detail = await skills_db.create_or_version_skill(session, package, changelog)
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=detail)


@router.post("/skills/from-github")
async def import_from_github(
    body: GithubImportRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        package = await fetch_github_skill(body.url)
        detail = await skills_db.create_or_version_skill(session, package, body.changelog)
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"拉取失败: {exc}") from exc
    return JSONResponse(content=detail)


@router.post("/skills/{skill_id}/replace-zip")
async def replace_zip(
    skill_id: int,
    file: UploadFile = File(...),
    changelog: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    raw = await file.read()
    try:
        package = parse_zip_bytes(raw)
        detail = await skills_db.update_skill_package(session, skill_id, package, changelog)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=detail)


@router.put("/skills/{skill_id}/skill-md")
@router.post("/skills/{skill_id}/skill-md")
async def update_skill_md(
    skill_id: int,
    body: UpdateSkillMdRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        current = await skills_db.get_skill_row(session, skill_id)
        if current is None:
            raise LookupError("Skill 不存在")
        package_zip = await skills_db.get_current_package(session, current)
        package = replace_skill_md(package_zip, body.content)
        detail = await skills_db.update_skill_package(session, skill_id, package, body.changelog)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=detail)


@router.post("/skills/{skill_id}/restore/{version}")
async def restore_version(
    skill_id: int,
    version: int,
    body: RestoreVersionRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        detail = await skills_db.restore_version(session, skill_id, version, body.changelog)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=detail)


@router.get("/skills/{skill_id}/download")
async def download_skill(
    skill_id: int,
    version: int | None = None,
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        filename, data = await skills_db.download_package(session, skill_id, version)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    quoted = quote(filename)
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quoted}"
        },
    )


@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        await skills_db.delete_skill(session, skill_id)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    return JSONResponse(content={"ok": True})


@router.put("/skills/{skill_id}/tags")
@router.post("/skills/{skill_id}/tags")
async def set_tags(
    skill_id: int,
    body: SetSkillTagsRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        detail = await skills_db.set_skill_tags(session, skill_id, body.tag_ids)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=detail)


@router.get("/tags")
async def list_tags(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    items = await skills_db.list_tags(session)
    return JSONResponse(content={"items": items})


@router.post("/tags")
async def create_tag(
    body: CreateTagRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        tag = await skills_db.create_tag(session, body.name, body.color)
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=tag)


@router.api_route("/tags/{tag_id}", methods=["PATCH", "POST"])
async def update_tag(
    tag_id: int,
    body: UpdateTagRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        tag = await skills_db.update_tag(session, tag_id, name=body.name, color=body.color)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=tag)


@router.delete("/tags/{tag_id}")
async def delete_tag(
    tag_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        await skills_db.delete_tag(session, tag_id)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    return JSONResponse(content={"ok": True})
