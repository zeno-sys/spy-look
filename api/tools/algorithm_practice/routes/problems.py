from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from db.algorithm_practice import (
    create_problem,
    delete_problem,
    get_problem_detail,
    list_problems,
    set_problem_tags,
    update_problem,
)
from db.engine import get_session
from tools.algorithm_practice.schemas import (
    CreateProblemRequest,
    SetProblemTagsRequest,
    UpdateProblemRequest,
)

router = APIRouter(prefix="/algorithm/admin", tags=["algorithm-problems"])


def _http_value_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _http_lookup(exc: LookupError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/problems")
async def get_problems(
    q: str | None = None,
    tag_ids: str | None = None,
    sort: str = "updated_desc",
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    parsed_tag_ids: list[int] | None = None
    if tag_ids:
        try:
            parsed_tag_ids = [int(x) for x in tag_ids.split(",") if x.strip()]
        except ValueError:
            parsed_tag_ids = None

    items = await list_problems(
        session,
        q=q,
        tag_ids=parsed_tag_ids,
        sort=sort,
    )
    return JSONResponse(content={"items": items})


@router.get("/problems/{problem_id}")
async def get_problem(
    problem_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    detail = await get_problem_detail(session, problem_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="题目不存在")
    return JSONResponse(content=detail)


@router.post("/problems")
async def post_problem(
    body: CreateProblemRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        item = await create_problem(
            session,
            title=body.title,
            description=body.description,
            tag_ids=body.tag_ids,
        )
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=item)


@router.post("/problems/{problem_id}")
@router.put("/problems/{problem_id}")
async def update_problem_endpoint(
    problem_id: int,
    body: UpdateProblemRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        item = await update_problem(
            session,
            problem_id,
            title=body.title,
            description=body.description,
            solution_code=body.solution_code,
            thought=body.thought,
        )
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=item)


@router.delete("/problems/{problem_id}")
async def delete_problem_endpoint(
    problem_id: int,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        await delete_problem(session, problem_id)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    return JSONResponse(content={"ok": True})


@router.post("/problems/{problem_id}/tags")
@router.put("/problems/{problem_id}/tags")
async def set_problem_tags_endpoint(
    problem_id: int,
    body: SetProblemTagsRequest,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        item = await set_problem_tags(session, problem_id, body.tag_ids)
    except LookupError as exc:
        raise _http_lookup(exc) from exc
    except ValueError as exc:
        raise _http_value_error(exc) from exc
    return JSONResponse(content=item)
