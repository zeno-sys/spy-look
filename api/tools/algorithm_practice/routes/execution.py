from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from tools.algorithm_practice.schemas import ExecuteCodeRequest, SyntaxCheckRequest
from tools.algorithm_practice.services.executor import check_syntax, execute_python

router = APIRouter(prefix="/algorithm/admin", tags=["algorithm-execution"])


@router.post("/execute")
async def execute_code(body: ExecuteCodeRequest) -> JSONResponse:
    result = await execute_python(body.code, body.stdin)
    return JSONResponse(content=result)


@router.post("/syntax-check")
async def syntax_check(body: SyntaxCheckRequest) -> JSONResponse:
    errors = check_syntax(body.code)
    return JSONResponse(content={"errors": errors})
